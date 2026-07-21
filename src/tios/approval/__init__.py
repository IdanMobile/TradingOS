"""Contextual approval model; no runtime order authority."""

from tios.approval.authority_audit import (
    AuthorityAudit,
    AuthorityAuditStatus,
    AuthorityClaim,
    AuthorityClaimState,
    audit_repository_authority,
)
from tios.approval.history import (
    ApprovalHistory,
    ApprovalTransitionEvent,
    GatedApprovalEvidence,
    HumanDecisionOutcome,
    HumanDecisionRecord,
    apply_gated_transition,
    resolve_stage_gate,
)
from tios.approval.state import (
    CURRENT_PHASE_STATES,
    LIVE_STATES,
    Approval,
    ApprovalContext,
    ApprovalError,
    ApprovalState,
    transition,
)

__all__ = [
    "AuthorityAudit",
    "AuthorityAuditStatus",
    "AuthorityClaim",
    "AuthorityClaimState",
    "LIVE_STATES",
    "CURRENT_PHASE_STATES",
    "Approval",
    "ApprovalContext",
    "ApprovalError",
    "ApprovalState",
    "ApprovalHistory",
    "ApprovalTransitionEvent",
    "GatedApprovalEvidence",
    "HumanDecisionOutcome",
    "HumanDecisionRecord",
    "apply_gated_transition",
    "audit_repository_authority",
    "resolve_stage_gate",
    "transition",
]
