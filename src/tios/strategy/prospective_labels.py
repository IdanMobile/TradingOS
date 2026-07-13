"""Causal future-label timing and exact Binance Spot kline parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from tios.strategy.liquidation_stress import LiquidationStressError, window_start

BAR = timedelta(minutes=1)
WINDOW = timedelta(minutes=5)
HORIZONS = {"1H": timedelta(hours=1), "6H": timedelta(hours=6), "24H": timedelta(hours=24)}


@dataclass(frozen=True, slots=True)
class LabelTimes:
    window_close: datetime
    entry_open: datetime
    exit_open: datetime
    available_at: datetime


def label_times(window: datetime, horizon: str) -> LabelTimes:
    """Return frozen strictly-later entry, exit, and causal availability times."""
    if window != window_start(window):
        raise LiquidationStressError("label window must be UTC five-minute aligned")
    try:
        duration = HORIZONS[horizon]
    except KeyError as error:
        raise LiquidationStressError("unsupported prospective label horizon") from error
    close = window + WINDOW
    entry = close + BAR
    exit_open = entry + duration
    return LabelTimes(close, entry, exit_open, exit_open + BAR)


def parse_exact_kline(raw: bytes, *, expected_open: datetime) -> Decimal:
    """Parse one exact completed Binance one-minute kline and return its open."""
    if expected_open.tzinfo is None or expected_open.utcoffset() != UTC.utcoffset(expected_open):
        raise LiquidationStressError("expected kline open must be UTC-aware")
    expected_ms = int(expected_open.timestamp() * 1000)
    try:
        payload = json.loads(raw)
        if not isinstance(payload, list) or len(payload) != 1:
            raise LiquidationStressError("exact kline response must contain one row")
        row = payload[0]
        if not isinstance(row, list) or len(row) != 12:
            raise LiquidationStressError("exact kline row schema changed")
        if row[0] != expected_ms or row[6] != expected_ms + 59_999:
            raise LiquidationStressError("exact kline timestamps do not match request")
        price = Decimal(str(row[1]))
    except (json.JSONDecodeError, InvalidOperation, TypeError, IndexError) as error:
        raise LiquidationStressError("invalid exact kline response") from error
    if price <= 0 or not price.is_finite():
        raise LiquidationStressError("exact kline open must be finite and positive")
    return price


def gross_return(entry: Decimal, exit_: Decimal) -> Decimal:
    if entry <= 0 or exit_ <= 0 or not entry.is_finite() or not exit_.is_finite():
        raise LiquidationStressError("label prices must be finite and positive")
    return exit_ / entry - Decimal(1)
