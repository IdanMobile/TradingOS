#!/usr/bin/env python3
"""Build retained S3/S4 readiness evidence without activating paper or live trading."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from tios.trading_domain import (
    AccountId,
    ApprovalId,
    CreatorType,
    CredentialPermission,
    DivergenceMetric,
    DivergenceObservation,
    DomainRef,
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
    Money,
    OperationalDrillKind,
    OperationalDrillRecord,
    OperationalDrillStatus,
    OperationalIncidentRecord,
    OperationalIncidentSeverity,
    OperationalIncidentStatus,
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
    Provenance,
    RestrictedCredentialPolicy,
    RiskId,
    RunId,
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
    VenueFamily,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "artifacts" / "reports" / "S3_S4_CONTROL_PLANE_READINESS_2026_07_11.json"
REPORT_MD = ROOT / "artifacts" / "reports" / "S3_S4_CONTROL_PLANE_READINESS_2026_07_11.md"
CREATED_AT = datetime(2026, 7, 11, tzinfo=UTC)
PROVENANCE = Provenance((DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),))


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _requirement(
    code: str,
    *,
    satisfied: bool,
    evidence_ref: str = "EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11",
    blocker: str = "not satisfied",
    kind: StageGateRequirementKind = StageGateRequirementKind.EVIDENCE,
) -> StageGateRequirement:
    return StageGateRequirement(
        code=code,
        kind=kind,
        satisfied=satisfied,
        evidence_refs=(DomainRef(evidence_ref),) if satisfied else (),
        blocker=None if satisfied else blocker,
    )


def build_payload() -> dict[str, Any]:
    s3_gate = StageGateReadinessRecord(
        gate_id=StageGateId("GATE-S3-PAPER-DEMO-READINESS-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        subject_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        requirements=(
            _requirement("S2_RESEARCH_CONSOLE_IMPLEMENTED", satisfied=True),
            _requirement("NO_LIVE_NO_ORDER_BOUNDARY_VERIFIED", satisfied=True),
            _requirement("S3_S4_CONTRACTS_IMPLEMENTED", satisfied=True),
            _requirement(
                "S2_EXIT_PASS",
                satisfied=False,
                blocker="S2 requirement audit says no strategy is complete approvable",
            ),
            _requirement(
                "HG_3_APPROVED",
                satisfied=False,
                blocker="operator has not approved HG-3",
                kind=StageGateRequirementKind.HUMAN_DECISION,
            ),
            _requirement(
                "COMPLETE_APPROVABLE_STRATEGY_CONTEXT",
                satisfied=False,
                blocker="no candidate is validated or promotion eligible",
            ),
            _requirement(
                "PAPER_LANE_ARCHITECTURE_DECISION",
                satisfied=False,
                blocker="paper-lane decision is deferred until S3 gates are satisfiable",
                kind=StageGateRequirementKind.HUMAN_DECISION,
            ),
            _requirement(
                "SECURITY_REVIEW_PASS",
                satisfied=False,
                blocker="paper integration security review has not passed",
            ),
            _requirement(
                "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL",
                satisfied=False,
                blocker="operator has not approved a specific isolated paper integration",
                kind=StageGateRequirementKind.HUMAN_DECISION,
            ),
        ),
        status=StageGateStatus.BLOCKED,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    s4_gate = StageGateReadinessRecord(
        gate_id=StageGateId("GATE-S4-LIVE-READINESS-2026-07-11"),
        stage=Stage.S4_LIVE,
        subject_ref=DomainRef("APR-FUTURE-PAPER-CONTEXT"),
        requirements=(
            _requirement(
                "S3_EXIT_PASS",
                satisfied=False,
                blocker="S3 paper/demo operations have not started",
            ),
            _requirement(
                "PAPER_STABILITY_PASS",
                satisfied=False,
                blocker="paper stability period has not been completed",
            ),
            _requirement(
                "PAPER_DIVERGENCE_ACCEPTABLE",
                satisfied=False,
                blocker="backtest-versus-paper divergence is not quantified",
            ),
            _requirement(
                "LIVE_RISK_SECURITY_PACKAGE_PASS",
                satisfied=False,
                blocker="independent live risk, kill-switch, and security evidence is absent",
            ),
            _requirement(
                "LIMITED_CAPITAL_VENUE_PROPOSAL",
                satisfied=False,
                blocker="no specific limited-capital venue proposal exists",
            ),
            _requirement(
                "HG_4_VENUE_OPERATOR_ELIGIBILITY",
                satisfied=False,
                blocker="venue and operator eligibility checks are incomplete",
                kind=StageGateRequirementKind.HUMAN_DECISION,
            ),
            _requirement(
                "HG_5_OPERATOR_APPROVAL",
                satisfied=False,
                blocker="operator has not approved limited live trading",
                kind=StageGateRequirementKind.HUMAN_DECISION,
            ),
            _requirement(
                "RESTRICTED_CREDENTIAL_GRANT",
                satisfied=False,
                blocker="no venue credential is requested or configured",
                kind=StageGateRequirementKind.CREDENTIAL_GRANT,
            ),
        ),
        status=StageGateStatus.BLOCKED,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    paper_probe = PaperLaneProposal(
        proposal_id=ApprovalId("APR-PAPER-LANE-PROBE-2026-07-11"),
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        mode=PaperLaneMode.SYNTHETIC_LOCAL_SIMULATOR,
        gate_ref=s3_gate.gate_id,
        requested_synthetic_capital=Money(Decimal("10000"), "USDT"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    divergence_probe = PaperDivergenceReport(
        report_id=ApprovalId("APR-PAPER-DIVERGENCE-PROBE-2026-07-11"),
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        backtest_run_ref=RunId("RUN-FUTURE-BACKTEST-CONTEXT"),
        paper_context_ref=DomainRef("APR-PAPER-LANE-PROBE-2026-07-11"),
        observations=(
            DivergenceObservation(
                DivergenceMetric.TOTAL_RETURN,
                Decimal("0.10"),
                Decimal("0.095"),
                Decimal("0.01"),
            ),
            DivergenceObservation(
                DivergenceMetric.FEE_TOTAL,
                Decimal("10"),
                Decimal("15"),
                Decimal("1"),
            ),
        ),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    live_probe = LiveReadinessProposal(
        proposal_id=ApprovalId("APR-LIVE-READINESS-PROBE-2026-07-11"),
        paper_context_ref=DomainRef("APR-PAPER-LANE-PROBE-2026-07-11"),
        gate_ref=s4_gate.gate_id,
        maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
        maximum_drawdown_fraction=Decimal("0.05"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    drill_probe = OperationalDrillRecord(
        drill_id=ApprovalId("APR-OPERATIONAL-DRILL-PROBE-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        kind=OperationalDrillKind.MANUAL_KILL_SWITCH,
        status=OperationalDrillStatus.PASS,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    blocked_drill_probe = OperationalDrillRecord(
        drill_id=ApprovalId("APR-CREDENTIAL-REVOCATION-DRILL-PROBE-2026-07-11"),
        stage=Stage.S4_LIVE,
        kind=OperationalDrillKind.CREDENTIAL_REVOCATION,
        status=OperationalDrillStatus.BLOCKED,
        evidence_refs=(),
        blocker="no restricted credential exists",
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ledger_initial = SyntheticLedgerEntry(
        entry_id=ApprovalId("APR-SYNTHETIC-LEDGER-ENTRY-INITIAL-2026-07-11"),
        occurred_at=CREATED_AT,
        kind=SyntheticLedgerEntryKind.INITIAL_CAPITAL,
        direction=LedgerDirection.CREDIT,
        amount=Money(Decimal("10000"), "USDT"),
        balance_after=Money(Decimal("10000"), "USDT"),
        source_ref=DomainRef("APR-PAPER-LANE-PROBE-2026-07-11"),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ledger_fee = SyntheticLedgerEntry(
        entry_id=ApprovalId("APR-SYNTHETIC-LEDGER-ENTRY-FEE-2026-07-11"),
        occurred_at=CREATED_AT,
        kind=SyntheticLedgerEntryKind.FEE,
        direction=LedgerDirection.DEBIT,
        amount=Money(Decimal("1"), "USDT"),
        balance_after=Money(Decimal("9999"), "USDT"),
        source_ref=DomainRef("APR-PAPER-DIVERGENCE-PROBE-2026-07-11"),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ledger_probe = SyntheticLedgerSnapshot(
        ledger_id=LedgerId("LEDGER-SYNTHETIC-DEMO-PROBE-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        as_of=CREATED_AT,
        entries=(ledger_initial, ledger_fee),
        balances=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    fill_policy_probe = SyntheticPaperFillPolicy(
        policy_id=ApprovalId("APR-SYNTHETIC-PAPER-FILL-POLICY-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        price_source=PaperFillPriceSource.BAR_MIDPOINT,
        fee_model=PaperFeeModel.FIXED_BPS,
        maker_fee_bps=Decimal("10"),
        taker_fee_bps=Decimal("10"),
        slippage_bps=Decimal("2"),
        max_fill_latency_seconds=60,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    account_probe = SyntheticAccountSnapshot(
        account_id=AccountId("ACCT-SYNTHETIC-DEMO-PROBE-2026-07-11"),
        ledger_ref=ledger_probe.ledger_id,
        stage=Stage.S3_PAPER_DEMO,
        as_of=CREATED_AT,
        balances=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    portfolio_probe = SyntheticPortfolioSnapshot(
        portfolio_id=PortfolioId("PF-SYNTHETIC-DEMO-PROBE-2026-07-11"),
        account_ref=account_probe.account_id,
        ledger_ref=ledger_probe.ledger_id,
        stage=Stage.S3_PAPER_DEMO,
        as_of=CREATED_AT,
        reporting_currency="USDT",
        cash=(Money(Decimal("9999"), "USDT"),),
        positions=(),
        equity=(Money(Decimal("9999"), "USDT"),),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    runtime_risk_probe = SyntheticRuntimeRiskPolicy(
        policy_id=RiskId("RISK-SYNTHETIC-RUNTIME-POLICY-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        portfolio_ref=portfolio_probe.portfolio_id,
        max_capital_at_risk=Money(Decimal("10000"), "USDT"),
        max_position_notional=Money(Decimal("2500"), "USDT"),
        max_daily_loss=Money(Decimal("250"), "USDT"),
        max_drawdown_fraction=Decimal("0.10"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    portfolio_risk_probe = SyntheticPortfolioRiskPolicy(
        policy_id=RiskId("RISK-SYNTHETIC-PORTFOLIO-POLICY-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        portfolio_ref=portfolio_probe.portfolio_id,
        max_symbol_concentration_fraction=Decimal("0.40"),
        max_correlated_exposure_fraction=Decimal("0.60"),
        max_strategy_budget_fraction=Decimal("0.25"),
        max_open_positions=8,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    strategy_budget_probe = SyntheticStrategyBudgetPolicy(
        policy_id=RiskId("RISK-SYNTHETIC-STRATEGY-BUDGET-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        portfolio_ref=portfolio_probe.portfolio_id,
        max_portfolio_fraction=Decimal("0.25"),
        max_notional=Money(Decimal("2500"), "USDT"),
        max_daily_loss=Money(Decimal("100"), "USDT"),
        max_open_positions=2,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    market_condition_probe = SyntheticMarketConditionPolicy(
        policy_id=RiskId("RISK-SYNTHETIC-MARKET-CONDITION-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        strategy_context_ref=DomainRef("SV-FUTURE-VALIDATED-CONTEXT"),
        max_market_data_age_seconds=30,
        max_quote_spread_bps=Decimal("25"),
        block_when_venue_health_degraded=True,
        require_monotonic_timestamps=True,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    credential_policy_probe = RestrictedCredentialPolicy(
        policy_id=ApprovalId("APR-RESTRICTED-CREDENTIAL-POLICY-2026-07-11"),
        stage=Stage.S4_LIVE,
        venue_family=VenueFamily("BINANCE_SPOT"),
        allowed_future_permissions=(
            CredentialPermission.READ_MARKET_DATA,
            CredentialPermission.READ_ACCOUNT,
            CredentialPermission.PLACE_SPOT_ORDERS,
            CredentialPermission.CANCEL_SPOT_ORDERS,
        ),
        max_order_notional=Money(Decimal("100"), "USDT"),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    operations_runbook_probe = PaperOperationsRunbook(
        runbook_id=ApprovalId("APR-PAPER-OPERATIONS-RUNBOOK-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=paper_probe.proposal_id,
        runtime_risk_policy_ref=runtime_risk_probe.policy_id,
        heartbeat_interval_seconds=60,
        heartbeat_timeout_seconds=180,
        log_retention_days=90,
        intervention_mode=PaperRunbookInterventionMode.MANUAL_ONLY,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    operations_event_probe = PaperOperationsEventRecord(
        event_id=ApprovalId("APR-PAPER-OPERATIONS-EVENT-HEARTBEAT-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        runbook_ref=operations_runbook_probe.runbook_id,
        occurred_at=CREATED_AT,
        kind=PaperOperationsEventKind.HEARTBEAT,
        severity=PaperOperationsEventSeverity.INFO,
        detail="probe heartbeat for future paper operations logging contract",
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    incident_probe = OperationalIncidentRecord(
        incident_id=ApprovalId("APR-OPERATIONAL-INCIDENT-PROBE-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        status=OperationalIncidentStatus.OPEN,
        severity=OperationalIncidentSeverity.CRITICAL,
        opened_at=CREATED_AT,
        summary="probe incident for future paper operations lifecycle contract",
        event_refs=(operations_event_probe.event_id,),
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    stability_probe = PaperStabilityReport(
        report_id=ApprovalId("APR-PAPER-STABILITY-PROBE-2026-07-11"),
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=paper_probe.proposal_id,
        divergence_report_ref=divergence_probe.report_id,
        runbook_ref=operations_runbook_probe.runbook_id,
        runtime_risk_policy_ref=runtime_risk_probe.policy_id,
        window_started_at=CREATED_AT,
        window_ended_at=CREATED_AT + timedelta(hours=1),
        required_observation_hours=Decimal("168"),
        observed_uptime_fraction=Decimal("0"),
        incident_count=0,
        missed_heartbeat_count=0,
        status=PaperStabilityStatus.BLOCKED,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        blocker="no active paper lane has run a stability window",
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    limited_live_risk_probe = LimitedLiveRiskPackage(
        package_id=ApprovalId("APR-LIMITED-LIVE-RISK-PACKAGE-2026-07-11"),
        stage=Stage.S4_LIVE,
        paper_stability_ref=stability_probe.report_id,
        credential_policy_ref=credential_policy_probe.policy_id,
        operations_runbook_ref=operations_runbook_probe.runbook_id,
        runtime_risk_policy_ref=runtime_risk_probe.policy_id,
        maximum_capital_at_risk=Money(Decimal("1000"), "USDT"),
        maximum_single_order_notional=Money(Decimal("100"), "USDT"),
        maximum_daily_loss=Money(Decimal("50"), "USDT"),
        kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
        status=LimitedLiveRiskPackageStatus.BLOCKED,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        blocker="S3 paper stability evidence is not complete",
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    live_runbook_probe = LiveOperationsRunbook(
        runbook_id=ApprovalId("APR-LIVE-OPERATIONS-RUNBOOK-2026-07-11"),
        stage=Stage.S4_LIVE,
        limited_live_risk_package_ref=limited_live_risk_probe.package_id,
        credential_policy_ref=credential_policy_probe.policy_id,
        heartbeat_interval_seconds=60,
        incident_response_minutes=15,
        log_retention_days=365,
        escalation_mode=LiveRunbookEscalationMode.OPERATOR_MANUAL_ONLY,
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    live_event_probe = LiveOperationsEventRecord(
        event_id=ApprovalId("APR-LIVE-OPERATIONS-EVENT-HEARTBEAT-2026-07-11"),
        stage=Stage.S4_LIVE,
        runbook_ref=live_runbook_probe.runbook_id,
        limited_live_risk_package_ref=limited_live_risk_probe.package_id,
        occurred_at=CREATED_AT,
        kind=LiveOperationsEventKind.HEARTBEAT,
        severity=LiveOperationsEventSeverity.INFO,
        detail="probe heartbeat for future limited-live operations logging contract",
        evidence_refs=(DomainRef("EV-S3S4-CONTROL-PLANE-READINESS-2026-07-11"),),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    probe_records = {
        "s3_gate": _jsonable(s3_gate),
        "s4_gate": _jsonable(s4_gate),
        "paper_lane_probe": _jsonable(paper_probe),
        "paper_divergence_probe": {
            **dict(_jsonable(divergence_probe)),
            "status": divergence_probe.status.value,
        },
        "live_readiness_probe": _jsonable(live_probe),
        "operational_drill_probe": _jsonable(drill_probe),
        "blocked_operational_drill_probe": _jsonable(blocked_drill_probe),
        "synthetic_ledger_probe": _jsonable(ledger_probe),
        "synthetic_paper_fill_policy_probe": _jsonable(fill_policy_probe),
        "synthetic_account_probe": _jsonable(account_probe),
        "synthetic_portfolio_probe": _jsonable(portfolio_probe),
        "synthetic_runtime_risk_policy_probe": _jsonable(runtime_risk_probe),
        "synthetic_portfolio_risk_policy_probe": _jsonable(portfolio_risk_probe),
        "synthetic_strategy_budget_policy_probe": _jsonable(strategy_budget_probe),
        "synthetic_market_condition_policy_probe": _jsonable(market_condition_probe),
        "restricted_credential_policy_probe": _jsonable(credential_policy_probe),
        "paper_operations_runbook_probe": _jsonable(operations_runbook_probe),
        "paper_operations_event_probe": _jsonable(operations_event_probe),
        "operational_incident_probe": _jsonable(incident_probe),
        "paper_stability_probe": _jsonable(stability_probe),
        "limited_live_risk_package_probe": _jsonable(limited_live_risk_probe),
        "live_operations_runbook_probe": _jsonable(live_runbook_probe),
        "live_operations_event_probe": _jsonable(live_event_probe),
    }
    payload = {
        "schema": "tios-s3-s4-control-plane-readiness-v1",
        "created_at": CREATED_AT.isoformat(),
        "mode": "CONTROL_PLANE_PROBE_ONLY",
        "status": "BLOCKED_BY_GATES",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "demo_orders": "DISABLED",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "active_record_counts": {
            "stage_gate_records": 0,
            "paper_lane_proposals": 0,
            "paper_divergence_reports": 0,
            "paper_fill_policies": 0,
            "operational_drill_records": 0,
            "synthetic_ledgers": 0,
            "synthetic_accounts": 0,
            "synthetic_portfolios": 0,
            "runtime_risk_policies": 0,
            "portfolio_risk_policies": 0,
            "strategy_budget_policies": 0,
            "market_condition_policies": 0,
            "restricted_credential_policies": 0,
            "paper_operations_runbooks": 0,
            "paper_operations_events": 0,
            "operational_incidents": 0,
            "durable_evidence_events": 0,
            "paper_stability_reports": 0,
            "limited_live_risk_packages": 0,
            "live_operations_runbooks": 0,
            "live_operations_events": 0,
            "live_readiness_proposals": 0,
        },
        "contract_probe_records": probe_records,
        "s3_blockers": [item.blocker for item in s3_gate.requirements if not item.satisfied],
        "s4_blockers": [item.blocker for item in s4_gate.requirements if not item.satisfied],
        "prohibited": [
            "credential_request",
            "venue_account_connection",
            "synthetic_wallet_mutation",
            "order_submit_cancel_replace",
            "paper_demo_live_activation",
            "real_money",
        ],
    }
    payload["content_sha256"] = _hash(payload)
    return payload


def write_artifacts() -> dict[str, Any]:
    payload = build_payload()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(_markdown(payload), encoding="utf-8")
    return payload | {
        "json_artifact": str(REPORT_JSON.relative_to(ROOT)),
        "markdown_artifact": str(REPORT_MD.relative_to(ROOT)),
    }


def _markdown(payload: dict[str, Any]) -> str:
    active = payload["active_record_counts"]
    s3 = "\n".join(f"- {item}" for item in payload["s3_blockers"])
    s4 = "\n".join(f"- {item}" for item in payload["s4_blockers"])
    return f"""# S3/S4 Control-Plane Readiness

