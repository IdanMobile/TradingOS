"""Strategy ingestion records + lifecycle-state guards (T-010-01, REQ-039).

specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md defines the canonical
lifecycle and required source record; this module is the minimal enforcement
of both, plus license-class gating (D-011: never import claimed profitability).
"""

from __future__ import annotations

from dataclasses import dataclass

LIFECYCLE = (
    "DISCOVERED",
    "SOURCE_CAPTURED",
    "LICENSE_CHECKED",
    "SEMANTIC_EXTRACTED",
    "AMBIGUITIES_RECORDED",
    "CANONICAL_SPEC_CREATED",
    "REFERENCE_REPRODUCED",
    "PARITY_CHECKED",
    "INTERNAL_BASELINE_RUN",
    "VALIDATION_ELIGIBLE",
)
TERMINAL_STATES = ("VALIDATION_ELIGIBLE", "REJECTED")
LICENSE_CLASSES = ("permissive", "copyleft", "proprietary", "unclear")


class LifecycleError(ValueError):
    """Disallowed lifecycle-state transition."""


def transition(current: str, target: str) -> str:
    """Guard one lifecycle-state transition; return the new state or raise.

    Only the next state in `LIFECYCLE` is reachable from a non-terminal state
    (no skipping, no reordering); `REJECTED` is reachable from any non-terminal
    state. Both `VALIDATION_ELIGIBLE` and `REJECTED` are terminal.
    """
    if current in TERMINAL_STATES:
        raise LifecycleError(f"{current} is terminal; no further transitions")
    if current not in LIFECYCLE:
        raise LifecycleError(f"unknown current state {current!r}")
    if target == "REJECTED":
        return target
    if target not in LIFECYCLE:
        raise LifecycleError(f"unknown target state {target!r}")
    if LIFECYCLE.index(target) != LIFECYCLE.index(current) + 1:
        raise LifecycleError(f"cannot skip/reorder: {current} -> {target} is not the next step")
    return target


@dataclass(frozen=True)
class SourceRecord:
    """Required source record (workflow spec `Required source record`)."""

    source_id: str
    source_class: str
    url: str
    title: str
    author: str
    published_at: str
    retrieved_at: str
    license: str
    version_or_commit: str
    market_claimed: str
    timeframe_claimed: str
    profit_claims_inherited: bool = False

    def __post_init__(self) -> None:
        if self.profit_claims_inherited:
            raise ValueError("profit_claims_inherited must be false (D-011)")


@dataclass(frozen=True)
class LicenseRecord:
    source_id: str
    license_class: str  # permissive | copyleft | proprietary | unclear
    license_name: str
    evidence_url: str

    def __post_init__(self) -> None:
        if self.license_class not in LICENSE_CLASSES:
            raise ValueError(f"unknown license_class {self.license_class!r}")


def license_gate(license_class: str) -> dict[str, bool]:
    """Gate what a license class permits.

    `unclear`/`proprietary` block reuse of source *code*; spec extraction from
    a published *description* may still proceed with a note, since it is not
    a code copy (SKILL_STRATEGY_SOURCE_INGESTOR step 2).
    """
    if license_class not in LICENSE_CLASSES:
        raise ValueError(f"unknown license_class {license_class!r}")
    return {
        "code_reuse_allowed": license_class in ("permissive", "copyleft"),
        "spec_extraction_allowed": True,
        "requires_attribution": license_class == "copyleft",
    }


@dataclass(frozen=True)
class AmbiguityRecord:
    source_id: str
    ambiguities: tuple[str, ...]
    justification_if_empty: str | None = None

    def __post_init__(self) -> None:
        if not self.ambiguities and not self.justification_if_empty:
            raise ValueError("ambiguities must be non-empty or justified (seed batch spec)")
