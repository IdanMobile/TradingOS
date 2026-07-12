"""Contextual approval states for the no-money prototype."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

ApprovalState = Literal[
    "NOT_ELIGIBLE",
    "RESEARCH",
    "VALIDATION",
    "PAPER_APPROVED",
    "PAPER_ACTIVE",
    "LIMITED_LIVE_REVIEW",
    "LIMITED_LIVE_APPROVED",
    "LIVE_APPROVED",
    "PAUSED",
    "DEGRADED",
    "RETIRED",
]

LIVE_STATES = frozenset({"LIMITED_LIVE_REVIEW", "LIMITED_LIVE_APPROVED", "LIVE_APPROVED"})
HUMAN_PAPER_STATES = frozenset({"PAPER_APPROVED", "PAPER_ACTIVE"})
CURRENT_PHASE_STATES = frozenset({"NOT_ELIGIBLE", "RESEARCH", "VALIDATION", "RETIRED"})
TRANSITIONS: dict[str, frozenset[str]] = {
    "NOT_ELIGIBLE": frozenset({"RESEARCH", "RETIRED"}),
    "RESEARCH": frozenset({"VALIDATION", "RETIRED"}),
    "VALIDATION": frozenset({"PAPER_APPROVED", "RETIRED"}),
    "PAPER_APPROVED": frozenset({"PAPER_ACTIVE", "RETIRED"}),
    "PAPER_ACTIVE": frozenset({"PAUSED", "DEGRADED", "LIMITED_LIVE_REVIEW", "RETIRED"}),
    "PAUSED": frozenset({"PAPER_ACTIVE", "RETIRED"}),
    "DEGRADED": frozenset({"PAUSED", "RETIRED"}),
    "LIMITED_LIVE_REVIEW": frozenset({"LIMITED_LIVE_APPROVED", "RETIRED"}),
    "LIMITED_LIVE_APPROVED": frozenset({"LIVE_APPROVED", "PAUSED", "RETIRED"}),
    "LIVE_APPROVED": frozenset({"PAUSED", "DEGRADED", "RETIRED"}),
    "RETIRED": frozenset(),
}


class ApprovalError(ValueError):
    """Raised when a contextual approval transition is forbidden."""


@dataclass(frozen=True)
class ApprovalContext:
    strategy_version_ref: str
    market: str
    instrument: str
    timeframe: str
    config_hash: str
    environment: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in self.__dict__.values()):
            raise ApprovalError("approval identity fields must be non-empty")


@dataclass(frozen=True)
class Approval:
    approval_id: str
    context: ApprovalContext
    state: ApprovalState = "NOT_ELIGIBLE"
    evidence_refs: tuple[str, ...] = ()
    human_decision_ref: str | None = None


def transition(
    approval: Approval,
    target: ApprovalState,
    *,
    evidence_refs: tuple[str, ...],
    human_decision_ref: str | None = None,
) -> Approval:
    """Apply one S1-safe transition; all live-family states are unreachable."""
    if target not in CURRENT_PHASE_STATES:
        raise ApprovalError("paper/live approval states are unreachable in the current phase")
    if target not in TRANSITIONS[approval.state]:
        raise ApprovalError(f"forbidden transition: {approval.state} -> {target}")
    if not evidence_refs:
        raise ApprovalError("every approval transition requires evidence")
    if target in HUMAN_PAPER_STATES and not human_decision_ref:
        raise ApprovalError(f"{target} requires a human decision reference")
    return replace(
        approval,
        state=target,
        evidence_refs=evidence_refs,
        human_decision_ref=human_decision_ref,
    )
