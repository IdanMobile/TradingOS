"""Minimal idempotent run executor and mandatory economic scenario grid."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from tios.core_types.engine import MANDATORY_GRID, FeeSlippageScenario
from tios.experiment.ledger import ExperimentLedger, Run


@dataclass(frozen=True)
class RunRequest:
    experiment_id: str
    params: dict[str, str]
    scenario: FeeSlippageScenario
    environment_manifest_hash: str

    @property
    def run_id(self) -> str:
        raw = (
            f"{self.experiment_id}|{sorted(self.params.items())}|"
            f"{self.scenario.scenario_id}|{self.environment_manifest_hash}"
        )
        return f"RUN-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


Runner = Callable[[RunRequest], tuple[dict[str, Decimal], tuple[str, ...]]]


class RunExecutor:
    def __init__(self, ledger: ExperimentLedger) -> None:
        self.ledger = ledger

    def execute(self, request: RunRequest, runner: Runner) -> Run:
        """Execute once; identical inputs return the retained prior run."""
        existing = next((run for run in self.ledger.runs() if run.run_id == request.run_id), None)
        if existing:
            return existing
        started = datetime.now(tz=UTC)
        try:
            metrics, artifact_refs = runner(request)
            run = Run(
                run_id=request.run_id,
                experiment_id=request.experiment_id,
                trial_key=request.run_id,
                params=request.params,
                scenario=request.scenario.scenario_id,
                status="COMPLETED",
                metrics=metrics,
                artifact_refs=artifact_refs,
                environment_manifest_hash=request.environment_manifest_hash,
                started_at=started,
                finished_at=datetime.now(tz=UTC),
            )
        except Exception as exc:
            run = Run(
                run_id=request.run_id,
                experiment_id=request.experiment_id,
                trial_key=request.run_id,
                params=request.params,
                scenario=request.scenario.scenario_id,
                status="FAILED",
                metrics={},
                artifact_refs=(),
                environment_manifest_hash=request.environment_manifest_hash,
                started_at=started,
                finished_at=datetime.now(tz=UTC),
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
        return self.ledger.record_run(run)


def mandatory_scenario_grid() -> tuple[FeeSlippageScenario, ...]:
    return MANDATORY_GRID


def assert_complete_grid(runs: tuple[Run, ...]) -> None:
    present = {run.scenario for run in runs}
    required = {scenario.scenario_id for scenario in MANDATORY_GRID}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"mandatory fee/slippage grid is incomplete: {', '.join(missing)}")
