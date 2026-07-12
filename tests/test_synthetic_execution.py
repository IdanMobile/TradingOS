from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.trading_domain import (
    AccountId,
    ApprovalId,
    ContractError,
    CreatorType,
    DatasetId,
    DomainRef,
    FillEvent,
    FillId,
    InstrumentId,
    LedgerDirection,
    LedgerId,
    LiquidityRole,
    Market,
    MarketBar,
    MarketName,
    Money,
    OrderId,
    OrderIntent,
    OrderType,
    PaperFeeModel,
    PaperFillPriceSource,
    PortfolioId,
    PositionId,
    PositionStatus,
    Provenance,
    RunId,
    Side,
    SignalId,
    SignedMoney,
    Stage,
    SyntheticExecutedFill,
    SyntheticFillStatus,
    SyntheticLedgerEntryKind,
    SyntheticPaperFillPolicy,
    Timeframe,
    VenueFamily,
    apply_synthetic_ledger_change,
    calculate_synthetic_fill,
    initialize_synthetic_ledger,
    project_synthetic_portfolio,
    project_synthetic_spot_position,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
RUN = RunId("RUN-synthetic-probe")
INSTRUMENT = InstrumentId("BTC-USDT.BINANCE_SPOT")
EVIDENCE = (DomainRef("EV-synthetic-execution"),)
PROVENANCE = Provenance(EVIDENCE)
MARKET = Market(
    MarketName("CRYPTO_SPOT"),
    VenueFamily("BINANCE_SPOT"),
    INSTRUMENT,
    Timeframe.M5,
    DatasetId("DS-synthetic-probe"),
)


def policy(source: PaperFillPriceSource = PaperFillPriceSource.BAR_MIDPOINT):
    return SyntheticPaperFillPolicy(
        policy_id=ApprovalId("APR-synthetic-fill-policy"),
        stage=Stage.S3_PAPER_DEMO,
        price_source=source,
        fee_model=PaperFeeModel.FIXED_BPS,
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("20"),
        slippage_bps=Decimal("2"),
        max_fill_latency_seconds=60,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def intent(
    side: Side = Side.BUY,
    order_type: OrderType = OrderType.MARKET,
    limit: Decimal | None = None,
    stop: Decimal | None = None,
) -> OrderIntent:
    return OrderIntent(
        source_signal_ref=SignalId("SIG-synthetic-probe"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        side=side,
        order_type=order_type,
        quantity=Decimal("2"),
        limit_price=limit,
        stop_price=stop,
        bracket_levels=None,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def bar(low: str = "90", high: str = "110", close: str = "100") -> MarketBar:
    return MarketBar(
        market=MARKET,
        open_time=NOW,
        close_time=NOW + timedelta(minutes=5),
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def fill(
    fill_id: str, side: Side, price: str, quantity: str, fee: str, minute: int
) -> SyntheticExecutedFill:
    order_intent = replace(intent(side=side), quantity=Decimal(quantity))
    event = FillEvent(
        fill_id=FillId(fill_id),
        order_ref=OrderId(f"ORD-{fill_id[5:]}"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        filled_at=NOW + timedelta(minutes=minute),
        price=Decimal(price),
        quantity=Decimal(quantity),
        fee=Money(Decimal(fee), "USDT"),
        liquidity_role=LiquidityRole.TAKER,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    return SyntheticExecutedFill(order_intent, event)


def test_calculate_synthetic_fill_applies_adverse_slippage_and_fee() -> None:
    result = calculate_synthetic_fill(intent=intent(), policy=policy(), bar=bar())
    assert result.status is SyntheticFillStatus.FILLED
    assert result.price == Decimal("100.0200")
    assert result.notional == Money(Decimal("200.0400"), "USDT")
    assert result.fee == Money(Decimal("0.4000800"), "USDT")
    assert result.liquidity_role is LiquidityRole.TAKER

    not_reached = calculate_synthetic_fill(
        intent=intent(order_type=OrderType.LIMIT, limit=Decimal("80")),
        policy=policy(),
        bar=bar(),
    )
    assert not_reached.status is SyntheticFillStatus.LIMIT_NOT_REACHED
    assert not_reached.price is None

    not_triggered = calculate_synthetic_fill(
        intent=intent(order_type=OrderType.STOP, stop=Decimal("120")),
        policy=policy(),
        bar=bar(),
    )
    assert not_triggered.status is SyntheticFillStatus.NOT_TRIGGERED


def test_synthetic_ledger_reducer_is_conservative_and_idempotent() -> None:
    ledger = initialize_synthetic_ledger(
        ledger_id=LedgerId("LEDGER-synthetic-reducer"),
        entry_id=ApprovalId("APR-ledger-initial"),
        initial_capital=Money(Decimal("1000"), "USDT"),
        occurred_at=NOW,
        source_ref=DomainRef("APR-paper-probe"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    changed = apply_synthetic_ledger_change(
        ledger,
        entry_id=ApprovalId("APR-ledger-fee"),
        occurred_at=NOW + timedelta(minutes=1),
        kind=SyntheticLedgerEntryKind.FEE,
        direction=LedgerDirection.DEBIT,
        amount=Money(Decimal("1"), "USDT"),
        source_ref=DomainRef("FILL-synthetic-probe"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert changed.balances == (Money(Decimal("999"), "USDT"),)
    replay = apply_synthetic_ledger_change(
        changed,
        entry_id=ApprovalId("APR-ledger-fee"),
        occurred_at=NOW + timedelta(minutes=1),
        kind=SyntheticLedgerEntryKind.FEE,
        direction=LedgerDirection.DEBIT,
        amount=Money(Decimal("1"), "USDT"),
        source_ref=DomainRef("FILL-synthetic-probe"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert replay is changed
    with pytest.raises(ContractError, match="idempotency key conflicts"):
        apply_synthetic_ledger_change(
            changed,
            entry_id=ApprovalId("APR-ledger-fee"),
            occurred_at=NOW + timedelta(minutes=1),
            kind=SyntheticLedgerEntryKind.FEE,
            direction=LedgerDirection.DEBIT,
            amount=Money(Decimal("2"), "USDT"),
            source_ref=DomainRef("FILL-synthetic-probe"),
            evidence_refs=EVIDENCE,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="overdraw"):
        apply_synthetic_ledger_change(
            changed,
            entry_id=ApprovalId("APR-ledger-overdraw"),
            occurred_at=NOW + timedelta(minutes=2),
            kind=SyntheticLedgerEntryKind.FILL_SETTLEMENT,
            direction=LedgerDirection.DEBIT,
            amount=Money(Decimal("1000"), "USDT"),
            source_ref=DomainRef("FILL-synthetic-overdraw"),
            evidence_refs=EVIDENCE,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_project_synthetic_spot_position_tracks_cost_basis_and_pnl() -> None:
    opened = project_synthetic_spot_position(
        position_id=PositionId("POS-synthetic"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        executions=(fill("FILL-buy", Side.BUY, "100", "2", "2", 1),),
        mark_price=Decimal("110"),
        as_of=NOW + timedelta(minutes=2),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert opened.status is PositionStatus.OPEN
    assert opened.quantity == Decimal("2")
    assert opened.average_price == Decimal("101")
    assert opened.unrealized_pnl == SignedMoney(Decimal("18"), "USDT")

    losing = project_synthetic_spot_position(
        position_id=PositionId("POS-synthetic-loss"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        executions=(fill("FILL-buy-loss", Side.BUY, "100", "2", "2", 1),),
        mark_price=Decimal("90"),
        as_of=NOW + timedelta(minutes=2),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert losing.unrealized_pnl == SignedMoney(Decimal("-22"), "USDT")

    closed = project_synthetic_spot_position(
        position_id=PositionId("POS-synthetic"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        executions=(
            fill("FILL-buy", Side.BUY, "100", "2", "2", 1),
            fill("FILL-sell", Side.SELL, "110", "2", "2", 2),
        ),
        mark_price=Decimal("110"),
        as_of=NOW + timedelta(minutes=3),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert closed.status is PositionStatus.CLOSED
    assert closed.quantity == 0
    assert closed.realized_pnl == SignedMoney(Decimal("16"), "USDT")
    losing_closed = project_synthetic_spot_position(
        position_id=PositionId("POS-synthetic-closed-loss"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        executions=(
            fill("FILL-buy-loss", Side.BUY, "100", "2", "2", 1),
            fill("FILL-sell-loss", Side.SELL, "90", "2", "2", 2),
        ),
        mark_price=Decimal("90"),
        as_of=NOW + timedelta(minutes=3),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert losing_closed.realized_pnl == SignedMoney(Decimal("-24"), "USDT")
    with pytest.raises(ContractError, match="sell more"):
        project_synthetic_spot_position(
            position_id=PositionId("POS-synthetic-short"),
            run_ref=RUN,
            instrument=INSTRUMENT,
            executions=(fill("FILL-sell", Side.SELL, "110", "1", "1", 1),),
            mark_price=Decimal("110"),
            as_of=NOW + timedelta(minutes=2),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_project_synthetic_portfolio_reconciles_ledger_cash_and_marks() -> None:
    ledger = initialize_synthetic_ledger(
        ledger_id=LedgerId("LEDGER-synthetic-portfolio"),
        entry_id=ApprovalId("APR-ledger-portfolio-initial"),
        initial_capital=Money(Decimal("1000"), "USDT"),
        occurred_at=NOW,
        source_ref=DomainRef("APR-paper-probe"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ledger = apply_synthetic_ledger_change(
        ledger,
        entry_id=ApprovalId("APR-ledger-buy-settlement"),
        occurred_at=NOW + timedelta(minutes=1),
        kind=SyntheticLedgerEntryKind.FILL_SETTLEMENT,
        direction=LedgerDirection.DEBIT,
        amount=Money(Decimal("202"), "USDT"),
        source_ref=DomainRef("FILL-buy"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    position = project_synthetic_spot_position(
        position_id=PositionId("POS-synthetic-portfolio"),
        run_ref=RUN,
        instrument=INSTRUMENT,
        executions=(fill("FILL-buy", Side.BUY, "100", "2", "2", 1),),
        mark_price=Decimal("110"),
        as_of=NOW + timedelta(minutes=2),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    projection = project_synthetic_portfolio(
        account_id=AccountId("ACCT-synthetic-portfolio"),
        portfolio_id=PortfolioId("PF-synthetic-portfolio"),
        ledger=ledger,
        positions=(position,),
        marks={INSTRUMENT: Decimal("110")},
        reporting_currency="USDT",
        as_of=NOW + timedelta(minutes=2),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
        evidence_refs=EVIDENCE,
    )
    assert projection.account.balances == (Money(Decimal("798"), "USDT"),)
    assert projection.portfolio.cash == (Money(Decimal("798"), "USDT"),)
    assert projection.portfolio.equity == (Money(Decimal("1018"), "USDT"),)
    with pytest.raises(ContractError, match="unrealized P&L"):
        project_synthetic_portfolio(
            account_id=AccountId("ACCT-synthetic-portfolio-bad"),
            portfolio_id=PortfolioId("PF-synthetic-portfolio-bad"),
            ledger=ledger,
            positions=(position,),
            marks={INSTRUMENT: Decimal("109")},
            reporting_currency="USDT",
            as_of=NOW + timedelta(minutes=2),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            evidence_refs=EVIDENCE,
        )
