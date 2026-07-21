"""Global trial budget and pre-registration enforcement.

Multiple-testing thresholds are only meaningful when the trial count they deflate
against is the *true* number of searches performed. `ScorecardEvidence` carries a
`declared_trial_count`, but a caller can declare three trials after searching three
thousand: the declaration is self-reported and nothing cross-checks it.

This module is that cross-check. Every family pre-registers its search space before
execution, every evaluated trial is appended to a persistent ledger, and a declared
trial count is verified against the ledger rather than trusted. Unregistered searches
cannot be scored at all.

Fail-closed throughout: a missing registration, an unreadable ledger, or a declared
count that disagrees with the ledger produces a blocker, never a pass.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
LEDGER_DIRNAME = Path("artifacts") / "validation" / "trial_budget"
REGISTRY_FILENAME = "registrations.jsonl"
LEDGER_FILENAME = "trials.jsonl"

# Fields a family must pin before it may run. Absent any of these the search is
# not reproducible and its statistics cannot be interpreted after the fact.
REQUIRED_REGISTRATION_FIELDS = (
    "family",
    "search_space",
    "primary_endpoint",
    "cost_model",
    "chronology",
    "thresholds",
    "stop_rules",
)


class TrialBudgetError(RuntimeError):
    """Raised when the ledger is asked to do something unsafe."""


@dataclass(frozen=True)
class BudgetVerdict:
    """Outcome of checking a declared trial count against the ledger."""

    verified: bool
    registration_ref: str
    declared_trial_count: int
    ledger_trial_count: int
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "registration_ref": self.registration_ref,
            "declared_trial_count": self.declared_trial_count,
            "ledger_trial_count": self.ledger_trial_count,
            "blockers": list(self.blockers),
        }


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _registration_ref(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    return f"PREREG-{digest[:32]}"


def _budget_dir(root: Path) -> Path:
    return root / LEDGER_DIRNAME


def _append(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON record under an exclusive lock.

    ponytail: JSONL + fcntl, not SQLite. Correct for concurrent appends and for the
    thousands-of-trials scale this project searches at. If the ledger ever grows past
    what a linear count scan tolerates, move to the SQLite pattern in services/jobs/store.py.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(_canonical(record) + "\n")
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return records


def preregister(root: Path, **fields: Any) -> str:
    """Pin a search family before it runs and return its registration ref.

    Re-registering identical fields is idempotent and returns the same ref, so a
    restarted driver does not fork a family's identity. Any change to the declared
    search space produces a different ref — by construction, an amended search is a
    new family and cannot inherit the original's trial budget.
    """
    missing = [name for name in REQUIRED_REGISTRATION_FIELDS if not fields.get(name)]
    if missing:
        raise TrialBudgetError(f"pre-registration is missing required fields: {sorted(missing)}")

    payload = {name: fields[name] for name in REQUIRED_REGISTRATION_FIELDS}
    ref = _registration_ref(payload)

    if registration(root, ref) is None:
        _append(
            _budget_dir(root) / REGISTRY_FILENAME,
            {
                "schema_version": SCHEMA_VERSION,
                "registration_ref": ref,
                "registered_at": utc_now().isoformat(),
                **payload,
            },
        )
    return ref


def registration(root: Path, registration_ref: str) -> dict[str, Any] | None:
    for record in _read(_budget_dir(root) / REGISTRY_FILENAME):
        if record.get("registration_ref") == registration_ref:
            return record
    return None


def record_trial(root: Path, registration_ref: str, trial_key: str) -> int:
    """Append one evaluated trial and return the family's running total.

    Refuses to record against an unknown registration: that is precisely the
    unregistered search this module exists to prevent.
    """
    if registration(root, registration_ref) is None:
        raise TrialBudgetError(
            f"cannot record a trial against unregistered family {registration_ref!r}; "
            "pre-register the search space before evaluating trials"
        )
    if not trial_key or not trial_key.strip():
        raise TrialBudgetError("trial_key must be a non-empty identifier")

    _append(
        _budget_dir(root) / LEDGER_FILENAME,
        {
            "schema_version": SCHEMA_VERSION,
            "registration_ref": registration_ref,
            "trial_key": trial_key,
            "recorded_at": utc_now().isoformat(),
        },
    )
    return trial_count(root, registration_ref)


def trial_count(root: Path, registration_ref: str) -> int:
    """Count distinct trials recorded for a family.

    Distinct by `trial_key`: re-running an identical trial after a crash must not
    inflate the budget, because it is not an additional search of the space.
    """
    keys = {
        record.get("trial_key")
        for record in _read(_budget_dir(root) / LEDGER_FILENAME)
        if record.get("registration_ref") == registration_ref
    }
    return len(keys)


def global_trial_count(root: Path) -> int:
    """Every trial this ecosystem has ever evaluated, across all families."""
    return len(
        {
            (record.get("registration_ref"), record.get("trial_key"))
            for record in _read(_budget_dir(root) / LEDGER_FILENAME)
        }
    )


def family_count(root: Path) -> int:
    """How many distinct families this ecosystem has ever admitted.

    Families are themselves a search. An agent free to spawn a new family whenever the
    last one failed is running a search over families, and if nothing counts them, that
    outer search is invisible to every statistic computed inside them.
    """
    return len(
        {record.get("registration_ref") for record in _read(_budget_dir(root) / REGISTRY_FILENAME)}
    )


def families(root: Path) -> tuple[dict[str, Any], ...]:
    """Every admitted family, in admission order."""
    return tuple(_read(_budget_dir(root) / REGISTRY_FILENAME))


def effective_trials_hierarchy_wide(root: Path, average_correlation: float) -> float:
    """Implied independent trials across *every* family, not just the current one.

    This is the family-level counterpart to `effective_trials_for_family`, and it is the
    one that should normally deflate a result.

    The reason is SUP-005 one level up. Deflating a candidate against only its own
    family's trials makes every family look modestly-searched no matter how many were
    tried: run fifty families of twenty trials each and each individual result is
    deflated against twenty, while the ecosystem actually searched a thousand. The
    winner is then noise that survived a search nobody counted.

    Sourcing the raw count from the whole ledger makes spawning a family cost something.
    An orchestrator may admit families freely, because doing so automatically raises the
    bar every subsequent family must clear — the correction is structural rather than a
    human deciding when to say enough.
    """
    from tios.validation.multiple_testing import implied_independent_trials

    raw = global_trial_count(root)
    if raw < 1:
        raise TrialBudgetError(
            "no trials recorded in any family; cannot deflate against an empty ledger"
        )
    return implied_independent_trials(raw, average_correlation)


def verify_declared_trials(
    root: Path,
    registration_ref: str,
    declared_trial_count: int,
) -> BudgetVerdict:
    """Check a scorecard's declared trial count against the ledger.

    This is the enforcement point. A declared count that understates the ledger means
    the search was wider than the statistics assume, and every threshold derived from
    it is too permissive.
    """
    blockers: list[str] = []

    if not isinstance(registration_ref, str) or not registration_ref.strip():
        blockers.append("PREREGISTRATION_REF_MISSING")
        return BudgetVerdict(False, str(registration_ref), declared_trial_count, 0, tuple(blockers))

    if registration(root, registration_ref) is None:
        blockers.append("PREREGISTRATION_NOT_FOUND")

    ledger = trial_count(root, registration_ref)

    if not isinstance(declared_trial_count, int) or isinstance(declared_trial_count, bool):
        blockers.append("DECLARED_TRIAL_COUNT_INVALID")
    elif declared_trial_count < ledger:
        blockers.append("DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER")
    elif declared_trial_count > ledger:
        blockers.append("DECLARED_TRIAL_COUNT_EXCEEDS_LEDGER")

    return BudgetVerdict(
        verified=not blockers,
        registration_ref=registration_ref,
        declared_trial_count=declared_trial_count,
        ledger_trial_count=ledger,
        blockers=tuple(blockers),
    )


def effective_trials_for_family(
    root: Path,
    registration_ref: str,
    average_correlation: float,
) -> float:
    """Ledger-backed implied independent trials for DSR deflation.

    Callers previously supplied `independent_trials` to `deflated_sharpe_ratio` from
    whatever population they happened to retain. Sourcing the raw count from the ledger
    means the deflation reflects the whole search, not the surviving slice of it.
    """
    from tios.validation.multiple_testing import implied_independent_trials

    raw = trial_count(root, registration_ref)
    if raw < 1:
        raise TrialBudgetError(
            f"no trials recorded for {registration_ref!r}; cannot deflate against an empty ledger"
        )
    return implied_independent_trials(raw, average_correlation)
