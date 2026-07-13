"""Prospective forced-order snapshot parsing and risk-state classification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

WINDOW_SECONDS = 300
BASELINE_WINDOWS = 8_640
SELL_SHARE_THRESHOLD = Decimal("0.80")


class LiquidationStressError(ValueError):
    """A prospective source record violates the frozen observation contract."""


class LiquidationStressState(StrEnum):
    SOURCE_WINDOW_INCOMPLETE = "SOURCE_WINDOW_INCOMPLETE"
    WARMUP_BLOCK = "WARMUP_BLOCK"
    LONG_LIQUIDATION_STRESS = "LONG_LIQUIDATION_STRESS"
    SHORT_LIQUIDATION_STRESS = "SHORT_LIQUIDATION_STRESS"
    NORMAL = "NORMAL"


@dataclass(frozen=True, slots=True)
class LiquidationSnapshot:
    event_time: datetime
    transaction_time: datetime
    received_at: datetime
    symbol: str
    pair: str
    side: str
    accumulated_filled_contracts: Decimal
    average_price: Decimal
    contract_size_usd: Decimal
    symbol_type: int

    @property
    def executed_notional_usd(self) -> Decimal:
        return self.accumulated_filled_contracts * self.contract_size_usd

    @property
    def identity(self) -> tuple[object, ...]:
        return (
            self.event_time,
            self.transaction_time,
            self.symbol,
            self.side,
            self.accumulated_filled_contracts,
            self.average_price,
        )


@dataclass(frozen=True, slots=True)
class LiquidationWindow:
    start: datetime
    complete: bool
    event_count: int
    gross_notional_usd: Decimal
    buy_notional_usd: Decimal
    sell_notional_usd: Decimal

    @property
    def sell_share(self) -> Decimal:
        if self.gross_notional_usd == 0:
            return Decimal(0)
        return self.sell_notional_usd / self.gross_notional_usd


def parse_force_order_message(
    raw_message: str,
    *,
    received_at: datetime,
    expected_symbol: str,
    expected_pair: str,
    contract_size_usd: Decimal,
) -> LiquidationSnapshot:
    """Parse one official force-order snapshot without treating it as a complete tape."""
    _require_utc(received_at, "received_at")
    if contract_size_usd <= 0 or not contract_size_usd.is_finite():
        raise LiquidationStressError("contract_size_usd must be finite and positive")
    try:
        payload = json.loads(raw_message)
        order = payload["o"]
        event_time_ms = _integer(payload["E"], "event time")
        transaction_time_ms = _integer(order["T"], "transaction time")
        symbol = str(order["s"])
        pair = str(order["ps"])
        side = str(order["S"])
        accumulated = Decimal(str(order["z"]))
        average_price = Decimal(str(order["ap"]))
        symbol_type = _integer(payload["st"], "symbol type")
    except (KeyError, TypeError, json.JSONDecodeError, InvalidOperation) as error:
        raise LiquidationStressError("invalid force-order snapshot schema") from error
    if payload.get("e") != "forceOrder":
        raise LiquidationStressError("unexpected event type")
    if symbol != expected_symbol or pair != expected_pair:
        raise LiquidationStressError("force-order instrument identity changed")
    if side not in {"BUY", "SELL"}:
        raise LiquidationStressError("force-order side is invalid")
    if accumulated <= 0 or not accumulated.is_finite():
        raise LiquidationStressError("accumulated filled contracts must be finite and positive")
    if average_price <= 0 or not average_price.is_finite():
        raise LiquidationStressError("average price must be finite and positive")
    event_time = datetime.fromtimestamp(event_time_ms / 1000, UTC)
    transaction_time = datetime.fromtimestamp(transaction_time_ms / 1000, UTC)
    if transaction_time > event_time or event_time > received_at:
        raise LiquidationStressError("force-order timestamps are not causal")
    return LiquidationSnapshot(
        event_time=event_time,
        transaction_time=transaction_time,
        received_at=received_at,
        symbol=symbol,
        pair=pair,
        side=side,
        accumulated_filled_contracts=accumulated,
        average_price=average_price,
        contract_size_usd=contract_size_usd,
        symbol_type=symbol_type,
    )


def window_start(at: datetime) -> datetime:
    _require_utc(at, "window timestamp")
    seconds = int(at.timestamp())
    return datetime.fromtimestamp(seconds - seconds % WINDOW_SECONDS, UTC)


def aggregate_window(
    snapshots: tuple[LiquidationSnapshot, ...], *, start: datetime, complete: bool
) -> LiquidationWindow:
    _require_utc(start, "window start")
    if start != window_start(start):
        raise LiquidationStressError("window start must align to the UTC epoch")
    end = datetime.fromtimestamp(start.timestamp() + WINDOW_SECONDS, UTC)
    unique: dict[tuple[object, ...], LiquidationSnapshot] = {}
    for snapshot in snapshots:
        if not start <= snapshot.event_time < end:
            raise LiquidationStressError("snapshot falls outside the requested window")
        unique[snapshot.identity] = snapshot
    buy = sum(
        (item.executed_notional_usd for item in unique.values() if item.side == "BUY"),
        Decimal(0),
    )
    sell = sum(
        (item.executed_notional_usd for item in unique.values() if item.side == "SELL"),
        Decimal(0),
    )
    return LiquidationWindow(start, complete, len(unique), buy + sell, buy, sell)


def nearest_rank_99(values: tuple[Decimal, ...]) -> Decimal:
    if not values or any(value < 0 or not value.is_finite() for value in values):
        raise LiquidationStressError("quantile inputs must be finite and nonnegative")
    ordered = sorted(values)
    rank = (99 * len(ordered) + 99) // 100
    return ordered[rank - 1]


def classify_window(
    current: LiquidationWindow,
    *,
    prior_complete_gross_notional: tuple[Decimal, ...],
) -> LiquidationStressState:
    if not current.complete:
        return LiquidationStressState.SOURCE_WINDOW_INCOMPLETE
    if len(prior_complete_gross_notional) != BASELINE_WINDOWS:
        return LiquidationStressState.WARMUP_BLOCK
    threshold = nearest_rank_99(prior_complete_gross_notional)
    if current.gross_notional_usd <= threshold:
        return LiquidationStressState.NORMAL
    if current.sell_share >= SELL_SHARE_THRESHOLD:
        return LiquidationStressState.LONG_LIQUIDATION_STRESS
    if Decimal(1) - current.sell_share >= SELL_SHARE_THRESHOLD:
        return LiquidationStressState.SHORT_LIQUIDATION_STRESS
    return LiquidationStressState.NORMAL


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise LiquidationStressError(f"{name} must be an integer")
    return value


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise LiquidationStressError(f"{name} must be UTC-aware")
