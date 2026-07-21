"""Safe self-modification for the autonomous orchestrator.

An orchestrator that edits its own codebase needs two guarantees that ordinary CI does
not provide.

First, **it must not be able to edit its own constraints.** A system that can rewrite the
gate it is judged by has no gate. Under sustained optimization pressure, relaxing a
threshold is always cheaper than meeting it, and nothing in the objective function marks
that as cheating. The immutable-path guard below is what makes autonomous code changes
survivable: the orchestrator may improve anything except what decides whether its work is
good.

Second, **a red gate must never survive a change.** Every modification lands on a branch,
runs the full local gate, and is reverted automatically if the gate fails. The orchestrator
never leaves `main` broken, because it never writes to `main` directly.

Proposals to change an immutable path are recorded rather than discarded — a genuine
argument for revising a constraint should reach the operator, not vanish.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_DIR = Path("artifacts") / "self_modification"
PROPOSALS_FILENAME = "constraint_change_proposals.jsonl"
GATE_COMMAND = ("make", "check")

# Paths the orchestrator may never modify. These encode the constraints it is measured
# against; allowing self-edits here would make every downstream guarantee unverifiable.
IMMUTABLE_PATHS = (
    "research/STRATEGY_ELIGIBILITY_CONTRACT_V1.yaml",
    "src/tios/validation/eligibility.py",
    "src/tios/validation/trial_budget.py",
    "src/tios/approval/attestation.py",
    "src/tios/approval/authority_audit.py",
    "src/tios/ai_eval/decision_inspector.py",
    "src/tios/ops/self_modification.py",
    "src/tios/services/reporting/backtest_attribution.py",
    "src/tios/services/reporting/decision_intelligence.py",
    "src/tios/trading_domain/decision_intelligence.py",
    "artifacts/evidence/B2_HISTORICAL_TRADE_TRACES_2026_07_21.jsonl",
    "PACKAGE_INTEGRITY_MANIFEST.md",
    "ops/OPERATOR_ATTESTATION.json",
    # The Makefile defines `make check` — the gate every change is judged by. Leaving it
    # mutable would let a change edit the standard it must meet, which is the same hole
    # the rest of this list exists to close. New targets go through an operator.
    "Makefile",
)

# Directory prefixes that are equally off-limits: sealed evidence must not be rewritten
# to make a result look better after the fact.
IMMUTABLE_PREFIXES = (
    "artifacts/holdout/",
    "artifacts/sealed/",
)


class SelfModificationError(RuntimeError):
    """Raised when a change is unsafe or the repository is in an unexpected state."""


@dataclass(frozen=True)
class ChangeOutcome:
    landed: bool
    branch: str
    rationale: str
    changed_paths: tuple[str, ...]
    blockers: tuple[str, ...]
    gate_output: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "landed": self.landed,
            "branch": self.branch,
            "rationale": self.rationale,
            "changed_paths": list(self.changed_paths),
            "blockers": list(self.blockers),
            "recorded_at": utc_now().isoformat(),
        }


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ("git", *args),
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
    )


def changed_paths(root: Path) -> tuple[str, ...]:
    """Every path modified in the working tree, staged or not, including untracked."""
    tracked = _git(root, "diff", "--name-only", "HEAD").stdout.split()
    untracked = _git(root, "ls-files", "--others", "--exclude-standard").stdout.split()
    return tuple(sorted(set(tracked) | set(untracked)))


def immutable_violations(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Which of these paths the orchestrator is forbidden to modify."""
    violations = [path for path in paths if path in IMMUTABLE_PATHS]
    violations.extend(
        path for path in paths if any(path.startswith(prefix) for prefix in IMMUTABLE_PREFIXES)
    )
    return tuple(sorted(set(violations)))


