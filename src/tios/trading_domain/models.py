"""Framework-free, inert S2 trading-domain contracts.

These types describe retained historical evidence and read projections.  They
contain no venue connectivity or trading commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar


class ContractError(ValueError):
    """Raised when a trading-domain contract invariant is violated."""


_ID_PREFIXES = (
    "DS-",
    "STRAT-",
    "SV-",
    "HYP-",
    "EXP-",
    "RUN-",
    "LAB-",
    "SCORE-",
    "VAL-",
    "EV-",
    "APR-",
    "SRC-",
    "RA-",
    "CON-",
    "MDL-",
    "AGT-",
    "PRM-",
    "BMK-",
    "LRN-",
    "JOB-",
    "SIG-",
    "ORD-",
    "FILL-",
    "POS-",
    "ACCT-",
    "PF-",
    "RISK-",
    "ANN-",
)
_ID_SUFFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_CURRENCY = re.compile(r"[A-Z][A-Z0-9]{2,9}\Z")
_CONTEXT_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _require_decimal(value: Decimal, field_name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractError(f"{field_name} must be a finite Decimal")
    if value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ContractError(f"{field_name} must be {qualifier}")


def _require_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContractError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ContractError(f"{field_name} must be UTC")


def _require_tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise ContractError(f"{field_name} must be an immutable tuple")


@dataclass(frozen=True, slots=True)
class PrefixedId:
    value: str
    prefix: ClassVar[str]

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.startswith(self.prefix):
            raise ContractError(f"id must start with {self.prefix}")
        if not _ID_SUFFIX.fullmatch(self.value[len(self.prefix) :]):
            raise ContractError("id must have a non-empty opaque suffix")

    def __str__(self) -> str:
        return self.value


class DatasetId(PrefixedId):
    prefix = "DS-"


class StrategyVersionId(PrefixedId):
    prefix = "SV-"


class RunId(PrefixedId):
    prefix = "RUN-"


class SignalId(PrefixedId):
    prefix = "SIG-"


class OrderId(PrefixedId):
    prefix = "ORD-"


class FillId(PrefixedId):
    prefix = "FILL-"


class PositionId(PrefixedId):
    prefix = "POS-"


class AccountId(PrefixedId):
    prefix = "ACCT-"


class PortfolioId(PrefixedId):
    prefix = "PF-"


class RiskId(PrefixedId):
    prefix = "RISK-"


class ApprovalId(PrefixedId):
    prefix = "APR-"


class AnnotationId(PrefixedId):
    prefix = "ANN-"


@dataclass(frozen=True, slots=True)
class DomainRef:
    value: str

    def __post_init__(self) -> None:
        prefix = next((item for item in _ID_PREFIXES if self.value.startswith(item)), None)
        if prefix is None or not _ID_SUFFIX.fullmatch(self.value[len(prefix) :]):
            raise ContractError("reference must be an opaque catalog-prefixed id")

    @property
    def prefix(self) -> str:
        return next(item for item in _ID_PREFIXES if self.value.startswith(item))

    def __str__(self) -> str:
        return self.value


class Environment(StrEnum):
    HISTORICAL_RESEARCH = "HISTORICAL_RESEARCH"


class ExecutionAuthority(StrEnum):
    NONE = "NONE"


class VenueConnection(StrEnum):
    NONE = "NONE"


class OrderCapability(StrEnum):
    DISABLED = "DISABLED"


class CreatorType(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return {
            Timeframe.M1: 60,
            Timeframe.M5: 300,
            Timeframe.M15: 900,
            Timeframe.H1: 3600,
            Timeframe.H4: 14400,
            Timeframe.D1: 86400,
        }[self]


@dataclass(frozen=True, slots=True)
class MarketName:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CONTEXT_NAME.fullmatch(self.value):
            raise ContractError("market must be an uppercase canonical name")


@dataclass(frozen=True, slots=True)
class VenueFamily:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CONTEXT_NAME.fullmatch(self.value):
            raise ContractError("venue family must be an uppercase canonical name")


@dataclass(frozen=True, slots=True)
class InstrumentId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ContractError("instrument must be a string")
        pair, separator, venue = self.value.partition(".")
        base, dash, quote = pair.partition("-")
        if (
            separator != "."
            or dash != "-"
            or not base
            or not quote
            or not _CONTEXT_NAME.fullmatch(base)
            or not _CONTEXT_NAME.fullmatch(quote)
            or not _CONTEXT_NAME.fullmatch(venue)
        ):
            raise ContractError("instrument must match BASE-QUOTE.VENUE_FAMILY")

    @property
    def base_currency(self) -> str:
        return self.value.partition("-")[0]

    @property
    def quote_currency(self) -> str:
        return self.value.partition("-")[2].partition(".")[0]

    @property
    def venue_family(self) -> VenueFamily:
        return VenueFamily(self.value.partition(".")[2])


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        _require_decimal(self.amount, "money amount")
        if not isinstance(self.currency, str) or not _CURRENCY.fullmatch(self.currency):
            raise ContractError("currency must be an uppercase currency code")


@dataclass(frozen=True, slots=True)
class Provenance:
    refs: tuple[DomainRef, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.refs, "provenance refs")
        if not self.refs or len(set(self.refs)) != len(self.refs):
            raise ContractError("provenance refs must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class Market:
    market: MarketName
    venue_family: VenueFamily
    instrument: InstrumentId
    timeframe: Timeframe
    dataset_ref: DatasetId

    def __post_init__(self) -> None:
        if self.instrument.venue_family != self.venue_family:
            raise ContractError("instrument and market venue families must match")


def _validate_record(
    schema_version: int,
    created_at: datetime,
    provenance: Provenance,
    environment: Environment,
) -> None:
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        raise ContractError("schema_version must be a positive integer")
    _require_utc(created_at, "created_at")
    if not isinstance(provenance, Provenance):
        raise ContractError("provenance must be a Provenance value")
    if environment is not Environment.HISTORICAL_RESEARCH:
        raise ContractError("only historical research records exist in S2")


@dataclass(frozen=True, slots=True)
class MarketBar:
    market: Market
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.open_time, "open_time")
        _require_utc(self.close_time, "close_time")
        if self.open_time >= self.close_time:
            raise ContractError("bar open_time must precede close_time")
        for name in ("open", "high", "low", "close"):
            _require_decimal(getattr(self, name), name, positive=True)
        _require_decimal(self.volume, "volume")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ContractError("bar OHLC values must lie between low and high")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    market: Market
    observed_at: datetime
    bid_price: Decimal
    bid_quantity: Decimal
    ask_price: Decimal
    ask_quantity: Decimal
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        for name in ("bid_price", "bid_quantity", "ask_price", "ask_quantity"):
            _require_decimal(getattr(self, name), name, positive=True)
        if self.bid_price > self.ask_price:
            raise ContractError("bid price cannot exceed ask price")


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class SignalEvent:
    signal_id: SignalId
    strategy_version_ref: StrategyVersionId
    run_ref: RunId
    instrument: InstrumentId
    timeframe: Timeframe
    observed_at: datetime
    side: Side
    rationale_code: str
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        if not self.rationale_code or not self.rationale_code.strip():
            raise ContractError("rationale_code must be non-empty")


@dataclass(frozen=True, slots=True)
class BracketLevels:
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    trailing_distance: Decimal | None = None

    def __post_init__(self) -> None:
        if self.take_profit is self.stop_loss is self.trailing_distance is None:
            raise ContractError("at least one bracket level is required")
        for name in ("take_profit", "stop_loss", "trailing_distance"):
            value = getattr(self, name)
            if value is not None:
                _require_decimal(value, name, positive=True)
        if self.trailing_distance is not None and self.trailing_distance >= 1:
            raise ContractError("trailing_distance is a percentage fraction below 1")
        if self.take_profit is not None and self.take_profit == self.stop_loss:
            raise ContractError("take-profit and stop-loss levels must differ")


def validate_bracket_levels(levels: BracketLevels, side: Side, reference_price: Decimal) -> None:
    """Validate directional bracket prices against an inert reference price."""
    _require_decimal(reference_price, "reference_price", positive=True)
    if side is Side.FLAT:
        raise ContractError("FLAT has no order bracket")
    if levels.take_profit is not None:
        valid_take_profit = (
            levels.take_profit > reference_price
            if side is Side.BUY
            else levels.take_profit < reference_price
        )
        if not valid_take_profit:
            raise ContractError("take-profit level is on the wrong side of the reference price")
    if levels.stop_loss is not None:
        valid_stop_loss = (
            levels.stop_loss < reference_price
            if side is Side.BUY
            else levels.stop_loss > reference_price
        )
        if not valid_stop_loss:
            raise ContractError("stop-loss level is on the wrong side of the reference price")


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    source_signal_ref: SignalId | None
    run_ref: RunId
    instrument: InstrumentId
    side: Side
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    bracket_levels: BracketLevels | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        if self.side is Side.FLAT:
            raise ContractError("an order intent side must be BUY or SELL")
        _require_decimal(self.quantity, "quantity", positive=True)
        if self.limit_price is not None:
            _require_decimal(self.limit_price, "limit_price", positive=True)
        if self.stop_price is not None:
            _require_decimal(self.stop_price, "stop_price", positive=True)
        required = {
            OrderType.MARKET: (False, False),
            OrderType.LIMIT: (True, False),
            OrderType.STOP: (False, True),
            OrderType.STOP_LIMIT: (True, True),
        }[self.order_type]
        if (self.limit_price is not None, self.stop_price is not None) != required:
            raise ContractError(f"invalid price fields for {self.order_type}")
        reference_price = self.limit_price or self.stop_price
        if self.bracket_levels is not None and reference_price is not None:
            validate_bracket_levels(self.bracket_levels, self.side, reference_price)


class LiquidityRole(StrEnum):
    MAKER = "MAKER"
    TAKER = "TAKER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FillEvent:
    fill_id: FillId
    order_ref: OrderId
    run_ref: RunId
    instrument: InstrumentId
    filled_at: datetime
    price: Decimal
    quantity: Decimal
    fee: Money
    liquidity_role: LiquidityRole | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.filled_at, "filled_at")
        _require_decimal(self.price, "price", positive=True)
        _require_decimal(self.quantity, "quantity", positive=True)
        if self.fee.currency != self.instrument.quote_currency:
            raise ContractError("fill fee currency must match the instrument quote currency")


class OrderStatus(StrEnum):
    INERT = "INERT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.INERT: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED}
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
}
TERMINAL_ORDER_STATES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}
)


def validate_order_transition(current: OrderStatus, target: OrderStatus) -> None:
    """Raise unless a retained order snapshot may follow another snapshot."""
    if target not in _ORDER_TRANSITIONS[current]:
        raise ContractError(f"invalid order transition: {current} -> {target}")


@dataclass(frozen=True, slots=True)
class OrderState:
    order_id: OrderId
    intent: OrderIntent
    observed_at: datetime
    state: OrderStatus
    fills: tuple[FillEvent, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        _require_tuple(self.fills, "fills")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("S2 order capabilities must remain disabled")
        if len({fill.fill_id for fill in self.fills}) != len(self.fills):
            raise ContractError("fill ids must be unique within an order history")
        for fill in self.fills:
            if (
                fill.order_ref != self.order_id
                or fill.run_ref != self.intent.run_ref
                or fill.instrument != self.intent.instrument
                or fill.filled_at > self.observed_at
            ):
                raise ContractError("fill context or timestamp does not match the order snapshot")
        quantity = self.filled_quantity
        if quantity > self.intent.quantity:
            raise ContractError("aggregate fill quantity exceeds order quantity")
        if self.state is OrderStatus.INERT and quantity != 0:
            raise ContractError("an INERT order cannot contain fills")
        if self.state is OrderStatus.PARTIALLY_FILLED and not (0 < quantity < self.intent.quantity):
            raise ContractError("PARTIALLY_FILLED requires a partial aggregate quantity")
        if self.state is OrderStatus.FILLED and quantity != self.intent.quantity:
            raise ContractError("FILLED requires the exact order quantity")
        if self.state is OrderStatus.REJECTED and quantity != 0:
            raise ContractError("a rejected order cannot contain fills")

    @property
    def filled_quantity(self) -> Decimal:
        return sum((fill.quantity for fill in self.fills), Decimal(0))

    @property
    def average_fill_price(self) -> Decimal | None:
        if not self.fills:
            return None
        notional = sum((fill.price * fill.quantity for fill in self.fills), Decimal(0))
        return notional / self.filled_quantity

    @property
    def total_fee(self) -> Money:
        amount = sum((fill.fee.amount for fill in self.fills), Decimal(0))
        return Money(amount, self.intent.instrument.quote_currency)


def aggregate_fills(
    snapshot: OrderState,
    fills: tuple[FillEvent, ...],
    *,
    observed_at: datetime,
    event_cursor: int,
) -> OrderState:
    """Return the next inert snapshot from newly retained historical fills."""
    _require_tuple(fills, "fills")
    if not fills:
        raise ContractError("at least one new fill is required")
    if snapshot.state in TERMINAL_ORDER_STATES:
        raise ContractError("terminal order states reject additional fills")
    _require_utc(observed_at, "observed_at")
    if observed_at < snapshot.observed_at or event_cursor <= snapshot.event_cursor:
        raise ContractError("order projection time and cursor must advance")
    combined = snapshot.fills + fills
    quantity = sum((fill.quantity for fill in combined), Decimal(0))
    next_state = (
        OrderStatus.FILLED if quantity == snapshot.intent.quantity else OrderStatus.PARTIALLY_FILLED
    )
    return replace(
        snapshot,
        observed_at=observed_at,
        state=next_state,
        fills=combined,
        event_cursor=event_cursor,
        created_at=observed_at,
    )


class PositionStatus(StrEnum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    position_id: PositionId
    run_ref: RunId
    instrument: InstrumentId
    as_of: datetime
    quantity: Decimal
    average_price: Decimal | None
    realized_pnl: Money
    unrealized_pnl: Money
    status: PositionStatus
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_decimal(self.quantity, "quantity")
        if self.average_price is not None:
            _require_decimal(self.average_price, "average_price", positive=True)
        currency = self.instrument.quote_currency
        if self.realized_pnl.currency != currency or self.unrealized_pnl.currency != currency:
            raise ContractError("position money must use the instrument quote currency")
        if self.status is PositionStatus.OPEN and (
            self.quantity == 0 or self.average_price is None
        ):
            raise ContractError("an open position requires quantity and average price")
        if self.status is not PositionStatus.OPEN and self.quantity != 0:
            raise ContractError("flat and closed positions must have zero quantity")
        if self.status is PositionStatus.FLAT and self.average_price is not None:
            raise ContractError("a flat position cannot have an average price")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: AccountId
    run_ref: RunId
    as_of: datetime
    balances: tuple[Money, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    synthetic: bool = False

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_tuple(self.balances, "balances")
        if self.synthetic is not False:
            raise ContractError("synthetic wallets do not exist in S2")
        if len({money.currency for money in self.balances}) != len(self.balances):
            raise ContractError("account balances must have unique currencies")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    portfolio_id: PortfolioId
    account_ref: AccountId
    run_ref: RunId
    as_of: datetime
    reporting_currency: str
    cash: tuple[Money, ...]
    positions: tuple[PositionSnapshot, ...]
    equity: tuple[Money, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        if not isinstance(self.reporting_currency, str) or not _CURRENCY.fullmatch(
            self.reporting_currency
        ):
            raise ContractError("reporting_currency must be an uppercase currency code")
        for name in ("cash", "positions", "equity"):
            _require_tuple(getattr(self, name), name)
        money = (
            self.cash
            + self.equity
            + tuple(
                item
                for position in self.positions
                for item in (position.realized_pnl, position.unrealized_pnl)
            )
        )
        if any(item.currency != self.reporting_currency for item in money):
            raise ContractError("all portfolio money must use the reporting currency")
        if any(
            position.run_ref != self.run_ref
            or position.instrument.quote_currency != self.reporting_currency
            or position.as_of > self.as_of
            for position in self.positions
        ):
            raise ContractError(
                "portfolio positions must share its run, time, and currency context"
            )
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


class RiskOutcome(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class RiskCheck:
    rule_code: str
    outcome: RiskOutcome
    evidence_refs: tuple[DomainRef, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.rule_code or not self.rule_code.strip():
            raise ContractError("risk rule_code must be non-empty")
        _require_tuple(self.evidence_refs, "risk check evidence_refs")
        if self.outcome is not RiskOutcome.NOT_EVALUATED and not self.evidence_refs:
            raise ContractError("evaluated risk checks require evidence")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_id: RiskId
    subject_ref: DomainRef
    as_of: datetime
    decision: RiskOutcome
    rule_results: tuple[RiskCheck, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    independent: bool = True

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_tuple(self.rule_results, "rule_results")
        _require_tuple(self.evidence_refs, "evidence_refs")
        if self.independent is not True:
            raise ContractError("risk decisions must remain independent")
        expected = RiskOutcome.NOT_EVALUATED
        if self.rule_results:
            if any(check.outcome is RiskOutcome.BLOCK for check in self.rule_results):
                expected = RiskOutcome.BLOCK
            elif all(check.outcome is RiskOutcome.PASS for check in self.rule_results):
                expected = RiskOutcome.PASS
        if self.decision is not expected:
            raise ContractError("risk decision must equal its independent rule outcomes")


class ApprovalState(StrEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    RESEARCH = "RESEARCH"
    VALIDATION = "VALIDATION"


class ApprovalDecision(StrEnum):
    NONE = "NONE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: ApprovalId
    strategy_version_ref: StrategyVersionId
    market: Market
    current_state: ApprovalState
    proposed_target: ApprovalState | None
    evidence_refs: tuple[DomainRef, ...]
    validation_refs: tuple[DomainRef, ...]
    risk_refs: tuple[RiskId, ...]
    decision: ApprovalDecision
    decided_by: DomainRef | None
    decided_at: datetime | None
    review_rule: str
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        for name in ("evidence_refs", "validation_refs", "risk_refs"):
            _require_tuple(getattr(self, name), name)
        if not self.review_rule or not self.review_rule.strip():
            raise ContractError("review_rule must be non-empty")
        decided = self.decision is not ApprovalDecision.NONE
        if decided != (self.decided_by is not None and self.decided_at is not None):
            raise ContractError("recorded decisions require both decider and UTC decision time")
        if self.decided_at is not None:
            _require_utc(self.decided_at, "decided_at")


class AnnotationKind(StrEnum):
    SIGNAL = "SIGNAL"
    FILL = "FILL"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True, slots=True)
class ChartAnnotation:
    annotation_id: AnnotationId
    chart_ref: str
    instrument: InstrumentId
    timeframe: Timeframe
    timestamp: datetime
    kind: AnnotationKind
    source_ref: DomainRef
    price: Decimal | None
    label: str | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.timestamp, "timestamp")
        if not self.chart_ref or not self.chart_ref.strip():
            raise ContractError("chart_ref must be non-empty")
        if self.price is not None:
            _require_decimal(self.price, "price", positive=True)
        expected_prefix = {
            AnnotationKind.SIGNAL: "SIG-",
            AnnotationKind.FILL: "FILL-",
            AnnotationKind.TAKE_PROFIT: "ORD-",
            AnnotationKind.STOP_LOSS: "ORD-",
        }[self.kind]
        if self.source_ref.prefix != expected_prefix:
            raise ContractError("annotation kind must match its retained typed source")
