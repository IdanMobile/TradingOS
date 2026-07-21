"""Fail-closed audit of contradictory repository execution-authority claims."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class AuthorityClaimState(StrEnum):
    NO_DEMO_AUTHORITY = "NO_DEMO_AUTHORITY"
    DEMO_ACTIVE = "DEMO_ACTIVE"


class AuthorityAuditStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class AuthorityClaim:
    source: str
    line: int
    precedence: int
    state: AuthorityClaimState
    excerpt: str


@dataclass(frozen=True, slots=True)
class AuthorityAudit:
    status: AuthorityAuditStatus
    claims: tuple[AuthorityClaim, ...]
    blockers: tuple[str, ...]

    @property
    def allows_order_path_changes(self) -> bool:
        return False


def _claim(
    root: Path,
    relative_path: str,
    marker: str,
    *,
    precedence: int,
    state: AuthorityClaimState,
) -> AuthorityClaim | None:
    path = root / relative_path
    if not path.is_file():
        return None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if marker in line:
            return AuthorityClaim(relative_path, line_number, precedence, state, line.strip())
    return None


def audit_repository_authority(root: Path) -> AuthorityAudit:
    """Audit the two currently contradictory controlling claims without granting authority.

    This transitional Phase-0 check is intentionally narrow. Once the operator resolves
    the conflict, it should be replaced by one canonical machine-readable authority record.
    """

    expected = (
        _claim(
            root,
            "handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md",
            "no paper/demo/live authority exists",
            precedence=100,
            state=AuthorityClaimState.NO_DEMO_AUTHORITY,
        ),
        _claim(
            root,
            "DECISION_LOG.md",
            "Demo order lane ACTIVE in execution-measurement mode",
            precedence=80,
            state=AuthorityClaimState.DEMO_ACTIVE,
        ),
    )
    claims = tuple(claim for claim in expected if claim is not None)
    if len(claims) != len(expected):
        return AuthorityAudit(
            AuthorityAuditStatus.INCOMPLETE,
            claims,
            ("AUTHORITY_SOURCE_MISSING_OR_UNRECOGNIZED",),
        )
    if len({claim.state for claim in claims}) > 1:
        return AuthorityAudit(
            AuthorityAuditStatus.CONFLICT,
            claims,
            ("CONTRADICTORY_DEMO_AUTHORITY_CLAIMS",),
        )
    return AuthorityAudit(AuthorityAuditStatus.CONSISTENT, claims, ())
