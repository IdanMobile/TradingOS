import pytest

from tios.approval import LIVE_STATES, Approval, ApprovalContext, ApprovalError, transition


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
    with pytest.raises(ApprovalError, match="human decision"):
        transition(validation, "PAPER_APPROVED", evidence_refs=("VAL-001",))


def test_live_states_are_unreachable_in_current_phase() -> None:
    approval = _approval()
    for state in LIVE_STATES:
        with pytest.raises(ApprovalError, match="unreachable"):
            transition(approval, state, evidence_refs=("EV-001",), human_decision_ref="HG-X")


def test_forbidden_skip_and_empty_evidence_fail_closed() -> None:
    with pytest.raises(ApprovalError, match="forbidden"):
        transition(_approval(), "VALIDATION", evidence_refs=("VAL-001",))
    with pytest.raises(ApprovalError, match="requires evidence"):
        transition(_approval(), "RESEARCH", evidence_refs=())
