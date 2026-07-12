from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.trading_domain import (
    ApprovalId,
    ContractError,
    CreatorType,
    DivergenceMetric,
    DivergenceStatus,
    DomainRef,
    PaperOperationsEventKind,
    PaperOperationsEventRecord,
    PaperOperationsEventSeverity,
    PaperOperationsRunbook,
    PaperRunbookInterventionMode,
    PaperStabilityStatus,
    Provenance,
    RiskId,
    RunId,
    Stage,
    build_synthetic_divergence_report,
    evaluate_paper_stability,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-synthetic-stability"),)
PROVENANCE = Provenance(EVIDENCE)
RUNBOOK_ID = ApprovalId("APR-paper-runbook-stability")


def divergence(paper_return: str = "0.11"):
    return build_synthetic_divergence_report(
        report_id=ApprovalId("APR-divergence-computed"),
        strategy_context_ref=DomainRef("SV-computed-context"),
        backtest_run_ref=RunId("RUN-backtest-computed"),
        paper_context_ref=DomainRef("APR-paper-computed"),
        backtest_metrics={
            DivergenceMetric.TOTAL_RETURN: Decimal("0.10"),
            DivergenceMetric.FILL_COUNT: Decimal("10"),
        },
        synthetic_metrics={
            DivergenceMetric.TOTAL_RETURN: Decimal(paper_return),
            DivergenceMetric.FILL_COUNT: Decimal("10"),
        },
        tolerances={
            DivergenceMetric.TOTAL_RETURN: Decimal("0.02"),
            DivergenceMetric.FILL_COUNT: Decimal("0"),
        },
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def runbook() -> PaperOperationsRunbook:
    return PaperOperationsRunbook(
        runbook_id=RUNBOOK_ID,
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=ApprovalId("APR-paper-computed"),
        runtime_risk_policy_ref=RiskId("RISK-runtime-computed"),
        heartbeat_interval_seconds=60,
        heartbeat_timeout_seconds=180,
        log_retention_days=90,
        intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def event(
    minute: int,
    kind: PaperOperationsEventKind = PaperOperationsEventKind.HEARTBEAT,
    severity: PaperOperationsEventSeverity = PaperOperationsEventSeverity.INFO,
) -> PaperOperationsEventRecord:
    return PaperOperationsEventRecord(
        event_id=ApprovalId(f"APR-paper-event-{minute}-{kind.value.lower()}"),
        stage=Stage.S3_PAPER_DEMO,
        runbook_ref=RUNBOOK_ID,
        occurred_at=NOW + timedelta(minutes=minute),
        kind=kind,
        severity=severity,
        detail="computed stability event",
        evidence_refs=EVIDENCE,
        created_at=NOW + timedelta(minutes=minute),
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def evaluate(events, report=None):  # type: ignore[no-untyped-def]
    return evaluate_paper_stability(
        report_id=ApprovalId("APR-stability-computed"),
        paper_lane_ref=ApprovalId("APR-paper-computed"),
        divergence_report=report or divergence(),
        runbook=runbook(),
        runtime_risk_policy_ref=RiskId("RISK-runtime-computed"),
        window_started_at=NOW,
        window_ended_at=NOW + timedelta(minutes=3),
        required_observation_hours=Decimal("0.05"),
        events=events,
        evidence_refs=EVIDENCE,
        created_at=NOW + timedelta(minutes=3),
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def test_computed_divergence_and_stability_pass_with_complete_evidence() -> None:
    report = divergence()
    assert report.status is DivergenceStatus.WITHIN_TOLERANCE
    stability = evaluate(tuple(event(minute) for minute in range(3)), report)
    assert stability.status is PaperStabilityStatus.PASS
    assert stability.observed_uptime_fraction == 1
    assert stability.incident_count == stability.missed_heartbeat_count == 0


def test_computed_stability_fails_on_missing_heartbeat_incident_or_divergence() -> None:
    missing = evaluate((event(0), event(1)))
    assert missing.status is PaperStabilityStatus.FAIL
    assert missing.observed_uptime_fraction == Decimal("2") / Decimal("3")

    incident = evaluate(
        (
            event(0),
            event(1),
            event(2),
            event(
                2,
                PaperOperationsEventKind.MANUAL_INTERVENTION,
                PaperOperationsEventSeverity.WARN,
            ),
        )
    )
    assert incident.status is PaperStabilityStatus.FAIL
    assert incident.incident_count == 1

    divergent = evaluate(tuple(event(minute) for minute in range(3)), divergence("0.20"))
    assert divergent.status is PaperStabilityStatus.FAIL


def test_divergence_metric_sets_and_event_context_fail_closed() -> None:
    with pytest.raises(ContractError, match="sets must match"):
        build_synthetic_divergence_report(
            report_id=ApprovalId("APR-divergence-bad"),
            strategy_context_ref=DomainRef("SV-computed-context"),
            backtest_run_ref=RunId("RUN-backtest-computed"),
            paper_context_ref=DomainRef("APR-paper-computed"),
            backtest_metrics={DivergenceMetric.TOTAL_RETURN: Decimal("0.1")},
            synthetic_metrics={},
            tolerances={DivergenceMetric.TOTAL_RETURN: Decimal("0.1")},
            evidence_refs=EVIDENCE,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="runbook and window"):
        evaluate((event(4),))
