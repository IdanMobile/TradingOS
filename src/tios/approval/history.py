"""Immutable future approval history guarded by typed S3/S4 evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from tios.trading_domain import (
    ApprovalId,
    DomainRef,
    RiskId,
    Stage,
    StageGateId,
    StageGateReadinessRecord,
    StageGateRequirementKind,
    StageGateStatus,
)

from .state import TRANSITIONS, Approval, ApprovalError, ApprovalState

PAPER_FAMILY = frozenset({"PAPER_APPROVED", "PAPER_ACTIVE"})
LIVE_FAMILY = frozenset({"LIMITED_LIVE_REVIEW", "LIMITED_LIVE_APPROVED", "LIVE_APPROVED"})


class HumanDecisionOutcome(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class HumanDecisionRecord:
    decision_id: ApprovalId
    gate_id: StageGateId
    subject_ref: DomainRef
    requirement_code: str
    decision: HumanDecisionOutcome
    decided_by: DomainRef
    decided_at: datetime
    evidence_refs: tuple[DomainRef, ...]
    review_rule: str
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if (
            not self.requirement_code.strip()
            or not self.review_rule.strip()
            or not self.evidence_refs
        ):
            raise ApprovalError("human decisions require code, review rule, and evidence")
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ApprovalError("human decision timestamps must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise ApprovalError("human decision expiry must be timezone-aware")
            if self.expires_at <= self.decided_at:
                raise ApprovalError("human decision expiry must follow the decision")


def resolve_stage_gate(
    gate: StageGateReadinessRecord,
    decisions: tuple[HumanDecisionRecord, ...],
    *,
    evaluated_at: datetime,
) -> StageGateReadinessRecord:
    """Resolve human requirements by exact gate, subject, code, outcome, and expiry."""
    requirements = []
    for requirement in gate.requirements:
        if requirement.kind is not StageGateRequirementKind.HUMAN_DECISION:
            requirements.append(requirement)
            continue
        matching = [
            decision
            for decision in decisions
            if decision.gate_id == gate.gate_id
            and decision.subject_ref == gate.subject_ref
            and decision.requirement_code == requirement.code
            and decision.decision is HumanDecisionOutcome.APPROVE
            and (decision.expires_at is None or decision.expires_at > evaluated_at)
        ]
        requirements.append(
            replace(
                requirement,
                satisfied=bool(matching),
                evidence_refs=tuple(DomainRef(str(item.decision_id)) for item in matching),
                blocker=None
                if matching
                else "matching approved human decision is absent or expired",
            )
        )
    all_satisfied = all(item.satisfied for item in requirements)
    non_human_satisfied = all(
        item.satisfied
        for item in requirements
        if item.kind is not StageGateRequirementKind.HUMAN_DECISION
    )
    status = (
        StageGateStatus.APPROVED
        if all_satisfied
        else StageGateStatus.READY_FOR_OPERATOR_DECISION
        if non_human_satisfied
        else StageGateStatus.BLOCKED
    )
    return replace(gate, requirements=tuple(requirements), status=status, created_at=evaluated_at)


@dataclass(frozen=True, slots=True)
class GatedApprovalEvidence:
    gate: StageGateReadinessRecord
    validation_ref: DomainRef
    risk_refs: tuple[RiskId, ...]
    security_review_ref: DomainRef
    human_decision_ref: ApprovalId
    human_decisions: tuple[HumanDecisionRecord, ...]
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.gate.status is not StageGateStatus.APPROVED:
            raise ApprovalError("gated approval requires an approved stage gate")
        if not self.risk_refs or len(set(self.risk_refs)) != len(self.risk_refs):
            raise ApprovalError("gated approval requires unique risk evidence")
        resolved = resolve_stage_gate(
            self.gate,
            self.human_decisions,
            evaluated_at=self.evaluated_at,
        )
        if resolved.status is not StageGateStatus.APPROVED:
            raise ApprovalError("gated approval human decisions do not resolve the stage gate")
        if self.human_decision_ref not in {item.decision_id for item in self.human_decisions}:
            raise ApprovalError("gated approval human decision reference is not retained")


@dataclass(frozen=True, slots=True)
class ApprovalTransitionEvent:
    event_id: ApprovalId
    approval_id: str
    from_state: ApprovalState
    to_state: ApprovalState
    transitioned_at: datetime
    gate_ref: StageGateId
    validation_ref: DomainRef
    risk_refs: tuple[RiskId, ...]
    security_review_ref: DomainRef
    human_decision_ref: ApprovalId


@dataclass(frozen=True, slots=True)
class ApprovalHistory:
    approval: Approval
    events: tuple[ApprovalTransitionEvent, ...]
    initial_state: ApprovalState = "NOT_ELIGIBLE"

    def __post_init__(self) -> None:
        state = self.initial_state
        previous_at: datetime | None = None
        for event in self.events:
            if event.approval_id != self.approval.approval_id or event.from_state != state:
                raise ApprovalError("approval history contains a broken transition chain")
            if previous_at is not None and event.transitioned_at <= previous_at:
                raise ApprovalError("approval history timestamps must strictly advance")
            if event.to_state not in TRANSITIONS[event.from_state]:
                raise ApprovalError("approval history contains a forbidden transition")
            state = event.to_state
            previous_at = event.transitioned_at
        if state != self.approval.state:
            raise ApprovalError("approval history final state does not match approval")


def apply_gated_transition(
    approval: Approval,
    target: ApprovalState,
    *,
    evidence: GatedApprovalEvidence,
    transitioned_at: datetime,
) -> tuple[Approval, ApprovalTransitionEvent]:
    """Apply one modeled S3/S4 transition; no execution capability is attached."""
    if target not in TRANSITIONS[approval.state]:
        raise ApprovalError(f"forbidden transition: {approval.state} -> {target}")
    expected_stage = _expected_stage(approval.state, target)
    if evidence.gate.stage is not expected_stage:
        raise ApprovalError(f"{target} requires an approved {expected_stage.value} gate")
    if str(evidence.gate.subject_ref) != approval.context.strategy_version_ref:
        raise ApprovalError("approval gate subject does not match strategy context")
    combined_refs = (
        str(evidence.validation_ref),
        *(str(item) for item in evidence.risk_refs),
        str(evidence.security_review_ref),
        str(evidence.gate.gate_id),
    )
    next_approval = replace(
        approval,
        state=target,
        evidence_refs=tuple(combined_refs),
        human_decision_ref=str(evidence.human_decision_ref),
    )
    digest = hashlib.sha256(
        f"{approval.approval_id}|{approval.state}|{target}|{transitioned_at.isoformat()}".encode()
    ).hexdigest()[:24]
    event = ApprovalTransitionEvent(
        event_id=ApprovalId(f"APR-transition-{digest}"),
        approval_id=approval.approval_id,
        from_state=approval.state,
        to_state=target,
        transitioned_at=transitioned_at,
        gate_ref=evidence.gate.gate_id,
        validation_ref=evidence.validation_ref,
        risk_refs=evidence.risk_refs,
        security_review_ref=evidence.security_review_ref,
        human_decision_ref=evidence.human_decision_ref,
    )
    return next_approval, event


def _expected_stage(current: ApprovalState, target: ApprovalState) -> Stage:
    if target in PAPER_FAMILY or (
        target in {"PAUSED", "DEGRADED", "RETIRED"} and current in PAPER_FAMILY
    ):
        return Stage.S3_PAPER_DEMO
    if target in LIVE_FAMILY or (
        target in {"PAUSED", "DEGRADED", "RETIRED"} and current in LIVE_FAMILY
    ):
        return Stage.S4_LIVE
    raise ApprovalError(f"{target} is not a gated S3/S4 transition")
