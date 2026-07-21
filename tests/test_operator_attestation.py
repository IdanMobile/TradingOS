import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tios.approval.attestation import (
    DEFAULT_PATH,
    AttestationError,
    authorizes,
    load,
    template,
    within_envelope,
)

FILLED = {
    "schema_version": 1,
    "venue": "OKX",
    "account_eligibility_confirmed": True,
    "product_availability_confirmed": True,
    "api_trading_permissions": ["spot_trade"],
    "automated_trading_terms_reviewed": True,
    "fee_tier": "VIP0",
    "funding_path_documented": True,
    "credential_isolation_process_ref": "docs/security/CREDENTIAL_ISOLATION.md",
    "max_capital": 5000.0,
    "max_drawdown_fraction": 0.15,
    "tax_workflow_ref": "docs/product/TAX_WORKFLOW.md",
    "attested_by": "operator",
    "attested_at": "2026-07-20T00:00:00+00:00",
    "kill_switch_conditions": ["drawdown>15%", "reconciliation_mismatch"],
}


def _write(root: Path, **overrides: object) -> Path:
    target = root / DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({**FILLED, **overrides}), encoding="utf-8")
    return target


def test_absent_attestation_loads_as_none(tmp_path: Path) -> None:
    assert load(tmp_path) is None


def test_offline_states_need_no_attestation(tmp_path: Path) -> None:
    """Research and validation involve no venue, capital, or counterparty."""
    for state in ("RESEARCH", "VALIDATION", "NOT_ELIGIBLE"):
        assert authorizes(None, state).authorized


def test_paper_state_is_blocked_without_attestation() -> None:
    verdict = authorizes(None, "PAPER_ACTIVE")
    assert not verdict.authorized
    assert "OPERATOR_ATTESTATION_ABSENT" in verdict.blockers


def test_template_is_entirely_unset_and_unloadable(tmp_path: Path) -> None:
    """An agent cannot pre-fill operator facts; the template refuses to load."""
    target = tmp_path / DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(template()), encoding="utf-8")
    with pytest.raises(AttestationError, match="unset required facts"):
        load(tmp_path)


def test_filled_attestation_authorizes_paper(tmp_path: Path) -> None:
    _write(tmp_path)
    attestation = load(tmp_path)
    assert attestation is not None
    verdict = authorizes(attestation, "PAPER_ACTIVE", now=datetime(2026, 7, 21, tzinfo=UTC))
    assert verdict.authorized, verdict.blockers


def test_demo_attestation_does_not_escalate_to_live(tmp_path: Path) -> None:
    """Live authority is an explicit opt-in, never inherited from a demo attestation."""
    _write(tmp_path)
    attestation = load(tmp_path)
    verdict = authorizes(attestation, "LIVE_APPROVED", now=datetime(2026, 7, 21, tzinfo=UTC))
    assert not verdict.authorized
    assert "LIVE_AUTHORITY_NOT_ATTESTED" in verdict.blockers


def test_explicit_live_opt_in_authorizes_live(tmp_path: Path) -> None:
    _write(tmp_path, authorizes_live=True)
    attestation = load(tmp_path)
    verdict = authorizes(attestation, "LIVE_APPROVED", now=datetime(2026, 7, 21, tzinfo=UTC))
    assert verdict.authorized, verdict.blockers


def test_expired_attestation_is_not_continuing_consent(tmp_path: Path) -> None:
    """Venue terms drift; a stale attestation reads as absent, not as ongoing approval."""
    _write(tmp_path)
    attestation = load(tmp_path)
    assert attestation is not None
    later = attestation.attested_at + timedelta(days=91)
    verdict = authorizes(attestation, "PAPER_ACTIVE", now=later)
    assert not verdict.authorized
    assert "OPERATOR_ATTESTATION_EXPIRED" in verdict.blockers


def test_missing_kill_switch_blocks_activation(tmp_path: Path) -> None:
    _write(tmp_path, kill_switch_conditions=[])
    verdict = authorizes(load(tmp_path), "PAPER_ACTIVE", now=datetime(2026, 7, 21, tzinfo=UTC))
    assert not verdict.authorized
    assert "KILL_SWITCH_CONDITIONS_NOT_DECLARED" in verdict.blockers


def test_invalid_limits_are_blocked(tmp_path: Path) -> None:
    _write(tmp_path, max_capital=0.0, max_drawdown_fraction=1.5)
    verdict = authorizes(load(tmp_path), "PAPER_ACTIVE", now=datetime(2026, 7, 21, tzinfo=UTC))
    assert not verdict.authorized
    assert "CAPITAL_LIMIT_NOT_SET" in verdict.blockers
    assert "DRAWDOWN_LIMIT_INVALID" in verdict.blockers


def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, attested_at="2026-07-20T00:00:00")
    with pytest.raises(AttestationError, match="must include a timezone"):
        load(tmp_path)


def test_envelope_halts_on_capital_breach(tmp_path: Path) -> None:
    _write(tmp_path)
    verdict = within_envelope(
        load(tmp_path), deployed_capital=5001.0, observed_drawdown_fraction=0.01
    )
    assert not verdict.authorized
    assert "CAPITAL_LIMIT_BREACHED" in verdict.blockers


def test_envelope_halts_on_drawdown_breach(tmp_path: Path) -> None:
    _write(tmp_path)
    verdict = within_envelope(
        load(tmp_path), deployed_capital=100.0, observed_drawdown_fraction=0.16
    )
    assert not verdict.authorized
    assert "DRAWDOWN_LIMIT_BREACHED" in verdict.blockers


def test_envelope_allows_operation_within_limits(tmp_path: Path) -> None:
    _write(tmp_path, attested_at=datetime.now(tz=UTC).isoformat())
    verdict = within_envelope(
        load(tmp_path), deployed_capital=100.0, observed_drawdown_fraction=0.01
    )
    assert verdict.authorized, verdict.blockers


def test_attestation_carries_no_credentials(tmp_path: Path) -> None:
    """The file asserts that isolation exists; it must never hold the secret itself.

    Checks field names rather than raw text: the template's comment legitimately warns
    against secrets, and matching prose would flag that warning as a violation.
    """
    fields = {name.lower() for name in template()}
    for forbidden in ("api_key", "api_secret", "secret", "password", "token", "private_key"):
        assert not any(forbidden in name for name in fields), f"{forbidden} must not be a field"
    # The one credential-adjacent field holds a documentation path, not a value.
    assert template()["credential_isolation_process_ref"] == "UNSET"
