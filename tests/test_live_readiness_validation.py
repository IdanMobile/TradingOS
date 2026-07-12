from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tios.trading_domain import (
    ApprovalId,
    CreatorType,
    CredentialPermission,
    DomainRef,
    KillSwitchMode,
    LimitedLiveRiskPackage,
    LimitedLiveRiskPackageStatus,
    Money,
    OperationalDrillKind,
    OperationalDrillRecord,
    OperationalDrillStatus,
    PaperOperationsRunbook,
    PaperRunbookInterventionMode,
    PaperStabilityReport,
    PaperStabilityStatus,
    PortfolioId,
    Provenance,
    RestrictedCredentialPolicy,
    RiskId,
    Stage,
    SyntheticRuntimeRiskPolicy,
    VenueFamily,
    validate_limited_live_readiness,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-live-readiness-validation"),)
PROVENANCE = Provenance(EVIDENCE)
STABILITY_ID = ApprovalId("APR-stability-ready")
CREDENTIAL_ID = ApprovalId("APR-credential-ready")
RUNBOOK_ID = ApprovalId("APR-paper-runbook-ready")
RUNTIME_ID = RiskId("RISK-runtime-ready")
PAPER_ID = ApprovalId("APR-paper-ready")


def stability() -> PaperStabilityReport:
    return PaperStabilityReport(
        report_id=STABILITY_ID,
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=PAPER_ID,
        divergence_report_ref=ApprovalId("APR-divergence-ready"),
        runbook_ref=RUNBOOK_ID,
        runtime_risk_policy_ref=RUNTIME_ID,
        window_started_at=NOW,
        window_ended_at=NOW + timedelta(hours=168),
        required_observation_hours=Decimal("168"),
        observed_uptime_fraction=Decimal("1"),
        incident_count=0,
        missed_heartbeat_count=0,
        status=PaperStabilityStatus.PASS,
        evidence_refs=EVIDENCE,
        created_at=NOW + timedelta(hours=168),
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def runtime() -> SyntheticRuntimeRiskPolicy:
    return SyntheticRuntimeRiskPolicy(
        policy_id=RUNTIME_ID,
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-live-readiness-context"),
        portfolio_ref=PortfolioId("PF-live-readiness"),
        max_capital_at_risk=Money(Decimal("1000"), "USDT"),
        max_position_notional=Money(Decimal("100"), "USDT"),
        max_daily_loss=Money(Decimal("50"), "USDT"),
        max_drawdown_fraction=Decimal("0.10"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def credential() -> RestrictedCredentialPolicy:
    return RestrictedCredentialPolicy(
        policy_id=CREDENTIAL_ID,
        stage=Stage.S4_LIVE,
        venue_family=VenueFamily("BINANCE_SPOT"),
        allowed_future_permissions=(
            CredentialPermission.READ_MARKET_DATA,
            CredentialPermission.READ_ACCOUNT,
            CredentialPermission.PLACE_SPOT_ORDERS,
            CredentialPermission.CANCEL_SPOT_ORDERS,
        ),
        max_order_notional=Money(Decimal("100"), "USDT"),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def runbook() -> PaperOperationsRunbook:
    return PaperOperationsRunbook(
        runbook_id=RUNBOOK_ID,
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=PAPER_ID,
        runtime_risk_policy_ref=RUNTIME_ID,
        heartbeat_interval_seconds=60,
        heartbeat_timeout_seconds=180,
        log_retention_days=90,
        intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def package() -> LimitedLiveRiskPackage:
    return LimitedLiveRiskPackage(
        package_id=ApprovalId("APR-live-risk-ready"),
        stage=Stage.S4_LIVE,
        paper_stability_ref=STABILITY_ID,
        credential_policy_ref=CREDENTIAL_ID,
        operations_runbook_ref=RUNBOOK_ID,
        runtime_risk_policy_ref=RUNTIME_ID,
        maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
        maximum_single_order_notional=Money(Decimal("100"), "USDT"),
        maximum_daily_loss=Money(Decimal("50"), "USDT"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        status=LimitedLiveRiskPackageStatus.READY_FOR_OPERATOR_DECISION,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def drills() -> tuple[OperationalDrillRecord, ...]:
    return tuple(
        OperationalDrillRecord(
            drill_id=ApprovalId(f"APR-drill-{kind.value.lower()}"),
            stage=(
                Stage.S4_LIVE
                if kind is OperationalDrillKind.CREDENTIAL_REVOCATION
                else Stage.S3_PAPER_DEMO
            ),
            kind=kind,
            status=OperationalDrillStatus.PASS,
            evidence_refs=EVIDENCE,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        for kind in OperationalDrillKind
    )


def test_limited_live_readiness_resolves_complete_evidence_graph() -> None:
    result = validate_limited_live_readiness(
        package=package(),
        stability=stability(),
        credential_policy=credential(),
        operations_runbook=runbook(),
        runtime_policy=runtime(),
        drills=drills(),
    )
    assert result.ready is True
    assert result.blockers == ()


def test_limited_live_readiness_reports_missing_and_incompatible_evidence() -> None:
    result = validate_limited_live_readiness(
        package=replace(
            package(),
            paper_stability_ref=ApprovalId("APR-stability-missing"),
            maximum_single_order_notional=Money(Decimal("100"), "USDT"),
        ),
        stability=replace(stability(), status=PaperStabilityStatus.FAIL),
        credential_policy=credential(),
        operations_runbook=runbook(),
        runtime_policy=runtime(),
        drills=(),
    )
    assert result.ready is False
    assert "paper stability reference does not resolve" in result.blockers
    assert "paper stability has not passed" in result.blockers
    assert "required drill has not passed: MANUAL_KILL_SWITCH" in result.blockers
