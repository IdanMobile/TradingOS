"""Typed, read-only snapshots and configuration for the local paper cockpit."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any

from tios.strategy.spec import CanonicalStrategySpec
from tios.trading_domain import (
    ApprovalId,
    DomainRef,
    StageGateReadinessRecord,
    StrategyVersionId,
    Timeframe,
)


class PaperRuntimeError(ValueError):
    """Paper state is invalid or unsafe to activate."""


class PaperMode(StrEnum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SYNTHETIC_LOCAL_SIMULATOR = "SYNTHETIC_LOCAL_SIMULATOR"


class FreshnessStatus(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class AttentionSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PaperBotPhase(StrEnum):
    INACTIVE = "INACTIVE"
    WARMING_UP = "WARMING_UP"
    WATCHING = "WATCHING"
    POSITION_OPEN = "POSITION_OPEN"
    PAUSED = "PAUSED"
    STALE = "STALE"


class SignalWatchState(StrEnum):
    WATCHING = "WATCHING"
    TRIGGERED = "TRIGGERED"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise PaperRuntimeError(f"{name} must be timezone-aware UTC")


def _finite(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise PaperRuntimeError(f"{name} must be a finite Decimal")
    if value < 0 or (positive and value == 0):
        raise PaperRuntimeError(f"{name} must be {'positive' if positive else 'nonnegative'}")


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PaperRuntimeError(f"{name} must be non-empty")


def _decimal_identity(value: Decimal) -> str:
    """Make numerically equal Decimals share hashes without changing API formatting."""
    if not value:
        return "0"
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        raise PaperRuntimeError("decimal identity requires a finite value")
    retained = list(digits)
    while retained[-1] == 0:
        retained.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in retained)
    return f"{'-' if sign else ''}{coefficient}e{exponent}"


@dataclass(frozen=True, slots=True)
class PaperRiskPolicy:
    """Conservative immutable defaults for synthetic USDT only."""

    starting_capital: Decimal = Decimal("10000")
    max_position_notional: Decimal = Decimal("1000")
    max_total_exposure: Decimal = Decimal("2000")
    max_daily_loss: Decimal = Decimal("100")
    max_drawdown_fraction: Decimal = Decimal("0.05")
    max_open_positions: int = 2
    fee_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("2")
    quote_max_age_seconds: int = 15
    max_fill_latency_seconds: int = 5
    heartbeat_interval_seconds: int = 10
    stale_after_seconds: int = 30

    def __post_init__(self) -> None:
        for name in (
            "starting_capital",
            "max_position_notional",
            "max_total_exposure",
            "max_daily_loss",
            "max_drawdown_fraction",
        ):
            _finite(getattr(self, name), name, positive=True)
        for name in ("fee_bps", "slippage_bps"):
            _finite(getattr(self, name), name)
        if self.max_position_notional > self.max_total_exposure:
            raise PaperRuntimeError("position notional cannot exceed total exposure")
        if self.max_total_exposure > self.starting_capital:
            raise PaperRuntimeError("total exposure cannot exceed starting capital")
        if self.max_daily_loss > self.starting_capital:
            raise PaperRuntimeError("daily loss cannot exceed starting capital")
        if self.max_drawdown_fraction >= 1:
            raise PaperRuntimeError("drawdown fraction must be below 1")
        for name in (
            "max_open_positions",
            "quote_max_age_seconds",
            "max_fill_latency_seconds",
            "heartbeat_interval_seconds",
            "stale_after_seconds",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise PaperRuntimeError(f"{name} must be a positive integer")
        if self.stale_after_seconds <= self.heartbeat_interval_seconds:
            raise PaperRuntimeError("stale threshold must exceed the heartbeat interval")


@dataclass(frozen=True, slots=True)
class PaperRuntimeConfig:
    """One strategy-version/symbol/timeframe identity; activation is checked separately."""

    strategy_version_ref: StrategyVersionId
    spec: CanonicalStrategySpec
    symbol: str
    timeframe: Timeframe
    gate: StageGateReadinessRecord | None
    validation_status: str
    validation_approval_ref: ApprovalId | None
    validation_evidence_refs: tuple[DomainRef, ...]
    allocated_capital: Decimal = Decimal("1000")
    _spec_sha256: str = field(init=False, repr=False, compare=False)
    _approval_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.symbol not in {"BTCUSDT", "ETHUSDT"}:
            raise PaperRuntimeError("paper symbols are limited to BTCUSDT and ETHUSDT")
        if self.timeframe not in set(Timeframe):
            raise PaperRuntimeError("unsupported paper timeframe")
        _finite(self.allocated_capital, "allocated_capital", positive=True)
        if not isinstance(self.validation_evidence_refs, tuple):
            raise PaperRuntimeError("validation_evidence_refs must be an immutable tuple")
        object.__setattr__(self, "_spec_sha256", self.spec.spec_hash())
        object.__setattr__(self, "_approval_sha256", self._current_approval_sha256())

    def _current_approval_sha256(self) -> str:
        payload = {
            "gate": jsonable(self.gate),
            "validation_status": self.validation_status,
            "validation_approval_ref": (
                str(self.validation_approval_ref)
                if self.validation_approval_ref is not None
                else None
            ),
            "validation_evidence_refs": [str(ref) for ref in self.validation_evidence_refs],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def assert_immutable(self) -> None:
        """Reject shallow-frozen configs whose nested spec/evidence was changed in place."""
        if self.spec.spec_hash() != self._spec_sha256:
            raise PaperRuntimeError("approved canonical strategy spec changed after configuration")
        if self._current_approval_sha256() != self._approval_sha256:
            raise PaperRuntimeError(
                "approved gate or validation evidence changed after configuration"
            )

    @property
    def spec_sha256(self) -> str:
        return self._spec_sha256

    @property
    def approval_sha256(self) -> str:
        return self._approval_sha256

    @property
    def config_digest(self) -> str:
        payload = {
            "strategy_version_ref": str(self.strategy_version_ref),
            "spec_sha256": self._spec_sha256,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "allocated_capital": _decimal_identity(self.allocated_capital),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def bot_id(self) -> str:
        return f"PAPERBOT-{self.config_digest[:20]}"

    @property
    def activation_key(self) -> tuple[str, str, str]:
        """Stable lane identity whose approved specification cannot be substituted."""
        return str(self.strategy_version_ref), self.symbol, self.timeframe.value


@dataclass(frozen=True, slots=True)
class SourceFreshness:
    source: str
    status: FreshnessStatus
    observed_at: datetime | None
    detail: str

    def __post_init__(self) -> None:
        _nonempty(self.source, "source")
        _nonempty(self.detail, "detail")
        if self.observed_at is not None:
            _utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    observed_at: datetime
    equity: Decimal

    def __post_init__(self) -> None:
        _utc(self.observed_at, "observed_at")
        _finite(self.equity, "equity")


@dataclass(frozen=True, slots=True)
class PaperPositionSnapshot:
    bot_id: str
    symbol: str
    opened_at: datetime
    as_of: datetime
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal

    def __post_init__(self) -> None:
        _nonempty(self.bot_id, "bot_id")
        _utc(self.opened_at, "opened_at")
        _utc(self.as_of, "as_of")
        if self.opened_at > self.as_of:
            raise PaperRuntimeError("position cannot open after its snapshot")
        for name in ("quantity", "entry_price", "mark_price", "exposure"):
            _finite(getattr(self, name), name, positive=True)
        for name in ("realized_pnl", "unrealized_pnl"):
            value = getattr(self, name)
            if not value.is_finite():
                raise PaperRuntimeError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class PaperBotSnapshot:
    bot_id: str
    strategy_version_ref: str
    symbol: str
    timeframe: str
    config_digest: str
    phase: PaperBotPhase
    started_at: datetime | None
    heartbeat_at: datetime | None
    last_evaluated_bar_at: datetime | None
    next_evaluation_at: datetime | None
    conditions_met: tuple[str, ...]
    entries_paused: bool
    allocated_capital: Decimal
    net_pnl: Decimal
    return_fraction: Decimal
    max_drawdown_fraction: Decimal
    trade_count: int
    win_rate_fraction: Decimal | None

    def __post_init__(self) -> None:
        for name in ("bot_id", "strategy_version_ref", "symbol", "timeframe", "config_digest"):
            _nonempty(getattr(self, name), name)
        for name in (
            "started_at",
            "heartbeat_at",
            "last_evaluated_bar_at",
            "next_evaluation_at",
        ):
            value = getattr(self, name)
            if value is not None:
                _utc(value, name)
        _finite(self.allocated_capital, "allocated_capital", positive=True)
        for name in ("net_pnl", "return_fraction"):
            if not getattr(self, name).is_finite():
                raise PaperRuntimeError(f"{name} must be finite")
        _finite(self.max_drawdown_fraction, "max_drawdown_fraction")
        if self.trade_count < 0:
            raise PaperRuntimeError("trade_count must be nonnegative")
        if self.win_rate_fraction is not None and not 0 <= self.win_rate_fraction <= 1:
            raise PaperRuntimeError("win rate must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SignalWatchSnapshot:
    signal_id: str
    bot_id: str
    symbol: str
    timeframe: str
    side: str | None
    state: SignalWatchState
    observed_at: datetime
    rationale: str
    conditions_met: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("signal_id", "bot_id", "symbol", "timeframe", "rationale"):
            _nonempty(getattr(self, name), name)
        if self.side not in {None, "BUY", "SELL"}:
            raise PaperRuntimeError("signal side must be BUY, SELL, or absent")
        _utc(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class AttentionItem:
    item_id: str
    severity: AttentionSeverity
    title: str
    summary: str
    created_at: datetime
    action: str | None = None
    acknowledged: bool = False

    def __post_init__(self) -> None:
        for name in ("item_id", "title", "summary"):
            _nonempty(getattr(self, name), name)
        _utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class FindingItem:
    item_id: str
    kind: str
    title: str
    summary: str
    source: str
    published_at: datetime
    affected_subjects: tuple[str, ...]
    match_reason: str
    url: str | None = None

    def __post_init__(self) -> None:
        for name in ("item_id", "kind", "title", "summary", "source", "match_reason"):
            _nonempty(getattr(self, name), name)
        _utc(self.published_at, "published_at")


@dataclass(frozen=True, slots=True)
class PortfolioPerformance:
    available: bool
    unavailable_reason: str | None
    range: str
    as_of: datetime
    currency: str
    equity: Decimal | None
    cash: Decimal | None
    exposure: Decimal | None
    pnl: Decimal | None
    realized_pnl: Decimal | None
    unrealized_pnl: Decimal | None
    fees: Decimal | None
    drawdown_fraction: Decimal | None
    points: tuple[EquityPoint, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.range, "range")
        _utc(self.as_of, "as_of")
        _nonempty(self.currency, "currency")
        metrics = (
            self.equity,
            self.cash,
            self.exposure,
            self.pnl,
            self.realized_pnl,
            self.unrealized_pnl,
            self.fees,
            self.drawdown_fraction,
        )
        if self.available and (
            self.unavailable_reason is not None or any(v is None for v in metrics)
        ):
            raise PaperRuntimeError("available portfolio performance requires every metric")
        if not self.available and (
            not self.unavailable_reason or any(v is not None for v in metrics)
        ):
            raise PaperRuntimeError("unavailable portfolio must have a reason and no fake metrics")
        for value in metrics:
            if value is not None and not value.is_finite():
                raise PaperRuntimeError("portfolio metrics must be finite")


@dataclass(frozen=True, slots=True)
class PaperActivity:
    sequence: int
    event_type: str
    subject_id: str
    occurred_at: datetime
    summary: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise PaperRuntimeError("activity sequence must be positive")
        for name in ("event_type", "subject_id", "summary"):
            _nonempty(getattr(self, name), name)
        _utc(self.occurred_at, "occurred_at")


@dataclass(frozen=True, slots=True)
class CockpitSnapshot:
    available: bool
    reason: str | None
    mode: PaperMode
    summary: str
    as_of: datetime
    sources: tuple[SourceFreshness, ...]
    attention: tuple[AttentionItem, ...]
    portfolio: PortfolioPerformance
    bots: tuple[PaperBotSnapshot, ...]
    positions: tuple[PaperPositionSnapshot, ...]
    signals: tuple[SignalWatchSnapshot, ...]
    leaderboard: tuple[PaperBotSnapshot, ...]
    findings: tuple[FindingItem, ...]
    recent_activity: tuple[PaperActivity, ...]
    execution_authority: str = "NONE"
    venue_connection: str = "NONE"
    paper_orders: str = "DISABLED"
    live_orders: str = "DISABLED"
    real_money: bool = False

    def __post_init__(self) -> None:
        _nonempty(self.summary, "summary")
        _utc(self.as_of, "as_of")
        if self.available != self.portfolio.available:
            raise PaperRuntimeError("cockpit and portfolio availability must agree")
        if self.available and self.reason is not None:
            raise PaperRuntimeError("available cockpit cannot carry an unavailable reason")
        if not self.available and not self.reason:
            raise PaperRuntimeError("unavailable cockpit requires a reason")
        if (
            self.execution_authority != "NONE"
            or self.venue_connection != "NONE"
            or self.paper_orders != "DISABLED"
            or self.live_orders != "DISABLED"
            or self.real_money
        ):
            raise PaperRuntimeError("paper cockpit cannot grant or imply execution authority")


def jsonable(value: object) -> Any:
    """Serialize snapshot values for APIs; money stays exact decimal text."""
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        _utc(value, "timestamp")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, tuple | list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, float):
        raise PaperRuntimeError("floating-point JSON values are prohibited")
    if value is None or isinstance(value, str | int | bool):
        return value
    raise PaperRuntimeError(f"unsupported JSON value: {type(value).__name__}")