Status: **{payload["status"]}**

This report validates the S3/S4 control-plane contracts as probe-only evidence.
It does not create a wallet, venue connection, credential, paper order, live order,
or real-money command.

## Capabilities

- execution authority: `{payload["execution_authority"]}`
- venue connection: `{payload["venue_connection"]}`
- demo orders: `{payload["demo_orders"]}`
- paper orders: `{payload["paper_orders"]}`
- live orders: `{payload["live_orders"]}`

## Active Records

- stage gate records: {active["stage_gate_records"]}
- paper lane proposals: {active["paper_lane_proposals"]}
- paper divergence reports: {active["paper_divergence_reports"]}
- paper fill policies: {active["paper_fill_policies"]}
- operational drill records: {active["operational_drill_records"]}
- synthetic ledgers: {active["synthetic_ledgers"]}
- synthetic accounts: {active["synthetic_accounts"]}
- synthetic portfolios: {active["synthetic_portfolios"]}
- runtime risk policies: {active["runtime_risk_policies"]}
- portfolio risk policies: {active["portfolio_risk_policies"]}
- strategy budget policies: {active["strategy_budget_policies"]}
- market condition policies: {active["market_condition_policies"]}
- restricted credential policies: {active["restricted_credential_policies"]}
- paper operations runbooks: {active["paper_operations_runbooks"]}
- paper operations events: {active["paper_operations_events"]}
- operational incidents: {active["operational_incidents"]}
- durable evidence events: {active["durable_evidence_events"]}
- paper stability reports: {active["paper_stability_reports"]}
- limited live risk packages: {active["limited_live_risk_packages"]}
- live operations runbooks: {active["live_operations_runbooks"]}
- live operations events: {active["live_operations_events"]}
- live readiness proposals: {active["live_readiness_proposals"]}

## S3 Blockers

{s3}

## S4 Blockers

{s4}

## Prohibited

{chr(10).join(f"- {item}" for item in payload["prohibited"])}
"""


def main() -> None:
    payload = write_artifacts()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "content_sha256": payload["content_sha256"],
                "json_artifact": payload["json_artifact"],
                "markdown_artifact": payload["markdown_artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
