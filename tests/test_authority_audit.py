from pathlib import Path

from tios.approval import AuthorityAuditStatus, audit_repository_authority


def test_current_repository_authority_conflict_is_machine_detected() -> None:
    root = Path(__file__).resolve().parents[1]
    audit = audit_repository_authority(root)
    assert audit.status is AuthorityAuditStatus.CONFLICT
    assert audit.blockers == ("CONTRADICTORY_DEMO_AUTHORITY_CLAIMS",)
    assert audit.allows_order_path_changes is False
    assert {claim.source for claim in audit.claims} == {
        "DECISION_LOG.md",
        "handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md",
    }


def test_missing_authority_source_fails_closed(tmp_path: Path) -> None:
    audit = audit_repository_authority(tmp_path)
    assert audit.status is AuthorityAuditStatus.INCOMPLETE
    assert audit.allows_order_path_changes is False
