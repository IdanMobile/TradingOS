from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tios.services.reporting import (
    DecisionTraceLedger,
    DecisionTraceLedgerError,
    project_decision_report,
    trace_digest,
)
from tios.trading_domain import (
    AttributionBasis,
    ContractError,
    CreatorType,
    DecisionOutcome,
    DecisionTrace,
    DecisionTraceStatus,
    DomainRef,
    FailureAttribution,
    FillEvent,
    FillId,
    InstrumentId,
    LiquidityRole,
    Money,
    OrderId,
    OrderIntent,
    OrderType,
    OutcomeClassification,
    Provenance,
    RiskCheck,
    RiskDecision,
    RiskId,
    RiskOutcome,
    RunId,
    Side,
    SignalEvent,
    SignalId,
    StrategyVersionId,
    Timeframe,
)

NOW = datetime(2026, 7, 21, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-DECISION-INTELLIGENCE-TEST"),)
PROVENANCE = Provenance(EVIDENCE)
INSTRUMENT = InstrumentId("ETH-USDT.BYBIT_DEMO")
SHA = "a" * 64


def _signal(index: int, side: Side = Side.BUY) -> SignalEvent:
    return SignalEvent(
        signal_id=SignalId(f"SIG-DI-{index}"),
        strategy_version_ref=StrategyVersionId("SV-DI-V1"),
        run_ref=RunId(f"RUN-DI-{index}"),
        instrument=INSTRUMENT,
        timeframe=Timeframe.H1,
        observed_at=NOW,
        side=side,
        rationale_code="OFFLINE_PROBE",
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def _risk(signal: SignalEvent, outcome: RiskOutcome = RiskOutcome.PASS) -> RiskDecision:
    check = RiskCheck("OFFLINE_PROBE", outcome, EVIDENCE, "deterministic fixture")
    return RiskDecision(
        risk_id=RiskId(f"RISK-{signal.signal_id.value}"),
        subject_ref=DomainRef(signal.signal_id.value),
        as_of=NOW,
        decision=outcome,
        rule_results=(check,),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def _filled_trace(
    index: int,
    net: str,
    classification: OutcomeClassification,
) -> DecisionTrace:
    signal = _signal(index)
    risk = _risk(signal)
    order_ref = OrderId(f"ORD-DI-{index}")
    intent = OrderIntent(
        source_signal_ref=signal.signal_id,
        run_ref=signal.run_ref,
        instrument=signal.instrument,
        side=signal.side,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        limit_price=None,
        stop_price=None,
        bracket_levels=None,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    fill = FillEvent(
        fill_id=FillId(f"FILL-DI-{index}"),
        order_ref=order_ref,
        run_ref=signal.run_ref,
        instrument=signal.instrument,
        filled_at=NOW,
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Money(Decimal("0.1"), "USDT"),
        liquidity_role=LiquidityRole.TAKER,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    net_pnl = Decimal(net)
    attribution = None
    if classification is OutcomeClassification.ORDINARY_STATISTICAL_LOSS:
        attribution = FailureAttribution(
            classification=classification,
            basis=AttributionBasis.DETERMINISTIC,
            confidence=Decimal("0.80"),
            facts=("All data, risk, cost, and fill checks passed; return was negative.",),
            competing_hypotheses=("The strategy edge may be weakening prospectively.",),
            evidence_refs=EVIDENCE,
        )
    return DecisionTrace(
        trace_id=f"TRACE-DI-{index}",
        input_sha256=SHA,
        feature_sha256="b" * 64,
        strategy_spec_sha256="c" * 64,
        signal=signal,
        risk=risk,
        status=DecisionTraceStatus.SIMULATED_FILLED,
        intent=intent,
        order_ref=order_ref,
        fills=(fill,),
        outcome=DecisionOutcome(
            classification=classification,
            gross_pnl=net_pnl + Decimal("0.20"),
            fees=Decimal("0.10"),
            slippage_cost=Decimal("0.10"),
            net_pnl=net_pnl,
            currency="USDT",
            horizon_seconds=3600,
            reconciled=True,
        ),
        attribution=attribution,
        evidence_refs=EVIDENCE,
        provenance=PROVENANCE,
    )


def _blocked_trace(index: int) -> DecisionTrace:
    signal = _signal(index)
    return DecisionTrace(
        trace_id=f"TRACE-DI-{index}",
        input_sha256=SHA,
        feature_sha256="b" * 64,
        strategy_spec_sha256="c" * 64,
        signal=signal,
        risk=_risk(signal, RiskOutcome.BLOCK),
        status=DecisionTraceStatus.RISK_BLOCKED,
        intent=None,
        order_ref=None,
        fills=(),
        outcome=DecisionOutcome(
            classification=OutcomeClassification.CORRECT_RISK_BLOCK,
            gross_pnl=Decimal("0"),
            fees=Decimal("0"),
            slippage_cost=Decimal("0"),
            net_pnl=Decimal("0"),
            currency="USDT",
            horizon_seconds=0,
            reconciled=True,
        ),
        attribution=FailureAttribution(
            classification=OutcomeClassification.CORRECT_RISK_BLOCK,
            basis=AttributionBasis.DETERMINISTIC,
            confidence=Decimal("1"),
            facts=("The independent risk rule blocked the intent.",),
            competing_hypotheses=(),
            evidence_refs=EVIDENCE,
        ),
        evidence_refs=EVIDENCE,
        provenance=PROVENANCE,
    )


def _no_trade_trace(index: int) -> DecisionTrace:
    signal = _signal(index, Side.FLAT)
    return DecisionTrace(
        trace_id=f"TRACE-DI-{index}",
        input_sha256=SHA,
        feature_sha256="b" * 64,
        strategy_spec_sha256="c" * 64,
        signal=signal,
        risk=_risk(signal),
        status=DecisionTraceStatus.NO_TRADE,
        intent=None,
        order_ref=None,
        fills=(),
        outcome=DecisionOutcome(
            classification=OutcomeClassification.NO_TRADE,
            gross_pnl=Decimal("0"),
            fees=Decimal("0"),
            slippage_cost=Decimal("0"),
            net_pnl=Decimal("0"),
            currency="USDT",
            horizon_seconds=3600,
            reconciled=True,
        ),
        attribution=None,
        evidence_refs=EVIDENCE,
        provenance=PROVENANCE,
    )


def test_trace_rejects_unreconciled_accounting_and_order_artifacts_after_block() -> None:
    profitable = _filled_trace(1, "2.0", OutcomeClassification.PROFITABLE)
    with pytest.raises(ContractError, match="net_pnl must reconcile"):
        replace(profitable.outcome, net_pnl=Decimal("999"))
    with pytest.raises(ContractError, match="classification must agree"):
        replace(
            profitable.outcome,
            classification=OutcomeClassification.ORDINARY_STATISTICAL_LOSS,
        )
    with pytest.raises(ContractError, match="fees must reconcile"):
        replace(
            profitable,
            outcome=replace(
                profitable.outcome,
                gross_pnl=Decimal("2.30"),
                fees=Decimal("0.20"),
            ),
        )

    blocked = _blocked_trace(2)
    assert profitable.intent is not None
    blocked_intent = replace(
        profitable.intent,
        source_signal_ref=blocked.signal.signal_id,
        run_ref=blocked.signal.run_ref,
    )
    with pytest.raises(ContractError, match="blocked decision cannot have order artifacts"):
        replace(blocked, intent=blocked_intent)


def test_report_separates_ordinary_loss_from_defect_and_preserves_funnel() -> None:
    traces = (
        _filled_trace(1, "2.0", OutcomeClassification.PROFITABLE),
        _filled_trace(2, "-1.5", OutcomeClassification.ORDINARY_STATISTICAL_LOSS),
        _blocked_trace(3),
        _no_trade_trace(4),
    )
    report = project_decision_report(traces)
    assert report.trace_count == 4
    assert report.risk_passed_count == 3
    assert report.risk_blocked_count == 1
    assert report.no_trade_count == 1
    assert report.intent_count == report.order_count == report.fill_event_count == 2
    assert report.reconciled_count == 2
    assert report.profitable_count == report.ordinary_loss_count == 1
    assert report.confirmed_defect_count == 0
    assert report.net_pnl == Decimal("0.5")
    assert len(report.source_trace_digests) == 4


def test_ai_defect_diagnosis_is_counted_as_hypothesis_not_confirmed() -> None:
    trace = _filled_trace(5, "-1", OutcomeClassification.ORDINARY_STATISTICAL_LOSS)
    hypothesis = replace(
        trace,
        outcome=replace(trace.outcome, classification=OutcomeClassification.EXECUTION_DEFECT),
        attribution=FailureAttribution(
            classification=OutcomeClassification.EXECUTION_DEFECT,
            basis=AttributionBasis.AI_HYPOTHESIS,
            confidence=Decimal("0.4"),
            facts=("Observed net return was negative after recorded costs.",),
            competing_hypotheses=("Signal weakness rather than execution may explain the loss.",),
            evidence_refs=EVIDENCE,
        ),
    )
    report = project_decision_report((hypothesis,))
    assert report.ai_hypothesis_count == 1
    assert report.confirmed_defect_count == 0


def test_ledger_is_idempotent_and_detects_tampering_and_conflicting_replay(
    tmp_path: Path,
) -> None:
    trace = _filled_trace(1, "2.0", OutcomeClassification.PROFITABLE)
    ledger = DecisionTraceLedger(tmp_path / "decision_traces.jsonl")
    first_digest = ledger.append(trace)
    assert ledger.append(trace) == first_digest
    assert len(ledger.records()) == 1

    conflicting = replace(
        trace,
        outcome=replace(
            trace.outcome,
            gross_pnl=Decimal("3.20"),
            net_pnl=Decimal("3.0"),
        ),
    )
    with pytest.raises(DecisionTraceLedgerError, match="different retained content"):
        ledger.append(conflicting)

    content = ledger.path.read_text()
    ledger.path.write_text(content.replace('"net_pnl":"2.0"', '"net_pnl":"9.0"'))
    with pytest.raises(DecisionTraceLedgerError, match="digest mismatch"):
        ledger.records()


@given(
    st.permutations(
        (
            _filled_trace(1, "2.0", OutcomeClassification.PROFITABLE),
            _filled_trace(2, "-1.5", OutcomeClassification.ORDINARY_STATISTICAL_LOSS),
            _blocked_trace(3),
        )
    )
)
def test_report_is_order_independent(traces: list[DecisionTrace]) -> None:
    report = project_decision_report(tuple(traces))
    canonical = project_decision_report(tuple(sorted(traces, key=lambda item: item.trace_id)))
    assert report == canonical
    assert report.source_trace_digests == tuple(
        trace_digest(trace) for trace in sorted(traces, key=lambda item: item.trace_id)
    )
