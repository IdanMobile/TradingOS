from dataclasses import replace
from datetime import UTC, datetime

import pytest

from tios.approval import (
    LIVE_STATES,
    Approval,
    ApprovalContext,
    ApprovalError,
    ApprovalHistory,
    GatedApprovalEvidence,
    HumanDecisionOutcome,
    HumanDecisionRecord,
    apply_gated_transition,
    transition,
)
from tios.trading_domain import (
    ApprovalId,
    CreatorType,
    DomainRef,
    Provenance,
    RiskId,
    Stage,
    StageGateId,
    StageGateReadinessRecord,
    StageGateRequirement,
    StageGateRequirementKind,
    StageGateStatus,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
PROVENANCE = Provenance((DomainRef("EV-approval-gate"),))


def _approval() -> Approval:
    return Approval(
        approval_id="APR-001",
        context=ApprovalContext(
            strategy_version_ref="SV-001",
            market="crypto_spot",
            instrument="BTC/USDT",
            timeframe="15m",
            config_hash="sha256:abc",
            environment="research",
        ),
    )


def test_contextual_approval_requires_evidence_and_ordered_transitions() -> None:
    research = transition(_approval(), "RESEARCH", evidence_refs=("EV-001",))
    validation = transition(research, "VALIDATION", evidence_refs=("VAL-001",))
    with pytest.raises(ApprovalError, match="unreachable"):
        transition(validation, "PAPER_APPROVED", evidence_refs=("VAL-001",))


def test_live_states_are_unreachable_in_current_phase() -> None:
    approval = _approval()
    for state in LIVE_STATES:
        with pytest.raises(ApprovalError, match="unreachable"):
            transition(approval, state, evidence_refs=("EV-001",), human_decision_ref="HG-X")


def test_paper_states_are_unreachable_through_current_phase_api() -> None:
    validation = transition(
        transition(_approval(), "RESEARCH", evidence_refs=("EV-001",)),
        "VALIDATION",
        evidence_refs=("VAL-001",),
    )
    with pytest.raises(ApprovalError, match="paper/live approval states are unreachable"):
        transition(
            validation,
            "PAPER_APPROVED",
            evidence_refs=("VAL-001",),
            human_decision_ref="APR-human-paper",
        )


def test_forbidden_skip_and_empty_evidence_fail_closed() -> None:
    with pytest.raises(ApprovalError, match="forbidden"):
        transition(_approval(), "VALIDATION", evidence_refs=("VAL-001",))
    with pytest.raises(ApprovalError, match="requires evidence"):
        transition(_approval(), "RESEARCH", evidence_refs=())


def approved_gate(stage: Stage) -> StageGateReadinessRecord:
    human_code = "HG_3_APPROVED" if stage is Stage.S3_PAPER_DEMO else "HG_5_OPERATOR_APPROVAL"
    evidence_codes = (
        (
            "S2_EXIT_PASS",
            "COMPLETE_APPROVABLE_STRATEGY_CONTEXT",
            "SECURITY_REVIEW_PASS",
        )
        if stage is Stage.S3_PAPER_DEMO
        else (
            "S3_EXIT_PASS",
            "PAPER_STABILITY_PASS",
            "PAPER_DIVERGENCE_ACCEPTABLE",
            "LIVE_RISK_SECURITY_PACKAGE_PASS",
            "LIMITED_CAPITAL_VENUE_PROPOSAL",
            "RESTRICTED_CREDENTIAL_GRANT",
        )
    )
    extra_human_codes = (
        ("PAPER_LANE_ARCHITECTURE_DECISION", "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL")
        if stage is Stage.S3_PAPER_DEMO
        else ("HG_4_VENUE_OPERATOR_ELIGIBILITY",)
    )
    return StageGateReadinessRecord(
        gate_id=StageGateId(f"GATE-{stage.value}-approved"),
        stage=stage,
        subject_ref=DomainRef("SV-001"),
        requirements=(
            StageGateRequirement(
                code=human_code,
                kind=StageGateRequirementKind.HUMAN_DECISION,
                satisfied=True,
                evidence_refs=(DomainRef("APR-human-gate"),),
            ),
            *tuple(
                StageGateRequirement(
                    code=code,
                    kind=StageGateRequirementKind.EVIDENCE,
                    satisfied=True,
                    evidence_refs=(DomainRef(f"EV-{code.lower()}"),),
                )
                for code in evidence_codes
            ),
            *tuple(
                StageGateRequirement(
                    code=code,
                    kind=StageGateRequirementKind.HUMAN_DECISION,
                    satisfied=True,
                    evidence_refs=(DomainRef(f"APR-{code.lower()}"),),
                )
                for code in extra_human_codes
            ),
        ),
        status=StageGateStatus.APPROVED,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def gated_evidence(stage: Stage) -> GatedApprovalEvidence:
    gate = approved_gate(stage)
    decisions = tuple(
        HumanDecisionRecord(
            decision_id=ApprovalId(f"APR-decision-{requirement.code.lower()}"),
            gate_id=gate.gate_id,
            subject_ref=gate.subject_ref,
            requirement_code=requirement.code,
            decision=HumanDecisionOutcome.APPROVE,
            decided_by=DomainRef("APR-operator-owner"),
            decided_at=NOW,
            evidence_refs=(DomainRef("EV-human-decision"),),
            review_rule="review on material context change",
        )
        for requirement in gate.requirements
        if requirement.kind is StageGateRequirementKind.HUMAN_DECISION
    )
    return GatedApprovalEvidence(
        gate=gate,
        validation_ref=DomainRef("VAL-001"),
        risk_refs=(RiskId("RISK-paper-approved"),),
        security_review_ref=DomainRef("EV-security-review"),
        human_decision_ref=decisions[0].decision_id,
        human_decisions=decisions,
        evaluated_at=NOW,
    )


def test_gated_approval_transition_retains_typed_history_without_execution() -> None:
    validation = Approval(
        approval_id="APR-001",
        context=_approval().context,
        state="VALIDATION",
        evidence_refs=("VAL-001",),
    )
    evidence = gated_evidence(Stage.S3_PAPER_DEMO)
    paper, event = apply_gated_transition(
        validation,
        "PAPER_APPROVED",
        evidence=evidence,
        transitioned_at=NOW,
    )
    assert paper.state == "PAPER_APPROVED"
    assert event.from_state == "VALIDATION"
    assert event.to_state == "PAPER_APPROVED"
    history = ApprovalHistory(paper, (event,), initial_state="VALIDATION")
    assert history.approval == paper

    with pytest.raises(ApprovalError, match="requires an approved S3_PAPER_DEMO gate"):
        apply_gated_transition(
            paper,
            "PAPER_ACTIVE",
            evidence=gated_evidence(Stage.S4_LIVE),
            transitioned_at=NOW,
        )


def test_gated_approval_rejects_missing_or_expired_human_decisions() -> None:
    valid = gated_evidence(Stage.S3_PAPER_DEMO)
    with pytest.raises(ApprovalError, match="do not resolve"):
        replace(valid, human_decisions=())
    expiring = replace(
        valid.human_decisions[0],
        expires_at=NOW.replace(year=2027),
    )
    with pytest.raises(ApprovalError, match="do not resolve"):
        replace(
            valid,
            human_decisions=(expiring, *valid.human_decisions[1:]),
            evaluated_at=NOW.replace(year=2028),
        )
