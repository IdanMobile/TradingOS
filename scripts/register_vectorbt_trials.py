"""Register every retained vectorbt sweep trial in the append-only OS ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.experiment import Experiment, ExperimentLedger, Run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/bakeoff/vectorbt"
LEDGER_PATH = SOURCE / "trial_ledger.jsonl"
SUMMARY_PATH = SOURCE / "trial_ledger_summary.json"
RESEARCH_ROOT = ROOT / "artifacts/research_lab/v0"
PARAMETER_NAMES = {
    "b2": ("fast", "slow"),
    "b3": ("window", "deviation"),
    "b4": ("lookback", "exit_window"),
}
EXPECTED_TRIAL_KEYS = {
    "b2": {
        f"fast={fast},slow={slow}"
        for fast, slow in product([2, 3, 5, 8, 10, 15], [10, 20, 30, 40, 50, 60])
        if fast < slow
    },
    "b3": {
        f"window={window},deviation={deviation:g}"
        for window, deviation in product([3, 5, 10, 20], [0.5, 1.0, 1.5, 2.0])
    },
    "b4": {
        f"lookback={lookback},exit_window={exit_window}"
        for lookback, exit_window in product([3, 5, 10, 20], [2, 3, 5, 10])
    },
}


def _confined(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must be within {root}")
    return resolved


def _normalize(value: object) -> str:
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise ValueError(f"non-finite parameter value: {value}")
    if decimal == decimal.to_integral():
        return str(int(decimal))
    return format(decimal.normalize(), "f")


def _run_id(baseline: str, trial_key: str, params: dict[str, str]) -> str:
    payload = json.dumps(
        {"baseline": baseline, "trial_key": trial_key, "params": params},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"RUN-VECTORBT-{baseline.upper()}-{hashlib.sha256(payload).hexdigest()[:20].upper()}"


def _artifact_ref(path: Path, repo_root: Path, allowed_root: Path) -> str:
    confined = _confined(path, allowed_root, "trial artifact")
    return confined.relative_to(repo_root.resolve()).as_posix()


def _execution_times(source: Path, baseline: str) -> tuple[datetime, datetime]:
    meta = json.loads((source / f"{baseline}_sweep_meta.json").read_text(encoding="utf-8"))
    started = datetime.fromisoformat(str(meta["started_at_utc"]))
    finished = datetime.fromisoformat(str(meta["finished_at_utc"]))
    if started.tzinfo is None or finished.tzinfo is None:
        raise ValueError(f"{baseline} execution timestamps must be timezone-aware")
    started, finished = started.astimezone(UTC), finished.astimezone(UTC)
    if finished < started:
        raise ValueError(f"{baseline} execution finish precedes start")
    return started, finished


def _metric(value: object, name: str) -> Decimal:
    metric = Decimal(str(value))
    if not metric.is_finite():
        raise ValueError(f"completed metric {name} must be finite")
    return metric


def _build_ledger(
    source: Path,
    ledger_path: Path,
    *,
    repo_root: Path,
    allowed_root: Path,
) -> dict[str, object]:
    ledger = ExperimentLedger(ledger_path)
    environment_hash = hashlib.sha256(
        (repo_root / "engines/vectorbt/env_manifest.txt").read_bytes()
    ).hexdigest()
    total = 0
    failed = 0
    for baseline in ("b2", "b3", "b4"):
        artifact = source / f"{baseline}_sweep_all_trials.parquet"
        rows: list[dict[str, Any]] = pq.read_table(  # type: ignore[no-untyped-call]
            artifact
        ).to_pylist()
        if not rows:
            raise ValueError(f"empty retained trial table: {artifact}")
        trial_keys = [str(row["trial_key"]) for row in rows]
        if len(set(trial_keys)) != len(trial_keys):
            raise ValueError(f"duplicate trial_key in {artifact}")
        if set(trial_keys) != EXPECTED_TRIAL_KEYS[baseline] or len(rows) != len(
            EXPECTED_TRIAL_KEYS[baseline]
        ):
            raise ValueError(f"{baseline} trial population must match v0 exactly")
        rows.sort(key=lambda row: str(row["trial_key"]))
        observed_parameters = {
            name
            for name in rows[0]
            if name not in {"trial_key", "status", "failure_reason", "total_return", "trades"}
        }
        parameter_names = PARAMETER_NAMES[baseline]
        if observed_parameters != set(parameter_names):
            raise ValueError(f"{baseline} parameter columns must be {parameter_names}")
        normalized = [{name: _normalize(row[name]) for name in parameter_names} for row in rows]
        for row, params in zip(rows, normalized, strict=True):
            expected_key = ",".join(f"{name}={params[name]}" for name in parameter_names)
            if row["trial_key"] != expected_key:
                raise ValueError(
                    f"trial_key does not match normalized parameters: {row['trial_key']}"
                )
        started_at, finished_at = _execution_times(source, baseline)
        experiment_id = f"EXP-VECTORBT-{baseline.upper()}-F1"
        ledger.declare(
            Experiment(
                experiment_id=experiment_id,
                hypothesis_ref=f"HYP-{baseline.upper()}-PARAMETER-SENSITIVITY",
                strategy_version_ref=f"STRAT-{baseline.upper()}-BASELINE-V1",
                dataset_ref="DS-CRYPTO-SPOT-BAKEOFF-V1",
                engine="vectorbt-1.1.0",
                parameter_space={
                    name: tuple(sorted({params[name] for params in normalized}))
                    for name in parameter_names
                },
                scenarios=("F1/S0",),
                selection_procedure=(
                    "retain all trials; no in-sample winner; require temporal validation, "
                    "multiple-testing control, and event-engine reproduction"
                ),
                created_at=started_at,
            )
        )
        artifact_ref = _artifact_ref(artifact, repo_root, allowed_root)
        for row, params in zip(rows, normalized, strict=True):
            status = str(row.get("status", "COMPLETED"))
            if status not in {"COMPLETED", "FAILED"}:
                raise ValueError(f"invalid trial status {status!r}")
            reason = str(row.get("failure_reason") or "") or None
            if status == "FAILED" and reason is None:
                raise ValueError("FAILED trial must include failure_reason")
            metrics = (
                {
                    "total_return": _metric(row["total_return"], "total_return"),
                    "trades": _metric(row["trades"], "trades"),
                }
                if status == "COMPLETED"
                else {}
            )
            trial_key = str(row["trial_key"])
            ledger.record_run(
                Run(
                    run_id=_run_id(baseline, trial_key, params),
                    experiment_id=experiment_id,
                    trial_key=trial_key,
                    params=params,
                    scenario="F1/S0",
                    status=status,  # type: ignore[arg-type]
                    metrics=metrics,
                    artifact_refs=(artifact_ref,),
                    environment_manifest_hash=environment_hash,
                    started_at=started_at,
                    finished_at=finished_at,
                    failure_reason=reason,
                )
            )
            failed += status == "FAILED"
        total += len(rows)
    return {
        "status": "COMPLETE_WITH_TRIAL_FAILURES" if failed else "PASS",
        "experiments": len(ledger.experiments()),
        "runs": len(ledger.runs()),
        "failed_runs": failed,
        "completed_runs": total - failed,
        "expected_runs": total,
        "all_trials_registered": len(ledger.runs()) == total,
        "ledger_sha256": ledger.digest(),
        "winner_selected": False,
    }


def register_trials(
    source: Path,
    ledger_path: Path,
    summary_path: Path,
    *,
    repo_root: Path = ROOT,
    allowed_root: Path | None = None,
) -> dict[str, object]:
    """Register retained trials, reusing only byte-identical complete output."""
    repo_root = repo_root.resolve()
    approved_roots = (
        (repo_root / "artifacts/bakeoff/vectorbt").resolve(),
        (repo_root / "artifacts/research_lab/v0").resolve(),
    )
    paths = (Path(source).resolve(), Path(ledger_path).resolve(), Path(summary_path).resolve())
    if allowed_root is None:
        allowed_root = next(
            (root for root in approved_roots if all(path.is_relative_to(root) for path in paths)),
            None,
        )
        if allowed_root is None:
            raise ValueError("source, ledger, and summary must share an approved artifact root")
    allowed_root = allowed_root.resolve()
    if allowed_root != approved_roots[0] and not allowed_root.is_relative_to(approved_roots[1]):
        raise ValueError("allowed_root must be an approved vectorbt or research-lab artifact root")
    source = _confined(paths[0], allowed_root, "source")
    ledger_path = _confined(paths[1], source, "ledger")
    summary_path = _confined(paths[2], source, "summary")
    if not allowed_root.is_relative_to(repo_root):
        raise ValueError("allowed artifact root must be within repository root")
    if ledger_path.exists() != summary_path.exists():
        raise FileExistsError("partial registration output exists; retained files were not changed")

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ledger_path.parent) as temporary:
        candidate = Path(temporary) / "trial_ledger.jsonl"
        summary = _build_ledger(
            source,
            candidate,
            repo_root=repo_root,
            allowed_root=allowed_root,
        )
        summary_bytes = (json.dumps(summary, indent=2) + "\n").encode()
        if ledger_path.exists():
            if ledger_path.read_bytes() != candidate.read_bytes():
                raise FileExistsError("conflicting retained ledger exists")
            if summary_path.read_bytes() != summary_bytes:
                raise FileExistsError("conflicting retained ledger summary exists")
            return summary
        ledger_path.write_bytes(candidate.read_bytes())
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_bytes(summary_bytes)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args()
    summary = register_trials(args.source, args.ledger, args.summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
