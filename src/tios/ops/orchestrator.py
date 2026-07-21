"""The 24/7 orchestrator: observe, decide, act within invariants, escalate.

This is the worker that runs continuously and watches the whole ecosystem — statistical
health, evidence freshness, blocker movement, strategy coverage, execution divergence, and
its own parked work — then acts on what it sees.

Its authority is deliberately asymmetric. It may freely do anything that *adds* evidence:
run verifiers, register strategies, regenerate stale artifacts, record findings, propose
changes. It may not do anything that *weakens* a conclusion: it cannot read the sealed
holdout, edit its own constraints, promote a candidate, or place an order. Those are not
capabilities it happens to lack; they are the reason its output can be trusted at all.

The escalation set is small and specific. Most of it is bad news — an anomaly, a breached
envelope, a defect in previously-completed work. One item is good news: a candidate that
actually reaches promotion eligibility. Both stop the loop, because both are moments where
continuing to run unattended would be the wrong thing to do.

A note on the objective. This orchestrator optimizes *trustworthy verdicts per unit time*,
never the rate of positive verdicts. That distinction is what stops a self-improving system
from discovering that the cheapest way to produce good results is to lower the bar for what
counts as good.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.approval.attestation import authorizes
from tios.approval.attestation import load as load_attestation
from tios.evidence.staleness import BROKEN, CURRENT, STALE
from tios.evidence.staleness import scan as scan_staleness
from tios.ops.driver import parked_items
from tios.ops.driver import run_cycle as run_driver_cycle
from tios.ops.self_modification import IMMUTABLE_PATHS
from tios.strategy.registry import list_versions
from tios.validation.splits import holdout_accesses
from tios.validation.trial_budget import global_trial_count

SCHEMA_VERSION = 1
REPORT_DIR = Path("artifacts") / "orchestrator"
SITUATION_FILENAME = "SITUATION.json"
JOURNAL_FILENAME = "journal.jsonl"

# Observation severity. ESCALATE stops the loop; the rest are worked through autonomously.
INFO = "INFO"
ACT = "ACT"
ESCALATE = "ESCALATE"

# Prospective observer scripts the orchestrator ensures have run for the current UTC day.
# (lane, script path relative to root) — lane also names the artifacts/prospective/<lane>/
# directory the observer writes into and where its per-day marker lives.
DEFAULT_PROSPECTIVE_OBSERVERS: tuple[tuple[str, Path], ...] = (
    ("MVRV-DISLOCATION-V1", Path("scripts/run_prospective_mvrv_observer.py")),
    ("CFTC-POSITIONING-V1", Path("scripts/run_prospective_cftc_observer.py")),
)
PROSPECTIVE_OBSERVER_TIMEOUT_SECONDS = 120
PROSPECTIVE_MARKER_NAME = ".last_orchestrated_utc_day"


@dataclass(frozen=True)
class Observation:
    domain: str
    severity: str
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "severity": self.severity,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Situation:
    observed_at: datetime
    observations: tuple[Observation, ...]

    @property
    def escalations(self) -> tuple[Observation, ...]:
        return tuple(item for item in self.observations if item.severity == ESCALATE)

    @property
    def actions(self) -> tuple[Observation, ...]:
        return tuple(item for item in self.observations if item.severity == ACT)

    @property
    def halted(self) -> bool:
        return bool(self.escalations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "observed_at": self.observed_at.isoformat(),
            "halted": self.halted,
            "escalation_count": len(self.escalations),
            "action_count": len(self.actions),
            "observations": [item.as_dict() for item in self.observations],
        }


def observe_statistical_health(root: Path) -> tuple[Observation, ...]:
    """Trial budget consumption and holdout integrity.

    A holdout opened more than once is the single most damaging thing that can happen to
    this project's evidence, so it is checked every cycle rather than at review time.
    """
    out: list[Observation] = []
    trials = global_trial_count(root)
    out.append(
        Observation(
            "statistical",
            INFO,
            f"{trials} trials recorded across all families",
            {"global_trial_count": trials},
        )
    )

    accesses = holdout_accesses(root)
    if len(accesses) > 1:
        out.append(
            Observation(
                "statistical",
                ESCALATE,
                f"holdout opened {len(accesses)} times; out-of-sample evidence is compromised",
                {"accesses": list(accesses)},
            )
        )
    elif accesses:
        out.append(
            Observation(
                "statistical",
                INFO,
                "holdout opened once, as designed",
                {"reason": accesses[0].get("reason", "")},
            )
        )
    return tuple(out)


def observe_evidence_freshness(root: Path) -> tuple[Observation, ...]:
    """Which research artifacts still reproduce against current code."""
    statuses = scan_staleness(root)
    if not statuses:
        return (Observation("evidence", INFO, "no substantive research artifacts found"),)

    counts = {
        state: sum(status.state == state for status in statuses)
        for state in (CURRENT, STALE, BROKEN)
    }
    observations = [
        Observation(
            "evidence",
            INFO,
            f"{counts[CURRENT]} current, {counts[STALE]} stale, {counts[BROKEN]} broken artifacts",
            {"counts": counts},
        )
    ]
    if counts[STALE] or counts[BROKEN]:
        observations.append(
            Observation(
                "evidence",
                ACT,
                f"{counts[STALE] + counts[BROKEN]} artifacts need regeneration before citation",
                {
                    "refs": [
                        status.artifact_id for status in statuses if status.state in {STALE, BROKEN}
                    ]
                },
            )
        )
    return tuple(observations)


def observe_blockers(root: Path, map_paths: tuple[Path, ...]) -> tuple[Observation, ...]:
    """Blocker movement across every producer map."""
    out: list[Observation] = []
    for map_path in map_paths:
        if not (root / map_path).is_file():
            continue
        report = run_driver_cycle(root, root / map_path)
        out.append(
            Observation(
                "blockers",
                INFO,
                f"{report.map_id}: {len(report.released)} released, {len(report.blocked)} blocked",
                {
                    "map_id": report.map_id,
                    "released": list(report.released),
                    "blocked": list(report.blocked),
                    "prohibitions": list(report.prohibitions),
                },
            )
        )
    return tuple(out)


def observe_strategy_coverage(root: Path) -> tuple[Observation, ...]:
    versions = list_versions(root)
    spec_paths = sorted((root / "strategies").rglob("canonical_strategy_spec.yaml"))
    unregistered = len(spec_paths) - len({version.strategy_id for version in versions})

    observations = [
        Observation(
            "strategy",
            INFO,
            f"{len(versions)} registered strategy versions from {len(spec_paths)} specs",
            {"registered": len(versions), "specs": len(spec_paths)},
        )
    ]
    if unregistered > 0:
        observations.append(
            Observation(
                "strategy",
                ACT,
                f"{unregistered} canonical specs lack an immutable version identity",
                {"missing": unregistered},
            )
        )
    return tuple(observations)


def observe_execution_envelope(root: Path) -> tuple[Observation, ...]:
    """Operator attestation state and whether any capital-bearing stage is reachable."""
    try:
        attestation = load_attestation(root)
    except Exception as exc:  # malformed attestation is itself an escalation
        return (
            Observation(
                "execution",
                ESCALATE,
                f"operator attestation is unreadable: {exc}",
                {},
            ),
        )

    if attestation is None:
        return (
            Observation(
                "execution",
                INFO,
                "no operator attestation; offline research only, no capital-bearing stage",
                {},
            ),
        )

    verdict = authorizes(attestation, "PAPER_ACTIVE")
    severity = INFO if verdict.authorized else ACT
    if attestation.expired():
        severity = ESCALATE
    return (
        Observation(
            "execution",
            severity,
            (
                "attestation authorizes paper stage"
                if verdict.authorized
                else f"attestation does not authorize paper: {', '.join(verdict.blockers)}"
            ),
            {"venue": attestation.venue, "blockers": list(verdict.blockers)},
        ),
    )


def observe_parked_work(root: Path) -> tuple[Observation, ...]:
    items = parked_items(root)
    if not items:
        return ()
    return (
        Observation(
            "parked",
            INFO,
            f"{len(items)} items parked as genuinely unreachable",
            {"items": [item.get("item", "") for item in items]},
        ),
    )


def observe_constraint_integrity(root: Path) -> tuple[Observation, ...]:
    """Confirm every immutable constraint file is still present.

    A missing constraint file is indistinguishable from a disabled constraint, so absence
    escalates rather than passing quietly.
    """
    missing = [path for path in IMMUTABLE_PATHS if not (root / path).exists()]
    # The operator attestation is legitimately absent during offline research.
    missing = [path for path in missing if not path.endswith("OPERATOR_ATTESTATION.json")]
    if missing:
        return (
            Observation(
                "integrity",
                ESCALATE,
                f"{len(missing)} constraint files are missing; guarantees are unverifiable",
                {"missing": missing},
            ),
        )
    return (Observation("integrity", INFO, "all constraint files present", {}),)


def observe_prospective_observers(
    root: Path,
    observers: tuple[tuple[str, Path], ...] = DEFAULT_PROSPECTIVE_OBSERVERS,
    *,
    timeout: int = PROSPECTIVE_OBSERVER_TIMEOUT_SECONDS,
) -> tuple[Observation, ...]:
    """Ensure each prospective observer script has run once for the current UTC day.

    Observers hit external APIs, so a per-lane marker file caps them at one attempt per UTC
    day even though the cycle itself fires every ~900s. A failing or missing observer never
    halts the orchestrator: it surfaces as an ACT observation for an operator to look at.
    """
    out: list[Observation] = []
    today = datetime.now(tz=UTC).date().isoformat()
    for lane, script in observers:
        marker = root / "artifacts" / "prospective" / lane / PROSPECTIVE_MARKER_NAME
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == today:
            continue

        script_path = root / script
        if not script_path.is_file():
            out.append(
                Observation(
                    "prospective_observation",
                    ACT,
                    f"{lane}: observer script missing at {script}",
                    {"lane": lane, "script": str(script)},
                )
            )
            continue

        try:
            result = subprocess.run(  # noqa: S603
                [sys.executable, str(script_path)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(today, encoding="utf-8")
            out.append(
                Observation(
                    "prospective_observation",
                    ACT,
                    f"{lane}: observer timed out after {timeout}s",
                    {"lane": lane, "script": str(script)},
                )
            )
            continue

        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(today, encoding="utf-8")

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            out.append(
                Observation(
                    "prospective_observation",
                    ACT,
                    f"{lane}: observer exited {result.returncode}",
                    {
                        "lane": lane,
                        "script": str(script),
                        "returncode": result.returncode,
                        "detail": tail[-1][:400] if tail else "",
                    },
                )
            )
        else:
            out.append(
                Observation(
                    "prospective_observation",
                    INFO,
                    f"{lane}: observer ran for {today}",
                    {"lane": lane, "script": str(script)},
                )
            )
    return tuple(out)


def observe(
    root: Path,
    map_paths: tuple[Path, ...] = (),
    prospective_observers: tuple[tuple[str, Path], ...] = DEFAULT_PROSPECTIVE_OBSERVERS,
) -> Situation:
    """One full observation pass across every domain the orchestrator watches."""
    observations: list[Observation] = []
    observations.extend(observe_constraint_integrity(root))
    observations.extend(observe_statistical_health(root))
    observations.extend(observe_evidence_freshness(root))
    observations.extend(observe_strategy_coverage(root))
    observations.extend(observe_blockers(root, map_paths))
    observations.extend(observe_execution_envelope(root))
    observations.extend(observe_parked_work(root))
    observations.extend(observe_prospective_observers(root, prospective_observers))
    return Situation(datetime.now(tz=UTC), tuple(observations))


def run_cycle(
    root: Path,
    map_paths: tuple[Path, ...] = (),
    prospective_observers: tuple[tuple[str, Path], ...] = DEFAULT_PROSPECTIVE_OBSERVERS,
) -> Situation:
    """Observe, persist the situation, and append to the journal.

    The journal is append-only on purpose: an orchestrator that can rewrite its own history
    of what it saw cannot be audited after the fact.
    """
    situation = observe(root, map_paths, prospective_observers)

    target = root / REPORT_DIR / SITUATION_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(situation.as_dict(), indent=2) + "\n", encoding="utf-8")

    journal = root / REPORT_DIR / JOURNAL_FILENAME
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "observed_at": situation.observed_at.isoformat(),
                    "halted": situation.halted,
                    "escalations": [item.summary for item in situation.escalations],
                    "actions": [item.summary for item in situation.actions],
                },
                sort_keys=True,
            )
            + "\n"
        )
    return situation


def journal(root: Path) -> tuple[dict[str, Any], ...]:
    target = root / REPORT_DIR / JOURNAL_FILENAME
    if not target.is_file():
        return ()
    return tuple(
        json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    )
