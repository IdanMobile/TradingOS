from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tios.trading_domain import (
    AccountId,
    AccountSnapshot,
    ApprovalId,
    BracketLevels,
    ContractError,
    CreatorType,
    CredentialPermission,
    DatasetId,
    DivergenceMetric,
    DivergenceObservation,
    DivergenceStatus,
    DomainRef,
    Environment,
    FillEvent,
    FillId,
    InstrumentId,
    KillSwitchMode,
    LedgerDirection,
    LedgerId,
    LimitedLiveRiskPackage,
    LimitedLiveRiskPackageStatus,
    LiveOperationsEventKind,
    LiveOperationsEventRecord,
    LiveOperationsEventSeverity,
    LiveOperationsRunbook,
    LiveReadinessProposal,
    LiveRunbookEscalationMode,
    Market,
    MarketBar,
    MarketName,
    Money,
    OperationalDrillKind,
    OperationalDrillRecord,
    OperationalDrillStatus,
    OrderId,
    OrderIntent,
    OrderState,
    OrderStatus,
    OrderType,
    PaperDivergenceReport,
    PaperFeeModel,
    PaperFillPriceSource,
    PaperLaneMode,
    PaperLaneProposal,
    PaperOperationsEventKind,
    PaperOperationsEventRecord,
    PaperOperationsEventSeverity,
    PaperOperationsRunbook,
    PaperRunbookInterventionMode,
    PaperStabilityReport,
    PaperStabilityStatus,
    PortfolioId,
    PortfolioSnapshot,
    PositionId,
    PositionSnapshot,
    PositionStatus,
    Provenance,
    RestrictedCredentialPolicy,
    RiskId,
    RunId,
    Side,
    SignalId,
    SignedMoney,
    Stage,
    StageGateId,
    StageGateReadinessRecord,
    StageGateRequirement,
    StageGateRequirementKind,
    StageGateStatus,
    SyntheticAccountSnapshot,
    SyntheticLedgerEntry,
    SyntheticLedgerEntryKind,
    SyntheticLedgerSnapshot,
    SyntheticMarketConditionPolicy,
    SyntheticPaperFillPolicy,
    SyntheticPortfolioRiskPolicy,
    SyntheticPortfolioSnapshot,
    SyntheticRuntimeRiskPolicy,
    SyntheticStrategyBudgetPolicy,
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
        realized_pnl=SignedMoney(Decimal("2"), currency),
        unrealized_pnl=SignedMoney(Decimal("3"), currency),
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
    assert SignedMoney(Decimal("-10.5"), "USDT").amount == Decimal("-10.5")
    with pytest.raises(ContractError, match="finite"):
        SignedMoney(Decimal("NaN"), "USDT")
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


def requirement(
    code: str,
    *,
    satisfied: bool,
    kind: StageGateRequirementKind = StageGateRequirementKind.EVIDENCE,
    evidence_ref: str = "EV-1",
    blocker: str = "not ready",
) -> StageGateRequirement:
    return StageGateRequirement(
        code=code,
        kind=kind,
        satisfied=satisfied,
        evidence_refs=(DomainRef(evidence_ref),) if satisfied else (),
        blocker=None if satisfied else blocker,
    )


def s3_requirements(
    *, s2_exit_satisfied: bool, human_satisfied: bool
) -> tuple[StageGateRequirement, ...]:
    return (
        requirement("S2_EXIT_PASS", satisfied=s2_exit_satisfied),
        requirement(
            "HG_3_APPROVED",
            satisfied=human_satisfied,
            kind=StageGateRequirementKind.HUMAN_DECISION,
            evidence_ref="APR-human-s3",
        ),
        requirement("COMPLETE_APPROVABLE_STRATEGY_CONTEXT", satisfied=s2_exit_satisfied),
        requirement(
            "PAPER_LANE_ARCHITECTURE_DECISION",
            satisfied=human_satisfied,
            kind=StageGateRequirementKind.HUMAN_DECISION,
            evidence_ref="APR-paper-architecture",
        ),
        requirement("SECURITY_REVIEW_PASS", satisfied=s2_exit_satisfied),
        requirement(
            "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL",
            satisfied=human_satisfied,
            kind=StageGateRequirementKind.HUMAN_DECISION,
            evidence_ref="APR-specific-integration",
        ),
    )


def test_s3_stage_gate_readiness_can_be_modeled_without_activation() -> None:
    blocked = StageGateReadinessRecord(
        gate_id=StageGateId("GATE-S3-1"),
        stage=Stage.S3_PAPER_DEMO,
        subject_ref=DomainRef("SV-candidate-1"),
        requirements=s3_requirements(s2_exit_satisfied=False, human_satisfied=False),
        status=StageGateStatus.BLOCKED,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert blocked.execution_authority.value == "NONE"
    assert blocked.paper_orders.value == "DISABLED"
    assert blocked.live_orders.value == "DISABLED"

    ready = StageGateReadinessRecord(
        gate_id=StageGateId("GATE-S3-2"),
        stage=Stage.S3_PAPER_DEMO,
        subject_ref=DomainRef("SV-candidate-1"),
        requirements=s3_requirements(s2_exit_satisfied=True, human_satisfied=False),
        status=StageGateStatus.READY_FOR_OPERATOR_DECISION,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert ready.status is StageGateStatus.READY_FOR_OPERATOR_DECISION

    with pytest.raises(ContractError, match="non-human evidence"):
        StageGateReadinessRecord(
            gate_id=StageGateId("GATE-S3-3"),
            stage=Stage.S3_PAPER_DEMO,
            subject_ref=DomainRef("SV-candidate-1"),
            requirements=s3_requirements(s2_exit_satisfied=False, human_satisfied=False),
            status=StageGateStatus.READY_FOR_OPERATOR_DECISION,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="APR evidence"):
        requirement(
            "HG_3_APPROVED",
            satisfied=True,
            kind=StageGateRequirementKind.HUMAN_DECISION,
            evidence_ref="EV-not-human-approval",
        )

    with pytest.raises(ContractError, match="missing required prerequisites"):
        StageGateReadinessRecord(
            gate_id=StageGateId("GATE-S4-incomplete"),
            stage=Stage.S4_LIVE,
            subject_ref=DomainRef("APR-paper-context-1"),
            requirements=(
                requirement("S3_EXIT_PASS", satisfied=False),
                requirement(
                    "HG_5_OPERATOR_APPROVAL",
                    satisfied=False,
                    kind=StageGateRequirementKind.HUMAN_DECISION,
                ),
            ),
            status=StageGateStatus.BLOCKED,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_paper_and_live_proposals_are_inert_control_plane_records() -> None:
    paper = PaperLaneProposal(
        proposal_id=ApprovalId("APR-paper-1"),
        strategy_context_ref=DomainRef("SV-candidate-1"),
        mode=PaperLaneMode.SYNTHETIC_LOCAL_SIMULATOR,
        gate_ref=StageGateId("GATE-S3-1"),
        requested_synthetic_capital=Money(Decimal("10000"), "USDT"),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert paper.execution_authority.value == "NONE"
    assert paper.paper_orders.value == paper.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="credential gate"):
        PaperLaneProposal(
            proposal_id=ApprovalId("APR-paper-2"),
            strategy_context_ref=DomainRef("SV-candidate-1"),
            mode=PaperLaneMode.VENUE_DEMO_OR_TESTNET,
            gate_ref=StageGateId("GATE-S3-1"),
            requested_synthetic_capital=Money(Decimal("10000"), "USDT"),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )

    live = LiveReadinessProposal(
        proposal_id=ApprovalId("APR-live-1"),
        paper_context_ref=DomainRef("APR-paper-1"),
        gate_ref=StageGateId("GATE-S4-1"),
        maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
        maximum_drawdown_fraction=Decimal("0.05"),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert live.execution_authority.value == "NONE"
    assert live.live_orders.value == "DISABLED"
    with pytest.raises(ContractError, match="fraction below 1"):
        LiveReadinessProposal(
            proposal_id=ApprovalId("APR-live-2"),
            paper_context_ref=DomainRef("APR-paper-1"),
            gate_ref=StageGateId("GATE-S4-1"),
            maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
            maximum_drawdown_fraction=Decimal("1"),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_paper_divergence_report_classifies_tolerance_without_activation() -> None:
    within = DivergenceObservation(
        metric=DivergenceMetric.TOTAL_RETURN,
        backtest_value=Decimal("0.10"),
        paper_value=Decimal("0.095"),
        tolerance=Decimal("0.01"),
    )
    outside = DivergenceObservation(
        metric=DivergenceMetric.FEE_TOTAL,
        backtest_value=Decimal("10"),
        paper_value=Decimal("15"),
        tolerance=Decimal("1"),
    )
    assert within.absolute_difference == Decimal("0.005")
    assert within.status is DivergenceStatus.WITHIN_TOLERANCE
    assert outside.status is DivergenceStatus.OUTSIDE_TOLERANCE

    report = PaperDivergenceReport(
        report_id=ApprovalId("APR-divergence-1"),
        strategy_context_ref=DomainRef("SV-candidate-1"),
        backtest_run_ref=RUN,
        paper_context_ref=DomainRef("APR-paper-1"),
        observations=(within, outside),
        evidence_refs=(DomainRef("EV-divergence-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert report.status is DivergenceStatus.OUTSIDE_TOLERANCE
    assert report.execution_authority.value == "NONE"
    assert report.paper_orders.value == report.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="unique"):
        PaperDivergenceReport(
            report_id=ApprovalId("APR-divergence-2"),
            strategy_context_ref=DomainRef("SV-candidate-1"),
            backtest_run_ref=RUN,
            paper_context_ref=DomainRef("APR-paper-1"),
            observations=(within, within),
            evidence_refs=(DomainRef("EV-divergence-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="evidence"):
        PaperDivergenceReport(
            report_id=ApprovalId("APR-divergence-3"),
            strategy_context_ref=DomainRef("SV-candidate-1"),
            backtest_run_ref=RUN,
            paper_context_ref=DomainRef("APR-paper-1"),
            observations=(within,),
            evidence_refs=(),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_operational_drill_records_are_evidence_only() -> None:
    passed = OperationalDrillRecord(
        drill_id=ApprovalId("APR-drill-1"),
        stage=Stage.S3_PAPER_DEMO,
        kind=OperationalDrillKind.MANUAL_KILL_SWITCH,
        status=OperationalDrillStatus.PASS,
        evidence_refs=(DomainRef("EV-drill-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert passed.execution_authority.value == "NONE"
    assert passed.paper_orders.value == passed.live_orders.value == "DISABLED"

    blocked = OperationalDrillRecord(
        drill_id=ApprovalId("APR-drill-2"),
        stage=Stage.S4_LIVE,
        kind=OperationalDrillKind.CREDENTIAL_REVOCATION,
        status=OperationalDrillStatus.BLOCKED,
        evidence_refs=(),
        blocker="no restricted credential exists",
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert blocked.blocker == "no restricted credential exists"
    with pytest.raises(ContractError, match="require evidence"):
        OperationalDrillRecord(
            drill_id=ApprovalId("APR-drill-3"),
            stage=Stage.S3_PAPER_DEMO,
            kind=OperationalDrillKind.FEED_LOSS,
            status=OperationalDrillStatus.PASS,
            evidence_refs=(),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot carry evidence"):
        OperationalDrillRecord(
            drill_id=ApprovalId("APR-drill-4"),
            stage=Stage.S3_PAPER_DEMO,
            kind=OperationalDrillKind.STALE_DATA,
            status=OperationalDrillStatus.NOT_RUN,
            evidence_refs=(DomainRef("EV-drill-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_synthetic_ledger_models_mock_money_without_activation() -> None:
    initial = SyntheticLedgerEntry(
        entry_id=ApprovalId("APR-ledger-entry-1"),
        occurred_at=NOW,
        kind=SyntheticLedgerEntryKind.INITIAL_CAPITAL,
        direction=LedgerDirection.CREDIT,
        amount=Money(Decimal("10000"), "USDT"),
        balance_after=Money(Decimal("10000"), "USDT"),
        source_ref=DomainRef("APR-PAPER-LANE-PROBE"),
        evidence_refs=(DomainRef("EV-ledger-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    fee = SyntheticLedgerEntry(
        entry_id=ApprovalId("APR-ledger-entry-2"),
        occurred_at=NOW + timedelta(minutes=1),
        kind=SyntheticLedgerEntryKind.FEE,
        direction=LedgerDirection.DEBIT,
        amount=Money(Decimal("1"), "USDT"),
        balance_after=Money(Decimal("9999"), "USDT"),
        source_ref=DomainRef("FILL-1"),
        evidence_refs=(DomainRef("EV-ledger-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    snapshot = SyntheticLedgerSnapshot(
        ledger_id=LedgerId("LEDGER-demo-probe-1"),
        stage=Stage.S3_PAPER_DEMO,
        as_of=NOW + timedelta(minutes=2),
        entries=(initial, fee),
        balances=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-ledger-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert snapshot.synthetic is True
    assert snapshot.real_money is False
    assert snapshot.execution_authority.value == "NONE"
    assert snapshot.paper_orders.value == snapshot.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="balance transition is inconsistent"):
        replace(
            snapshot,
            ledger_id=LedgerId("LEDGER-demo-probe-inconsistent"),
            entries=(initial, replace(fee, balance_after=Money(Decimal("9998"), "USDT"))),
            balances=(Money(Decimal("9998"), "USDT"),),
        )
    with pytest.raises(ContractError, match="cannot overdraw"):
        replace(
            snapshot,
            ledger_id=LedgerId("LEDGER-demo-probe-overdraw"),
            entries=(
                initial,
                replace(
                    fee,
                    amount=Money(Decimal("10001"), "USDT"),
                    balance_after=Money(Decimal("0"), "USDT"),
                ),
            ),
            balances=(Money(Decimal("0"), "USDT"),),
        )
    with pytest.raises(ContractError, match="begin with credited initial capital"):
        replace(
            snapshot,
            ledger_id=LedgerId("LEDGER-demo-probe-no-initial"),
            entries=(fee,),
            balances=(Money(Decimal("9999"), "USDT"),),
        )

    with pytest.raises(ContractError, match="latest entry balances"):
        SyntheticLedgerSnapshot(
            ledger_id=LedgerId("LEDGER-demo-probe-2"),
            stage=Stage.S3_PAPER_DEMO,
            as_of=NOW + timedelta(minutes=2),
            entries=(initial, fee),
            balances=(Money(Decimal("10000"), "USDT"),),
            evidence_refs=(DomainRef("EV-ledger-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="non-real-money"):
        SyntheticLedgerSnapshot(
            ledger_id=LedgerId("LEDGER-demo-probe-3"),
            stage=Stage.S3_PAPER_DEMO,
            as_of=NOW,
            entries=(initial,),
            balances=(Money(Decimal("10000"), "USDT"),),
            evidence_refs=(DomainRef("EV-ledger-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            real_money=True,
        )


def test_synthetic_paper_fill_policy_is_inert_and_mock_only() -> None:
    policy = SyntheticPaperFillPolicy(
        policy_id=ApprovalId("APR-fill-policy-1"),
        stage=Stage.S3_PAPER_DEMO,
        price_source=PaperFillPriceSource.BAR_MIDPOINT,
        fee_model=PaperFeeModel.FIXED_BPS,
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("20"),
        slippage_bps=Decimal("2"),
        max_fill_latency_seconds=60,
        evidence_refs=(DomainRef("EV-fill-policy-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert policy.synthetic is True
    assert policy.real_money is False
    assert policy.execution_authority.value == "NONE"
    assert policy.paper_orders.value == policy.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S3"):
        SyntheticPaperFillPolicy(
            policy_id=ApprovalId("APR-fill-policy-2"),
            stage=Stage.S4_LIVE,
            price_source=PaperFillPriceSource.BAR_CLOSE,
            fee_model=PaperFeeModel.FIXED_BPS,
            maker_fee_bps=Decimal("10"),
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("0"),
            max_fill_latency_seconds=0,
            evidence_refs=(DomainRef("EV-fill-policy-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        SyntheticPaperFillPolicy(
            policy_id=ApprovalId("APR-fill-policy-3"),
            stage=Stage.S3_PAPER_DEMO,
            price_source=PaperFillPriceSource.QUOTE_MIDPOINT,
            fee_model=PaperFeeModel.FIXED_BPS,
            maker_fee_bps=Decimal("10"),
            taker_fee_bps=Decimal("10"),
            slippage_bps=Decimal("0"),
            max_fill_latency_seconds=0,
            evidence_refs=(DomainRef("EV-fill-policy-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_synthetic_account_and_portfolio_snapshots_are_inert_mock_money() -> None:
    account = SyntheticAccountSnapshot(
        account_id=AccountId("ACCT-demo-probe-1"),
        ledger_ref=LedgerId("LEDGER-demo-probe-1"),
        stage=Stage.S3_PAPER_DEMO,
        as_of=NOW,
        balances=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-account-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    portfolio = SyntheticPortfolioSnapshot(
        portfolio_id=PortfolioId("PF-demo-probe-1"),
        account_ref=account.account_id,
        ledger_ref=account.ledger_ref,
        stage=Stage.S3_PAPER_DEMO,
        as_of=NOW,
        reporting_currency="USDT",
        cash=(Money(Decimal("9999"), "USDT"),),
        positions=(),
        equity=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-account-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert account.synthetic is True
    assert portfolio.synthetic is True
    assert account.real_money is False
    assert portfolio.real_money is False
    assert account.execution_authority.value == portfolio.execution_authority.value == "NONE"
    assert account.paper_orders.value == portfolio.paper_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="non-real-money"):
        SyntheticAccountSnapshot(
            account_id=AccountId("ACCT-demo-probe-2"),
            ledger_ref=LedgerId("LEDGER-demo-probe-1"),
            stage=Stage.S3_PAPER_DEMO,
            as_of=NOW,
            balances=(Money(Decimal("9999"), "USDT"),),
            evidence_refs=(DomainRef("EV-account-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            real_money=True,
        )
    with pytest.raises(ContractError, match="all synthetic portfolio money"):
        SyntheticPortfolioSnapshot(
            portfolio_id=PortfolioId("PF-demo-probe-2"),
            account_ref=account.account_id,
            ledger_ref=account.ledger_ref,
            stage=Stage.S3_PAPER_DEMO,
            as_of=NOW,
            reporting_currency="USDT",
            cash=(Money(Decimal("9999"), "BTC"),),
            positions=(),
            equity=(Money(Decimal("9999"), "USDT"),),
            evidence_refs=(DomainRef("EV-account-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )


def test_synthetic_runtime_risk_policy_is_bounded_and_inert() -> None:
    policy = SyntheticRuntimeRiskPolicy(
        policy_id=RiskId("RISK-runtime-probe-1"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        portfolio_ref=PortfolioId("PF-demo-probe-1"),
        max_capital_at_risk=Money(Decimal("10000"), "USDT"),
        max_position_notional=Money(Decimal("2500"), "USDT"),
        max_daily_loss=Money(Decimal("250"), "USDT"),
        max_drawdown_fraction=Decimal("0.10"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        evidence_refs=(DomainRef("EV-runtime-risk-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert policy.synthetic is True
    assert policy.real_money is False
    assert policy.execution_authority.value == "NONE"
    assert policy.paper_orders.value == policy.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="cannot exceed max_capital"):
        SyntheticRuntimeRiskPolicy(
            policy_id=RiskId("RISK-runtime-probe-2"),
            stage=Stage.S3_PAPER_DEMO,
            strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_capital_at_risk=Money(Decimal("10000"), "USDT"),
            max_position_notional=Money(Decimal("10001"), "USDT"),
            max_daily_loss=Money(Decimal("250"), "USDT"),
            max_drawdown_fraction=Decimal("0.10"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            evidence_refs=(DomainRef("EV-runtime-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="below 1"):
        SyntheticRuntimeRiskPolicy(
            policy_id=RiskId("RISK-runtime-probe-3"),
            stage=Stage.S3_PAPER_DEMO,
            strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_capital_at_risk=Money(Decimal("10000"), "USDT"),
            max_position_notional=Money(Decimal("2500"), "USDT"),
            max_daily_loss=Money(Decimal("250"), "USDT"),
            max_drawdown_fraction=Decimal("1"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            evidence_refs=(DomainRef("EV-runtime-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        SyntheticRuntimeRiskPolicy(
            policy_id=RiskId("RISK-runtime-probe-4"),
            stage=Stage.S3_PAPER_DEMO,
            strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_capital_at_risk=Money(Decimal("10000"), "USDT"),
            max_position_notional=Money(Decimal("2500"), "USDT"),
            max_daily_loss=Money(Decimal("250"), "USDT"),
            max_drawdown_fraction=Decimal("0.10"),
            kill_switch_mode=KillSwitchMode.AUTOMATIC_LOCAL_SIMULATION,
            evidence_refs=(DomainRef("EV-runtime-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_synthetic_portfolio_risk_policy_is_bounded_and_inert() -> None:
    policy = SyntheticPortfolioRiskPolicy(
        policy_id=RiskId("RISK-portfolio-probe-1"),
        stage=Stage.S3_PAPER_DEMO,
        portfolio_ref=PortfolioId("PF-demo-probe-1"),
        max_symbol_concentration_fraction=Decimal("0.40"),
        max_correlated_exposure_fraction=Decimal("0.60"),
        max_strategy_budget_fraction=Decimal("0.25"),
        max_open_positions=8,
        evidence_refs=(DomainRef("EV-portfolio-risk-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert policy.synthetic is True
    assert policy.real_money is False
    assert policy.execution_authority.value == "NONE"
    assert policy.paper_orders.value == policy.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S3"):
        SyntheticPortfolioRiskPolicy(
            policy_id=RiskId("RISK-portfolio-probe-2"),
            stage=Stage.S4_LIVE,
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_symbol_concentration_fraction=Decimal("0.40"),
            max_correlated_exposure_fraction=Decimal("0.60"),
            max_strategy_budget_fraction=Decimal("0.25"),
            max_open_positions=8,
            evidence_refs=(DomainRef("EV-portfolio-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="at most 1"):
        SyntheticPortfolioRiskPolicy(
            policy_id=RiskId("RISK-portfolio-probe-3"),
            stage=Stage.S3_PAPER_DEMO,
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_symbol_concentration_fraction=Decimal("1.01"),
            max_correlated_exposure_fraction=Decimal("0.60"),
            max_strategy_budget_fraction=Decimal("0.25"),
            max_open_positions=8,
            evidence_refs=(DomainRef("EV-portfolio-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="positive integer"):
        SyntheticPortfolioRiskPolicy(
            policy_id=RiskId("RISK-portfolio-probe-4"),
            stage=Stage.S3_PAPER_DEMO,
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_symbol_concentration_fraction=Decimal("0.40"),
            max_correlated_exposure_fraction=Decimal("0.60"),
            max_strategy_budget_fraction=Decimal("0.25"),
            max_open_positions=0,
            evidence_refs=(DomainRef("EV-portfolio-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        SyntheticPortfolioRiskPolicy(
            policy_id=RiskId("RISK-portfolio-probe-5"),
            stage=Stage.S3_PAPER_DEMO,
            portfolio_ref=PortfolioId("PF-demo-probe-1"),
            max_symbol_concentration_fraction=Decimal("0.40"),
            max_correlated_exposure_fraction=Decimal("0.60"),
            max_strategy_budget_fraction=Decimal("0.25"),
            max_open_positions=8,
            evidence_refs=(DomainRef("EV-portfolio-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_synthetic_strategy_budget_and_market_guards_are_bounded_and_inert() -> None:
    budget = SyntheticStrategyBudgetPolicy(
        policy_id=RiskId("RISK-budget-probe-1"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        portfolio_ref=PortfolioId("PF-demo-probe-1"),
        max_portfolio_fraction=Decimal("0.25"),
        max_notional=Money(Decimal("2500"), "USDT"),
        max_daily_loss=Money(Decimal("100"), "USDT"),
        max_open_positions=2,
        evidence_refs=(DomainRef("EV-budget-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    market = SyntheticMarketConditionPolicy(
        policy_id=RiskId("RISK-market-guard-1"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        max_market_data_age_seconds=30,
        max_quote_spread_bps=Decimal("25"),
        block_when_venue_health_degraded=True,
        require_monotonic_timestamps=True,
        evidence_refs=(DomainRef("EV-market-guard-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert budget.execution_authority.value == market.execution_authority.value == "NONE"
    assert budget.paper_orders.value == market.paper_orders.value == "DISABLED"
    with pytest.raises(ContractError, match="at most 1"):
        replace(budget, max_portfolio_fraction=Decimal("1.01"))
    with pytest.raises(ContractError, match="cannot exceed"):
        replace(budget, max_daily_loss=Money(Decimal("2501"), "USDT"))
    with pytest.raises(ContractError, match="fail closed"):
        replace(market, block_when_venue_health_degraded=False)
    with pytest.raises(ContractError, match="positive integer"):
        replace(market, max_market_data_age_seconds=0)
    with pytest.raises(ContractError, match="cannot activate orders"):
        replace(market, paper_orders="ENABLED")  # type: ignore[arg-type]


def test_restricted_credential_policy_has_no_secret_or_funds_movement_grant() -> None:
    policy = RestrictedCredentialPolicy(
        policy_id=ApprovalId("APR-credential-policy-1"),
        stage=Stage.S4_LIVE,
        venue_family=VenueFamily("BINANCE_SPOT"),
        allowed_future_permissions=(
            CredentialPermission.READ_MARKET_DATA,
            CredentialPermission.READ_ACCOUNT,
            CredentialPermission.PLACE_SPOT_ORDERS,
            CredentialPermission.CANCEL_SPOT_ORDERS,
        ),
        max_order_notional=Money(Decimal("100"), "USDT"),
        evidence_refs=(DomainRef("EV-credential-policy-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert policy.credential_material_present is False
    assert policy.outbound_funds_allowed is False
    assert policy.transfers_allowed is False
    assert policy.execution_authority.value == "NONE"
    assert policy.venue_connection.value == "NONE"
    assert policy.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="funds movement"):
        RestrictedCredentialPolicy(
            policy_id=ApprovalId("APR-credential-policy-2"),
            stage=Stage.S4_LIVE,
            venue_family=VenueFamily("BINANCE_SPOT"),
            allowed_future_permissions=(CredentialPermission.FUNDS_OUT,),
            max_order_notional=Money(Decimal("100"), "USDT"),
            evidence_refs=(DomainRef("EV-credential-policy-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot contain credential grants"):
        RestrictedCredentialPolicy(
            policy_id=ApprovalId("APR-credential-policy-3"),
            stage=Stage.S4_LIVE,
            venue_family=VenueFamily("BINANCE_SPOT"),
            allowed_future_permissions=(CredentialPermission.READ_ACCOUNT,),
            max_order_notional=Money(Decimal("100"), "USDT"),
            evidence_refs=(DomainRef("EV-credential-policy-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            credential_material_present=True,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        RestrictedCredentialPolicy(
            policy_id=ApprovalId("APR-credential-policy-4"),
            stage=Stage.S4_LIVE,
            venue_family=VenueFamily("BINANCE_SPOT"),
            allowed_future_permissions=(CredentialPermission.READ_ACCOUNT,),
            max_order_notional=Money(Decimal("100"), "USDT"),
            evidence_refs=(DomainRef("EV-credential-policy-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            live_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_paper_operations_runbook_is_probe_only_and_bounded() -> None:
    runbook = PaperOperationsRunbook(
        runbook_id=ApprovalId("APR-runbook-1"),
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=ApprovalId("APR-paper-1"),
        runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
        heartbeat_interval_seconds=60,
        heartbeat_timeout_seconds=180,
        log_retention_days=90,
        intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
        evidence_refs=(DomainRef("EV-runbook-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert runbook.execution_authority.value == "NONE"
    assert runbook.paper_orders.value == runbook.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S3"):
        PaperOperationsRunbook(
            runbook_id=ApprovalId("APR-runbook-2"),
            stage=Stage.S4_LIVE,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            heartbeat_interval_seconds=60,
            heartbeat_timeout_seconds=180,
            log_retention_days=90,
            intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="heartbeat timeout"):
        PaperOperationsRunbook(
            runbook_id=ApprovalId("APR-runbook-3"),
            stage=Stage.S3_PAPER_DEMO,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            heartbeat_interval_seconds=60,
            heartbeat_timeout_seconds=30,
            log_retention_days=90,
            intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        PaperOperationsRunbook(
            runbook_id=ApprovalId("APR-runbook-4"),
            stage=Stage.S3_PAPER_DEMO,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            heartbeat_interval_seconds=60,
            heartbeat_timeout_seconds=180,
            log_retention_days=90,
            intervention_mode=PaperRunbookInterventionMode.LOCAL_SIMULATION_ONLY,
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_paper_operations_event_record_is_evidence_only() -> None:
    event = PaperOperationsEventRecord(
        event_id=ApprovalId("APR-paper-event-1"),
        stage=Stage.S3_PAPER_DEMO,
        runbook_ref=ApprovalId("APR-runbook-1"),
        occurred_at=NOW,
        kind=PaperOperationsEventKind.HEARTBEAT,
        severity=PaperOperationsEventSeverity.INFO,
        detail="heartbeat retained for future paper operations",
        evidence_refs=(DomainRef("EV-runbook-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert event.execution_authority.value == "NONE"
    assert event.paper_orders.value == event.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S3"):
        PaperOperationsEventRecord(
            event_id=ApprovalId("APR-paper-event-2"),
            stage=Stage.S4_LIVE,
            runbook_ref=ApprovalId("APR-runbook-1"),
            occurred_at=NOW,
            kind=PaperOperationsEventKind.PROCESS_STARTED,
            severity=PaperOperationsEventSeverity.INFO,
            detail="wrong stage",
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot be INFO"):
        PaperOperationsEventRecord(
            event_id=ApprovalId("APR-paper-event-3"),
            stage=Stage.S3_PAPER_DEMO,
            runbook_ref=ApprovalId("APR-runbook-1"),
            occurred_at=NOW,
            kind=PaperOperationsEventKind.KILL_SWITCH_OBSERVED,
            severity=PaperOperationsEventSeverity.INFO,
            detail="risk-relevant event",
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        PaperOperationsEventRecord(
            event_id=ApprovalId("APR-paper-event-4"),
            stage=Stage.S3_PAPER_DEMO,
            runbook_ref=ApprovalId("APR-runbook-1"),
            occurred_at=NOW,
            kind=PaperOperationsEventKind.MANUAL_INTERVENTION,
            severity=PaperOperationsEventSeverity.WARN,
            detail="manual intervention observed",
            evidence_refs=(DomainRef("EV-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_paper_stability_report_is_blocked_until_paper_window_exists() -> None:
    blocked = PaperStabilityReport(
        report_id=ApprovalId("APR-stability-1"),
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=ApprovalId("APR-paper-1"),
        divergence_report_ref=ApprovalId("APR-divergence-1"),
        runbook_ref=ApprovalId("APR-runbook-1"),
        runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
        window_started_at=NOW,
        window_ended_at=NOW + timedelta(hours=1),
        required_observation_hours=Decimal("168"),
        observed_uptime_fraction=Decimal("0"),
        incident_count=0,
        missed_heartbeat_count=0,
        status=PaperStabilityStatus.BLOCKED,
        evidence_refs=(DomainRef("EV-stability-1"),),
        blocker="no active paper lane",
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert blocked.execution_authority.value == "NONE"
    assert blocked.paper_orders.value == blocked.live_orders.value == "DISABLED"

    passing = PaperStabilityReport(
        report_id=ApprovalId("APR-stability-2"),
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=ApprovalId("APR-paper-1"),
        divergence_report_ref=ApprovalId("APR-divergence-1"),
        runbook_ref=ApprovalId("APR-runbook-1"),
        runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
        window_started_at=NOW,
        window_ended_at=NOW + timedelta(hours=168),
        required_observation_hours=Decimal("168"),
        observed_uptime_fraction=Decimal("1"),
        incident_count=0,
        missed_heartbeat_count=0,
        status=PaperStabilityStatus.PASS,
        evidence_refs=(DomainRef("EV-stability-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert passing.status is PaperStabilityStatus.PASS

    with pytest.raises(ContractError, match="observation window and uptime"):
        replace(
            passing,
            report_id=ApprovalId("APR-stability-short-window"),
            window_ended_at=NOW + timedelta(hours=1),
        )
    with pytest.raises(ContractError, match="nonnegative"):
        replace(
            blocked,
            report_id=ApprovalId("APR-stability-negative-uptime"),
            observed_uptime_fraction=Decimal("-0.1"),
        )

    with pytest.raises(ContractError, match="require a blocker"):
        PaperStabilityReport(
            report_id=ApprovalId("APR-stability-3"),
            stage=Stage.S3_PAPER_DEMO,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            divergence_report_ref=ApprovalId("APR-divergence-1"),
            runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            window_started_at=NOW,
            window_ended_at=NOW + timedelta(hours=1),
            required_observation_hours=Decimal("168"),
            observed_uptime_fraction=Decimal("0"),
            incident_count=0,
            missed_heartbeat_count=0,
            status=PaperStabilityStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-stability-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="zero incidents"):
        PaperStabilityReport(
            report_id=ApprovalId("APR-stability-4"),
            stage=Stage.S3_PAPER_DEMO,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            divergence_report_ref=ApprovalId("APR-divergence-1"),
            runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            window_started_at=NOW,
            window_ended_at=NOW + timedelta(hours=168),
            required_observation_hours=Decimal("168"),
            observed_uptime_fraction=Decimal("1"),
            incident_count=1,
            missed_heartbeat_count=0,
            status=PaperStabilityStatus.PASS,
            evidence_refs=(DomainRef("EV-stability-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        PaperStabilityReport(
            report_id=ApprovalId("APR-stability-5"),
            stage=Stage.S3_PAPER_DEMO,
            paper_lane_ref=ApprovalId("APR-paper-1"),
            divergence_report_ref=ApprovalId("APR-divergence-1"),
            runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            window_started_at=NOW,
            window_ended_at=NOW + timedelta(hours=1),
            required_observation_hours=Decimal("168"),
            observed_uptime_fraction=Decimal("0"),
            incident_count=0,
            missed_heartbeat_count=0,
            status=PaperStabilityStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-stability-1"),),
            blocker="no active paper lane",
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            paper_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_limited_live_risk_package_is_blocked_until_s4_gates() -> None:
    blocked = LimitedLiveRiskPackage(
        package_id=ApprovalId("APR-live-risk-package-1"),
        stage=Stage.S4_LIVE,
        paper_stability_ref=ApprovalId("APR-stability-1"),
        credential_policy_ref=ApprovalId("APR-credential-policy-1"),
        operations_runbook_ref=ApprovalId("APR-runbook-1"),
        runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
        maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
        maximum_single_order_notional=Money(Decimal("100"), "USDT"),
        maximum_daily_loss=Money(Decimal("50"), "USDT"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        status=LimitedLiveRiskPackageStatus.BLOCKED,
        evidence_refs=(DomainRef("EV-live-risk-1"),),
        blocker="paper stability missing",
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert blocked.execution_authority.value == "NONE"
    assert blocked.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="operator-manual kill switch"):
        replace(
            blocked,
            package_id=ApprovalId("APR-live-risk-package-automatic"),
            status=LimitedLiveRiskPackageStatus.READY_FOR_OPERATOR_DECISION,
            kill_switch_mode=KillSwitchMode.AUTOMATIC_LOCAL_SIMULATION,
            blocker=None,
        )

    with pytest.raises(ContractError, match="reserved for S4"):
        LimitedLiveRiskPackage(
            package_id=ApprovalId("APR-live-risk-package-2"),
            stage=Stage.S3_PAPER_DEMO,
            paper_stability_ref=ApprovalId("APR-stability-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            operations_runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
            maximum_single_order_notional=Money(Decimal("100"), "USDT"),
            maximum_daily_loss=Money(Decimal("50"), "USDT"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            status=LimitedLiveRiskPackageStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-live-risk-1"),),
            blocker="paper stability missing",
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="require a blocker"):
        LimitedLiveRiskPackage(
            package_id=ApprovalId("APR-live-risk-package-3"),
            stage=Stage.S4_LIVE,
            paper_stability_ref=ApprovalId("APR-stability-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            operations_runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
            maximum_single_order_notional=Money(Decimal("100"), "USDT"),
            maximum_daily_loss=Money(Decimal("50"), "USDT"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            status=LimitedLiveRiskPackageStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-live-risk-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot exceed capital"):
        LimitedLiveRiskPackage(
            package_id=ApprovalId("APR-live-risk-package-4"),
            stage=Stage.S4_LIVE,
            paper_stability_ref=ApprovalId("APR-stability-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            operations_runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
            maximum_single_order_notional=Money(Decimal("1001"), "USDT"),
            maximum_daily_loss=Money(Decimal("50"), "USDT"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            status=LimitedLiveRiskPackageStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-live-risk-1"),),
            blocker="paper stability missing",
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        LimitedLiveRiskPackage(
            package_id=ApprovalId("APR-live-risk-package-5"),
            stage=Stage.S4_LIVE,
            paper_stability_ref=ApprovalId("APR-stability-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            operations_runbook_ref=ApprovalId("APR-runbook-1"),
            runtime_risk_policy_ref=RiskId("RISK-runtime-probe-1"),
            maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
            maximum_single_order_notional=Money(Decimal("100"), "USDT"),
            maximum_daily_loss=Money(Decimal("50"), "USDT"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            status=LimitedLiveRiskPackageStatus.BLOCKED,
            evidence_refs=(DomainRef("EV-live-risk-1"),),
            blocker="paper stability missing",
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            live_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_live_operations_runbook_is_inert_s4_evidence() -> None:
    runbook = LiveOperationsRunbook(
        runbook_id=ApprovalId("APR-live-runbook-1"),
        stage=Stage.S4_LIVE,
        limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
        credential_policy_ref=ApprovalId("APR-credential-policy-1"),
        heartbeat_interval_seconds=60,
        incident_response_minutes=15,
        log_retention_days=365,
        escalation_mode=LiveRunbookEscalationMode.OPERATOR_MANUAL_ONLY,
        evidence_refs=(DomainRef("EV-live-runbook-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert runbook.execution_authority.value == "NONE"
    assert runbook.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S4"):
        LiveOperationsRunbook(
            runbook_id=ApprovalId("APR-live-runbook-2"),
            stage=Stage.S3_PAPER_DEMO,
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            heartbeat_interval_seconds=60,
            incident_response_minutes=15,
            log_retention_days=365,
            escalation_mode=LiveRunbookEscalationMode.OPERATOR_MANUAL_ONLY,
            evidence_refs=(DomainRef("EV-live-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="positive integer"):
        LiveOperationsRunbook(
            runbook_id=ApprovalId("APR-live-runbook-3"),
            stage=Stage.S4_LIVE,
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            heartbeat_interval_seconds=0,
            incident_response_minutes=15,
            log_retention_days=365,
            escalation_mode=LiveRunbookEscalationMode.DISABLE_AND_REVIEW,
            evidence_refs=(DomainRef("EV-live-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        LiveOperationsRunbook(
            runbook_id=ApprovalId("APR-live-runbook-4"),
            stage=Stage.S4_LIVE,
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            credential_policy_ref=ApprovalId("APR-credential-policy-1"),
            heartbeat_interval_seconds=60,
            incident_response_minutes=15,
            log_retention_days=365,
            escalation_mode=LiveRunbookEscalationMode.OPERATOR_MANUAL_ONLY,
            evidence_refs=(DomainRef("EV-live-runbook-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            live_orders="ENABLED",  # type: ignore[arg-type]
        )


def test_live_operations_event_record_is_inert_s4_evidence() -> None:
    event = LiveOperationsEventRecord(
        event_id=ApprovalId("APR-live-event-1"),
        stage=Stage.S4_LIVE,
        runbook_ref=ApprovalId("APR-live-runbook-1"),
        limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
        occurred_at=NOW,
        kind=LiveOperationsEventKind.HEARTBEAT,
        severity=LiveOperationsEventSeverity.INFO,
        detail="heartbeat retained for future limited-live operations",
        evidence_refs=(DomainRef("EV-live-event-1"),),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    assert event.execution_authority.value == "NONE"
    assert event.live_orders.value == "DISABLED"

    with pytest.raises(ContractError, match="reserved for S4"):
        LiveOperationsEventRecord(
            event_id=ApprovalId("APR-live-event-2"),
            stage=Stage.S3_PAPER_DEMO,
            runbook_ref=ApprovalId("APR-live-runbook-1"),
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            occurred_at=NOW,
            kind=LiveOperationsEventKind.PROCESS_STARTED,
            severity=LiveOperationsEventSeverity.INFO,
            detail="wrong stage",
            evidence_refs=(DomainRef("EV-live-event-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot be INFO"):
        LiveOperationsEventRecord(
            event_id=ApprovalId("APR-live-event-3"),
            stage=Stage.S4_LIVE,
            runbook_ref=ApprovalId("APR-live-runbook-1"),
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            occurred_at=NOW,
            kind=LiveOperationsEventKind.RISK_LIMIT_BREACH,
            severity=LiveOperationsEventSeverity.INFO,
            detail="risk-relevant event",
            evidence_refs=(DomainRef("EV-live-event-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        LiveOperationsEventRecord(
            event_id=ApprovalId("APR-live-event-4"),
            stage=Stage.S4_LIVE,
            runbook_ref=ApprovalId("APR-live-runbook-1"),
            limited_live_risk_package_ref=ApprovalId("APR-live-risk-package-1"),
            occurred_at=NOW,
            kind=LiveOperationsEventKind.ESCALATION_RECORDED,
            severity=LiveOperationsEventSeverity.WARN,
            detail="operator escalation recorded",
            evidence_refs=(DomainRef("EV-live-event-1"),),
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
            live_orders="ENABLED",  # type: ignore[arg-type]
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
