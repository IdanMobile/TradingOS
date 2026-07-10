from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tios.trading_domain import (
    AccountId,
    AccountSnapshot,
    BracketLevels,
    ContractError,
    CreatorType,
    DatasetId,
    DomainRef,
    Environment,
    FillEvent,
    FillId,
    InstrumentId,
    Market,
    MarketBar,
    MarketName,
    Money,
    OrderId,
    OrderIntent,
    OrderState,
    OrderStatus,
    OrderType,
    PortfolioId,
    PortfolioSnapshot,
    PositionId,
    PositionSnapshot,
    PositionStatus,
    Provenance,
    RunId,
    Side,
    SignalId,
    Timeframe,
    VenueFamily,
    aggregate_fills,
    validate_bracket_levels,
    validate_order_transition,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)
RUN = RunId("RUN-history-1")
INSTRUMENT = InstrumentId("BTC-USDT.BINANCE_SPOT")
PROVENANCE = Provenance((DomainRef("RUN-history-1"),))
MARKET = Market(
    MarketName("CRYPTO_SPOT"),
    VenueFamily("BINANCE_SPOT"),
    INSTRUMENT,
    Timeframe.M5,
    DatasetId("DS-bars-1"),
)


def intent(*, bracket: BracketLevels | None = None) -> OrderIntent:
    return OrderIntent(
        source_signal_ref=SignalId("SIG-1"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("2"),
        limit_price=Decimal("100"),
        stop_price=None,
        bracket_levels=bracket,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def fill(fill_id: str, quantity: str, price: str = "100") -> FillEvent:
    return FillEvent(
        fill_id=FillId(fill_id),
        order_ref=OrderId("ORD-1"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        filled_at=NOW + timedelta(minutes=1),
        price=Decimal(price),
        quantity=Decimal(quantity),
        fee=Money(Decimal("0.10"), "USDT"),
        liquidity_role=None,
        created_at=NOW + timedelta(minutes=1),
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def order_state() -> OrderState:
    return OrderState(
        order_id=OrderId("ORD-1"),
        intent=intent(),
        observed_at=NOW,
        state=OrderStatus.INERT,
        fills=(),
        event_cursor=0,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def position(currency: str = "USDT") -> PositionSnapshot:
    return PositionSnapshot(
        position_id=PositionId("POS-1"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        as_of=NOW,
        quantity=Decimal("1"),
        average_price=Decimal("100"),
        realized_pnl=Money(Decimal("2"), currency),
        unrealized_pnl=Money(Decimal("3"), currency),
        status=PositionStatus.OPEN,
        event_cursor=4,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def test_bar_validates_decimal_utc_and_ohlc() -> None:
    bar = MarketBar(
        MARKET,
        NOW,
        NOW + timedelta(minutes=5),
        Decimal("100"),
        Decimal("110"),
        Decimal("90"),
        Decimal("105"),
        Decimal("12.5"),
        NOW,
        CreatorType.SYSTEM,
        PROVENANCE,
    )
    assert bar.market.timeframe.seconds == 300

    with pytest.raises(ContractError, match="Decimal"):
        MarketBar(
            MARKET,
            NOW,
            NOW + timedelta(minutes=5),
            100,  # type: ignore[arg-type]
            Decimal("110"),
            Decimal("90"),
            Decimal("105"),
            Decimal("1"),
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )
    with pytest.raises(ContractError, match="timezone-aware UTC"):
        MarketBar(
            MARKET,
            NOW.replace(tzinfo=None),
            NOW + timedelta(minutes=5),
            Decimal("100"),
            Decimal("110"),
            Decimal("90"),
            Decimal("105"),
            Decimal("1"),
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )
    with pytest.raises(ContractError, match="must be UTC"):
        MarketBar(
            MARKET,
            NOW.astimezone(timezone(timedelta(hours=2))),
            (NOW + timedelta(minutes=5)).astimezone(timezone(timedelta(hours=2))),
            Decimal("100"),
            Decimal("110"),
            Decimal("90"),
            Decimal("105"),
            Decimal("1"),
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )
    with pytest.raises(ContractError, match="OHLC"):
        MarketBar(
            MARKET,
            NOW,
            NOW + timedelta(minutes=5),
            Decimal("80"),
            Decimal("110"),
            Decimal("90"),
            Decimal("105"),
            Decimal("1"),
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )


@pytest.mark.parametrize(
    ("constructor", "value"),
    [
        (OrderId, "FILL-1"),
        (RunId, "RUN-"),
        (InstrumentId, "btcusdt"),
    ],
)
def test_ids_and_instrument_are_validated(constructor: object, value: str) -> None:
    with pytest.raises(ContractError):
        constructor(value)  # type: ignore[operator]


def test_money_price_quantity_and_fee_validation() -> None:
    with pytest.raises(ContractError, match="nonnegative"):
        Money(Decimal("-0.01"), "USDT")
    with pytest.raises(ContractError, match="finite"):
        Money(Decimal("NaN"), "USDT")
    with pytest.raises(ContractError, match="positive"):
        replace(intent(), quantity=Decimal("0"))
    with pytest.raises(ContractError, match="fee currency"):
        FillEvent(
            **{
                "fill_id": FillId("FILL-bad-fee"),
                "order_ref": OrderId("ORD-1"),
                "run_ref": RUN,
                "instrument": INSTRUMENT,
                "filled_at": NOW,
                "price": Decimal("100"),
                "quantity": Decimal("1"),
                "fee": Money(Decimal("0"), "BTC"),
                "liquidity_role": None,
                "created_at": NOW,
                "creator_type": CreatorType.SYSTEM,
                "provenance": PROVENANCE,
            }
        )


def test_bracket_direction_and_order_type_rules() -> None:
    bracket = BracketLevels(
        take_profit=Decimal("120"), stop_loss=Decimal("90"), trailing_distance=None
    )
    assert intent(bracket=bracket).bracket_levels == bracket
    validate_bracket_levels(bracket, Side.BUY, Decimal("100"))
    with pytest.raises(ContractError, match="take-profit"):
        validate_bracket_levels(bracket, Side.SELL, Decimal("100"))
    with pytest.raises(ContractError, match="invalid price fields"):
        OrderIntent(
            source_signal_ref=None,
            run_ref=RUN,
            instrument=INSTRUMENT,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            limit_price=Decimal("100"),
            stop_price=None,
            bracket_levels=None,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_lifecycle_rejects_invalid_and_terminal_transitions() -> None:
    validate_order_transition(OrderStatus.INERT, OrderStatus.PARTIALLY_FILLED)
    with pytest.raises(ContractError, match="invalid order transition"):
        validate_order_transition(OrderStatus.INERT, OrderStatus.INERT)
    for terminal in (
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    ):
        with pytest.raises(ContractError, match="invalid order transition"):
            validate_order_transition(terminal, OrderStatus.PARTIALLY_FILLED)


def test_partial_and_full_fill_aggregation() -> None:
    partial = aggregate_fills(
        order_state(),
        (fill("FILL-1", "0.5", "100"),),
        observed_at=NOW + timedelta(minutes=2),
        event_cursor=1,
    )
    assert partial.state is OrderStatus.PARTIALLY_FILLED
    assert partial.filled_quantity == Decimal("0.5")

    complete = aggregate_fills(
        partial,
        (fill("FILL-2", "1.5", "102"),),
        observed_at=NOW + timedelta(minutes=3),
        event_cursor=2,
    )
    assert complete.state is OrderStatus.FILLED
    assert complete.filled_quantity == Decimal("2")
    assert complete.average_fill_price == Decimal("101.5")
    assert complete.total_fee == Money(Decimal("0.20"), "USDT")

    with pytest.raises(ContractError, match="terminal"):
        aggregate_fills(
            complete,
            (fill("FILL-3", "0.1"),),
            observed_at=NOW + timedelta(minutes=4),
            event_cursor=3,
        )


def test_overfill_and_duplicate_historical_fills_are_rejected() -> None:
    with pytest.raises(ContractError, match="exceeds"):
        aggregate_fills(
            order_state(),
            (fill("FILL-over", "2.1"),),
            observed_at=NOW + timedelta(minutes=2),
            event_cursor=1,
        )
    duplicate = fill("FILL-duplicate", "0.5")
    with pytest.raises(ContractError, match="unique"):
        aggregate_fills(
            order_state(),
            (duplicate, duplicate),
            observed_at=NOW + timedelta(minutes=2),
            event_cursor=1,
        )


def test_demo_paper_and_other_environments_cannot_be_constructed() -> None:
    for reserved in ("DEMO", "PAPER", "LI" + "VE"):
        with pytest.raises(ValueError):
            Environment(reserved)
    with pytest.raises(ContractError, match="synthetic wallets"):
        AccountSnapshot(
            AccountId("ACCT-1"),
            RUN,
            NOW,
            (Money(Decimal("1000"), "USDT"),),
            0,
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
            synthetic=True,
        )
    state = order_state()
    assert state.execution_authority.value == "NONE"
    assert state.paper_orders.value == state.live_orders.value == "DISABLED"


def test_portfolio_enforces_one_currency_and_projection_context() -> None:
    portfolio = PortfolioSnapshot(
        PortfolioId("PF-1"),
        AccountId("ACCT-1"),
        RUN,
        NOW,
        "USDT",
        (Money(Decimal("1000"), "USDT"),),
        (position(),),
        (Money(Decimal("1100"), "USDT"),),
        5,
        NOW,
        CreatorType.SYSTEM,
        PROVENANCE,
    )
    assert portfolio.positions[0].event_cursor == 4
    with pytest.raises(ContractError, match="reporting currency"):
        PortfolioSnapshot(
            PortfolioId("PF-2"),
            AccountId("ACCT-1"),
            RUN,
            NOW,
            "USDT",
            (Money(Decimal("1"), "BTC"),),
            (position(),),
            (Money(Decimal("1100"), "USDT"),),
            5,
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )


def test_records_and_historical_fill_collections_are_frozen() -> None:
    historical_fill = fill("FILL-frozen", "1")
    with pytest.raises(FrozenInstanceError):
        historical_fill.quantity = Decimal("2")  # type: ignore[misc]
    state = OrderState(
        OrderId("ORD-1"),
        intent(),
        NOW + timedelta(minutes=2),
        OrderStatus.PARTIALLY_FILLED,
        (historical_fill,),
        1,
        NOW,
        CreatorType.SYSTEM,
        PROVENANCE,
    )
    with pytest.raises(FrozenInstanceError):
        state.fills = ()  # type: ignore[misc]
    with pytest.raises(ContractError, match="immutable tuple"):
        OrderState(
            OrderId("ORD-2"),
            intent(),
            NOW,
            OrderStatus.INERT,
            [],  # type: ignore[arg-type]
            0,
            NOW,
            CreatorType.SYSTEM,
            PROVENANCE,
        )