def record_constraint_change_proposal(root: Path, *, path: str, argument: str) -> None:
    """Persist an argument for revising a constraint instead of acting on it.

    The orchestrator is expected to disagree with its constraints sometimes, and a good
    argument is worth surfacing. Recording it keeps the reasoning available to the
    operator while leaving the constraint in force.
    """
    target = root / EVIDENCE_DIR / PROPOSALS_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "path": path,
                    "argument": argument,
                    "proposed_at": utc_now().isoformat(),
                    "status": "OPEN_FOR_OPERATOR_REVIEW",
                },
                sort_keys=True,
            )
            + "\n"
        )


def run_gate(root: Path, command: tuple[str, ...] = GATE_COMMAND) -> tuple[bool, str]:
    """Run the full local gate. Returns (passed, combined output)."""
    result = subprocess.run(  # noqa: S603
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (result.stdout + result.stderr)


def start_change(root: Path, slug: str) -> str:
    """Branch off the current HEAD for an orchestrator change.

    Refuses to start from a dirty tree: mixing an in-flight edit into a new change makes
    the revert path ambiguous, and an ambiguous revert is how a red gate survives.
    """
    if changed_paths(root):
        raise SelfModificationError(
            "refusing to start a change from a dirty working tree; "
            "land or discard the in-flight edit first"
        )
    branch = f"orchestrator/{utc_now():%Y%m%dT%H%M%S}-{slug}"
    _git(root, "checkout", "-b", branch)
    return branch


def land_change(
    root: Path,
    *,
    rationale: str,
    gate_command: tuple[str, ...] = GATE_COMMAND,
    merge_into: str | None = "main",
) -> ChangeOutcome:
    """Verify the working-tree change and either commit it or revert it entirely.

    Order matters: the immutable-path check runs *before* the gate. A change touching a
    constraint is rejected on principle, not because it happened to fail tests — a
    constraint edit that passes the suite is more dangerous, not less.
    """
    if not rationale.strip():
        raise SelfModificationError("every orchestrator change requires a rationale")

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    paths = changed_paths(root)

    if not paths:
        return ChangeOutcome(False, branch, rationale, (), ("NO_CHANGES",), "")

    violations = immutable_violations(paths)
    if violations:
        _revert(root)
        return ChangeOutcome(
            landed=False,
            branch=branch,
            rationale=rationale,
            changed_paths=paths,
            blockers=("IMMUTABLE_PATH_MODIFIED: " + ", ".join(violations),),
            gate_output="",
        )

    passed, output = run_gate(root, gate_command)
    if not passed:
        _revert(root)
        return ChangeOutcome(False, branch, rationale, paths, ("GATE_FAILED",), output)

    outcome = ChangeOutcome(True, branch, rationale, paths, (), output)
    # Evidence is written before the commit so it lands with the change it describes.
    # Writing it afterwards would leave the tree dirty and make the next start_change
    # refuse, deadlocking the orchestrator after its first successful modification.
    _record_evidence(root, outcome)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", f"orchestrator: {rationale}")

    # Fast-forward only. A green gate plus a clean immutable-path check is exactly the
    # condition under which merging is safe; refusing anything but a fast-forward means
    # concurrent history is surfaced as a conflict rather than silently resolved.
    if merge_into:
        _git(root, "checkout", merge_into)
        merged = _git(root, "merge", "--ff-only", branch, check=False)
        if merged.returncode != 0:
            _git(root, "checkout", branch)
            return ChangeOutcome(
                landed=False,
                branch=branch,
                rationale=rationale,
                changed_paths=paths,
                blockers=("MERGE_NOT_FAST_FORWARD",),
                gate_output=merged.stderr,
            )
    return outcome


def _revert(root: Path) -> None:
    """Discard every working-tree change, tracked and untracked."""
    _git(root, "reset", "--hard", "HEAD")
    _git(root, "clean", "-fd")


def _record_evidence(root: Path, outcome: ChangeOutcome) -> None:
    target = root / EVIDENCE_DIR / f"{outcome.branch.replace('/', '_')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(outcome.as_dict(), indent=2) + "\n", encoding="utf-8")
