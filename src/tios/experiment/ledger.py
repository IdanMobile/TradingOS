"""Append-only experiment/run ledger for the S1 prototype."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

RunStatus = Literal["COMPLETED", "FAILED", "ABORTED"]


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _canonical(value: object) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis_ref: str
    strategy_version_ref: str
    dataset_ref: str
    engine: str
    parameter_space: dict[str, tuple[str, ...]]
    scenarios: tuple[str, ...]
    selection_procedure: str
    created_at: datetime


@dataclass(frozen=True)
class Run:
    run_id: str
    experiment_id: str
    trial_key: str
    params: dict[str, str]
    scenario: str
    status: RunStatus
    metrics: dict[str, Decimal]
    artifact_refs: tuple[str, ...]
    environment_manifest_hash: str
    started_at: datetime
    finished_at: datetime | None = None
    failure_reason: str | None = None


class LedgerError(ValueError):
    """Raised when an append-only ledger invariant is violated."""


class ExperimentLedger:
    """Small local ledger backed by append-only JSONL records."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _append(self, kind: str, record: Experiment | Run) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"kind": kind, "record": asdict(record)}
        line = _canonical(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def declare(self, experiment: Experiment) -> Experiment:
        if any(item.experiment_id == experiment.experiment_id for item in self.experiments()):
            raise LedgerError(f"experiment already exists: {experiment.experiment_id}")
        self._append("experiment", experiment)
        return experiment

    def record_run(self, run: Run) -> Run:
        if not any(item.experiment_id == run.experiment_id for item in self.experiments()):
            raise LedgerError(f"unknown experiment: {run.experiment_id}")
        if any(item.run_id == run.run_id for item in self.runs()):
            raise LedgerError(f"run already exists: {run.run_id}")
        if run.status == "FAILED" and not run.failure_reason:
            raise LedgerError("FAILED runs must preserve a failure_reason")
        self._append("run", run)
        return run

    def experiments(self) -> tuple[Experiment, ...]:
        return tuple(
            self._decode(item["record"], Experiment) for item in self._read_kind("experiment")
        )

    def runs(self, experiment_id: str | None = None) -> tuple[Run, ...]:
        runs = tuple(self._decode(item["record"], Run) for item in self._read_kind("run"))
        return tuple(
            run for run in runs if experiment_id is None or run.experiment_id == experiment_id
        )

    def assert_winner_references_population(self, experiment_id: str, winner_run_id: str) -> None:
        population = self.runs(experiment_id)
        if not population:
            raise LedgerError("winner cannot be selected from an empty trial population")
        if not any(run.run_id == winner_run_id for run in population):
            raise LedgerError("winner must reference a retained run in the experiment population")

    def digest(self) -> str:
        payload = self.path.read_bytes() if self.path.exists() else b""
        return hashlib.sha256(payload).hexdigest()

    def _read_kind(self, kind: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        return [row for row in rows if row["kind"] == kind]

    @staticmethod
    def _decode(payload: dict[str, Any], cls: type[Experiment] | type[Run]) -> Any:
        fields = dict(payload)
        fields["created_at" if cls is Experiment else "started_at"] = datetime.fromisoformat(
            fields["created_at" if cls is Experiment else "started_at"]
        )
        if cls is Run:
            if fields["finished_at"]:
                fields["finished_at"] = datetime.fromisoformat(fields["finished_at"])
            fields["metrics"] = {key: Decimal(value) for key, value in fields["metrics"].items()}
            fields["artifact_refs"] = tuple(fields["artifact_refs"])
        else:
            fields["scenarios"] = tuple(fields["scenarios"])
            fields["parameter_space"] = {
                key: tuple(values) for key, values in fields["parameter_space"].items()
            }
        return cls(**fields)
