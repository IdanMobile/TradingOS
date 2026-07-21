"""Operator attestation: the facts only a human can supply, supplied once.

Ten items in `MISSING_AND_OPEN_ITEMS.md` are marked human-only before live trading —
account eligibility, product availability, API permissions, automated-trading terms,
fee tier, funding path, credential isolation, capital and drawdown limits, tax workflow,
and final approval. None of them are computable from market data; they are facts about
the operator and their accounts.

Historically that made every advancement an interactive approval. This module turns them
into one signed, expiring attestation that the engine enforces predicates against
automatically. The operator states the facts once; the system runs unattended inside the
envelope those facts define.

Two properties matter:

*This file never holds credentials.* It asserts that a credential-isolation process exists
and where it is documented. It does not hold keys, secrets, or account numbers. A reader of
this file gains no access to anything.

*Attestations expire.* Venue terms, fee tiers, and product availability drift. A stale
attestation is treated as absent rather than as continuing consent, because the operator
attested to conditions that may no longer hold.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_PATH = Path("ops") / "OPERATOR_ATTESTATION.json"
DEFAULT_VALIDITY_DAYS = 90
UNSET = "UNSET"

# Every fact the operator must state before any capital-bearing stage is reachable.
# Order matches MISSING_AND_OPEN_ITEMS.md "Human-only before live trading".
REQUIRED_FACTS = (
    "venue",
    "account_eligibility_confirmed",
    "product_availability_confirmed",
    "api_trading_permissions",
    "automated_trading_terms_reviewed",
    "fee_tier",
    "funding_path_documented",
    "credential_isolation_process_ref",
    "max_capital",
    "max_drawdown_fraction",
    "tax_workflow_ref",
    "attested_by",
)

# Stages this attestation can authorize. Research and validation never require it —
# offline work needs no operator facts.
DEMO_STATES = frozenset({"PAPER_APPROVED", "PAPER_ACTIVE"})
LIVE_STATES = frozenset({"LIMITED_LIVE_REVIEW", "LIMITED_LIVE_APPROVED", "LIVE_APPROVED"})


class AttestationError(RuntimeError):
    """Raised when an attestation is malformed or asked to authorize beyond its scope."""


@dataclass(frozen=True)
class AttestationVerdict:
    authorized: bool
    target_state: str
    blockers: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "target_state": self.target_state,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class OperatorAttestation:
    venue: str
    account_eligibility_confirmed: bool
    product_availability_confirmed: bool
    api_trading_permissions: tuple[str, ...]
    automated_trading_terms_reviewed: bool
    fee_tier: str
    funding_path_documented: bool
    credential_isolation_process_ref: str
    max_capital: float
    max_drawdown_fraction: float
    tax_workflow_ref: str
    attested_by: str
    attested_at: datetime
    expires_at: datetime
    authorizes_live: bool = False
    kill_switch_conditions: tuple[str, ...] = field(default_factory=tuple)

    def expired(self, now: datetime | None = None) -> bool:
        return (now or utc_now()) >= self.expires_at

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "venue": self.venue,
            "account_eligibility_confirmed": self.account_eligibility_confirmed,
            "product_availability_confirmed": self.product_availability_confirmed,
            "api_trading_permissions": list(self.api_trading_permissions),
            "automated_trading_terms_reviewed": self.automated_trading_terms_reviewed,
            "fee_tier": self.fee_tier,
            "funding_path_documented": self.funding_path_documented,
            "credential_isolation_process_ref": self.credential_isolation_process_ref,
            "max_capital": self.max_capital,
            "max_drawdown_fraction": self.max_drawdown_fraction,
            "tax_workflow_ref": self.tax_workflow_ref,
            "attested_by": self.attested_by,
            "attested_at": self.attested_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "authorizes_live": self.authorizes_live,
            "kill_switch_conditions": list(self.kill_switch_conditions),
        }


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def load(root: Path, path: Path | None = None) -> OperatorAttestation | None:
    """Read the attestation, or None when it is absent.

    Absent is a normal state, not an error: offline research runs without any operator
    facts. Callers translate None into blockers only for stages that need it.
    """
    target = root / (path or DEFAULT_PATH)
    if not target.is_file():
        return None

    payload = json.loads(target.read_text(encoding="utf-8"))
    unset = [name for name in REQUIRED_FACTS if _is_unset(payload.get(name))]
    if unset:
        raise AttestationError(
            f"attestation at {target} has unset required facts: {sorted(unset)}; "
            "the operator must supply these before any capital-bearing stage is reachable"
        )

    attested_at = _timestamp(payload, "attested_at")
    expires_at = (
        _timestamp(payload, "expires_at")
        if payload.get("expires_at")
        else attested_at + timedelta(days=DEFAULT_VALIDITY_DAYS)
    )

    return OperatorAttestation(
        venue=str(payload["venue"]),
        account_eligibility_confirmed=bool(payload["account_eligibility_confirmed"]),
        product_availability_confirmed=bool(payload["product_availability_confirmed"]),
        api_trading_permissions=tuple(payload["api_trading_permissions"]),
        automated_trading_terms_reviewed=bool(payload["automated_trading_terms_reviewed"]),
        fee_tier=str(payload["fee_tier"]),
        funding_path_documented=bool(payload["funding_path_documented"]),
        credential_isolation_process_ref=str(payload["credential_isolation_process_ref"]),
        max_capital=float(payload["max_capital"]),
        max_drawdown_fraction=float(payload["max_drawdown_fraction"]),
        tax_workflow_ref=str(payload["tax_workflow_ref"]),
        attested_by=str(payload["attested_by"]),
        attested_at=attested_at,
        expires_at=expires_at,
        authorizes_live=bool(payload.get("authorizes_live", False)),
        kill_switch_conditions=tuple(payload.get("kill_switch_conditions", ())),
    )


def authorizes(
    attestation: OperatorAttestation | None,
    target_state: str,
    *,
    now: datetime | None = None,
) -> AttestationVerdict:
    """Decide whether the operator's standing facts authorize a target approval state.

    Research and validation states need no attestation — offline work involves no venue,
    no capital, and no counterparty. Everything from paper onward does.
    """
    if target_state not in DEMO_STATES | LIVE_STATES:
        return AttestationVerdict(True, target_state)

    if attestation is None:
        return AttestationVerdict(False, target_state, ("OPERATOR_ATTESTATION_ABSENT",))

    blockers: list[str] = []
    if attestation.expired(now):
        blockers.append("OPERATOR_ATTESTATION_EXPIRED")
    if not attestation.account_eligibility_confirmed:
        blockers.append("ACCOUNT_ELIGIBILITY_NOT_CONFIRMED")
    if not attestation.product_availability_confirmed:
        blockers.append("PRODUCT_AVAILABILITY_NOT_CONFIRMED")
    if not attestation.automated_trading_terms_reviewed:
        blockers.append("AUTOMATED_TRADING_TERMS_NOT_REVIEWED")
    if not attestation.funding_path_documented:
        blockers.append("FUNDING_PATH_NOT_DOCUMENTED")
    if attestation.max_capital <= 0:
        blockers.append("CAPITAL_LIMIT_NOT_SET")
    if not 0 < attestation.max_drawdown_fraction <= 1:
        blockers.append("DRAWDOWN_LIMIT_INVALID")
    if not attestation.kill_switch_conditions:
        blockers.append("KILL_SWITCH_CONDITIONS_NOT_DECLARED")

    # Live authority is a separate, explicit opt-in. An attestation covering a demo lane
    # never silently escalates into real-money authority just because it exists.
    if target_state in LIVE_STATES and not attestation.authorizes_live:
        blockers.append("LIVE_AUTHORITY_NOT_ATTESTED")

    return AttestationVerdict(not blockers, target_state, tuple(blockers))


def within_envelope(
    attestation: OperatorAttestation | None,
    *,
    deployed_capital: float,
    observed_drawdown_fraction: float,
) -> AttestationVerdict:
    """Check live operation against the attested envelope.

    This is the runtime half: `authorizes` gates entry into a stage, this gates staying
    there. Breaching either limit is a halt condition, not a warning.
    """
    if attestation is None:
        return AttestationVerdict(False, "ENVELOPE", ("OPERATOR_ATTESTATION_ABSENT",))

    blockers: list[str] = []
    if deployed_capital > attestation.max_capital:
        blockers.append("CAPITAL_LIMIT_BREACHED")
    if observed_drawdown_fraction > attestation.max_drawdown_fraction:
        blockers.append("DRAWDOWN_LIMIT_BREACHED")
    if attestation.expired():
        blockers.append("OPERATOR_ATTESTATION_EXPIRED")
    return AttestationVerdict(not blockers, "ENVELOPE", tuple(blockers))


def template() -> dict[str, Any]:
    """An unfilled attestation. Every operator fact is UNSET by construction.

    The template is deliberately not fillable by an agent: these are assertions about a
    human's accounts and legal position, and a plausible-looking guess is worse than a
    blank because it reads as confirmed.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "_comment": (
            "Operator-supplied facts. Replace every UNSET value. This file must never "
            "contain API keys, secrets, or account numbers - only assertions about them."
        ),
        "venue": UNSET,
        "account_eligibility_confirmed": UNSET,
        "product_availability_confirmed": UNSET,
        "api_trading_permissions": UNSET,
        "automated_trading_terms_reviewed": UNSET,
        "fee_tier": UNSET,
        "funding_path_documented": UNSET,
        "credential_isolation_process_ref": UNSET,
        "max_capital": UNSET,
        "max_drawdown_fraction": UNSET,
        "tax_workflow_ref": UNSET,
        "attested_by": UNSET,
        "attested_at": UNSET,
        "expires_at": None,
        "authorizes_live": False,
        "kill_switch_conditions": [],
    }


def _is_unset(value: Any) -> bool:
    return value is None or value == UNSET or (isinstance(value, str) and not value.strip())


def _timestamp(payload: dict[str, Any], key: str) -> datetime:
    raw = payload.get(key)
    if _is_unset(raw):
        raise AttestationError(f"attestation field {key!r} is required")
    parsed = datetime.fromisoformat(str(raw))
    if parsed.tzinfo is None:
        raise AttestationError(f"attestation field {key!r} must include a timezone")
    return parsed.astimezone(UTC)
