#!/usr/bin/env python3
"""Run the deterministic, offline-only Research Lab v0 batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq
import yaml
from register_vectorbt_trials import register_trials

from tios.evidence import EvidenceRecord, EvidenceRegistry
from tios.research_assets import HypothesisRegistry, ResearchSourceRegistry
from tios.strategy.spec import CanonicalStrategySpec, parse_spec
from tios.strategy.validator import validate_yaml
from tios.strategy.version import StrategyVersion, create_version

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/normalized/BTCUSDT_5m.parquet"
FROZEN_MANIFEST = ROOT / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
QUALITY_REPORT = ROOT / "artifacts/datasets/QUALITY_REPORT.json"
SPECS = tuple(sorted((ROOT / "fixtures/strategies/baselines").glob("B[234]_*.yaml")))
VECTORBT_ENV = ROOT / "engines/vectorbt/env_manifest.txt"
OUTPUT_ROOT = ROOT / "artifacts/research_lab/v0"
EXPECTED_STRATEGIES = {"STRAT-B2-ma-crossover", "STRAT-B3-bollinger-mr", "STRAT-B4-vol-breakout"}
SAFETY = {
    "mode": "OFFLINE_RESEARCH_ONLY",
    "winner_selected": False,
    "execution_authority": "NONE",
    "venue_connection": "NONE",
    "paper_orders": "DISABLED",
    "live_orders": "DISABLED",
}
SCORE_STATES = {
    "data_integrity_and_freshness": "PASS",
    "economic_performance_after_declared_costs": "UNASSESSED",
    "drawdown_and_loss_severity": "UNASSESSED",
    "parameter_neighborhood_robustness": "BLOCKED",
    "temporal_walk_forward_stability": "BLOCKED",
    "regime_stability": "BLOCKED",
    "baseline_superiority": "BLOCKED",
    "multiple_testing_selection_bias_control": "BLOCKED",
    "cross_engine_reproduction": "BLOCKED",
    "operational_and_evidence_completeness": "PASS",
}
BLOCKERS = [
    "economic and drawdown metrics are retained but not validation evidence",
    "parameter-neighborhood robustness is not run",
    "temporal/walk-forward stability is not run",
    "regime stability is not run",
    "baseline superiority is not established",
    "multiple-testing and selection-bias controls are incomplete",
    "cross-engine reproduction is incomplete",
]
EXPECTED_TRIAL_CONFIG = {
    "b2": [
        f"fast={fast},slow={slow}"
        for fast, slow in product([2, 3, 5, 8, 10, 15], [10, 20, 30, 40, 50, 60])
        if fast < slow
    ],
    "b3": [
        f"window={window},deviation={deviation:g}"
        for window, deviation in product([3, 5, 10, 20], [0.5, 1.0, 1.5, 2.0])
    ],
    "b4": [
        f"lookback={lookback},exit_window={exit_window}"
        for lookback, exit_window in product([3, 5, 10, 20], [2, 3, 5, 10])
    ],
}
EXPECTED_ARTIFACTS = {
    *(f"{baseline}_sweep_all_trials.parquet" for baseline in EXPECTED_TRIAL_CONFIG),
    *(f"{baseline}_sweep_meta.json" for baseline in EXPECTED_TRIAL_CONFIG),
    "trial_ledger.jsonl",
    "trial_ledger_summary.json",
    "trading_evidence.jsonl",
    "provenance.json",
    "scorecards.json",
}
EXPECTED_RESULT_FIELDS = {
    "lab_id",
    "status",
    "reused",
    "started_at_utc",
    "finished_at_utc",
    "hashes",
    "commands",
    "counts",
    "ledger_sha256",
    "blockers",
    "score_states",
    "artifact_manifest_sha256",
    "content_sha256",
    *SAFETY,
}
RunCommand = Callable[..., subprocess.CompletedProcess[str]]
VALIDATION_SUMMARY = Path("artifacts/validation/B2_F0_S0/validation_summary.json")
CROSS_ENGINE_EVIDENCE = Path("artifacts/validation/CROSS_ENGINE_REPRODUCTION_2026_07_11.json")
VALIDATION_EVIDENCE_FILES = (
    VALIDATION_SUMMARY,
    CROSS_ENGINE_EVIDENCE,
    Path("artifacts/validation/B2_F0_S0/cost_sensitivity.json"),
    Path("artifacts/validation/B2_F0_S0/parameter_robustness.json"),
    Path("artifacts/validation/B2_F0_S0/walk_forward/summary.json"),
    Path("artifacts/validation/B2_F0_S0/regime_report.json"),
    Path("artifacts/validation/B2_F0_S0/baseline_comparison.json"),
    Path("artifacts/bakeoff/parity/engine_parity.json"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _confined(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must be within {root}")
    return resolved


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _repo_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "vectorbt_python": repo_root / "engines/vectorbt/.venv/bin/python",
        "vectorbt_environment": repo_root / "engines/vectorbt/env_manifest.txt",
        "probe": repo_root / "engines/vectorbt/probe_sweep.py",
        "registration": repo_root / "scripts/register_vectorbt_trials.py",
        "runner": repo_root / "scripts/run_research_lab_v0.py",
        "sources": repo_root / "research/PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml",
        "hypotheses": repo_root / "research/RESEARCH_HYPOTHESES_V1.yaml",
    }


def _validation_hashes(repo_root: Path) -> dict[str, str]:
    return {
        path.as_posix(): sha256(repo_root / path)
        for path in VALIDATION_EVIDENCE_FILES
        if (repo_root / path).is_file()
    }


def _score_assessment(repo_root: Path) -> dict[str, Any]:
    path = repo_root / VALIDATION_SUMMARY
    if not path.is_file():
        return {"score_states": dict(SCORE_STATES), "blockers": list(BLOCKERS)}
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
        gates = summary["gates"]
        metrics = summary["metrics"]
    except (KeyError, ValueError, TypeError):
        return {"score_states": dict(SCORE_STATES), "blockers": list(BLOCKERS)}

    states = dict(SCORE_STATES)
    blockers = []
    profit = _metric(metrics.get("profit_total_abs", "0"), "profit_total_abs")
    drawdown = _metric(metrics.get("max_drawdown_abs", "0"), "max_drawdown_abs")
    states["economic_performance_after_declared_costs"] = "PASS" if profit > 0 else "FAIL"
    states["drawdown_and_loss_severity"] = "PASS" if drawdown <= 0 else "FAIL"
    if profit <= 0:
        blockers.append("economic performance after declared costs is negative")
    if drawdown > 0:
        blockers.append("drawdown/loss severity remains material")

    gate_map = {
        "G7": (
            "temporal_walk_forward_stability",
            "walk-forward evidence is complete but zero windows are positive",
        ),
        "G8": (
            "parameter_neighborhood_robustness",
            "parameter-neighborhood evidence is complete but all neighbors remain negative",
        ),
        "G9": (
            "regime_stability",
            "regime evidence is descriptive only and does not support promotion",
        ),
        "G11": (
            "baseline_superiority",
            "baseline superiority failed; candidate underperforms cash and B1",
        ),
    }
    for gate, (dimension, blocker) in gate_map.items():
        gate_state = gates.get(gate, {}).get("status")
        if gate_state != "PASS":
            states[dimension] = "BLOCKED"
            blockers.append(blocker)
        elif gate in {"G7", "G8", "G11"}:
            states[dimension] = "FAIL"
            blockers.append(blocker)
        else:
            states[dimension] = "PASS_WITH_SCOPE_NOTE"
            blockers.append(blocker)
    g10_status = gates.get("G10", {}).get("status")
    if g10_status == "PASS":
        states["multiple_testing_selection_bias_control"] = "PASS"
    elif g10_status == "FAIL":
        states["multiple_testing_selection_bias_control"] = "FAIL"
        blockers.append(
            "multiple-testing control failed: candidate-specific PBO/DSR with "
            "independent recomputation rejects the selected configuration"
        )
    else:
        states["multiple_testing_selection_bias_control"] = "BLOCKED"
        blockers.append("multiple-testing and selection-bias controls are incomplete")
    reproduction_path = repo_root / CROSS_ENGINE_EVIDENCE
    reproduction_verdict = None
    if reproduction_path.is_file():
        try:
            reproduction_verdict = json.loads(reproduction_path.read_text(encoding="utf-8"))[
                "verdict"
            ]
        except (KeyError, ValueError, TypeError):
            reproduction_verdict = None
    if reproduction_verdict in {"PASS_WITH_SCOPE_NOTE", "PARTIAL", "FAIL"}:
        states["cross_engine_reproduction"] = reproduction_verdict
        blockers.append(
            "cross-engine reproduction is signal-level with quantified residuals; "
            "fill/P&L parity across engines is not claimed"
            if reproduction_verdict == "PASS_WITH_SCOPE_NOTE"
            else "cross-engine reproduction is incomplete or failing; see "
            "CROSS_ENGINE_REPRODUCTION evidence"
        )
    else:
        states["cross_engine_reproduction"] = "BLOCKED"
        blockers.append("cross-engine reproduction is incomplete")
    return {"score_states": states, "blockers": sorted(set(blockers))}


def _resolve_lineage(repo_root: Path, specs: Sequence[Path]) -> dict[str, Any]:
    paths = _repo_paths(repo_root)
    sources = ResearchSourceRegistry.load(paths["sources"])
    hypotheses = HypothesisRegistry.load(paths["hypotheses"], sources)
    if {record.candidate_id for record in hypotheses.list()} != {"B2", "B3", "B4"}:
        raise RuntimeError("hypothesis registry must resolve exactly B2/B3/B4")
    parsed: dict[str, CanonicalStrategySpec] = {}
    versions: dict[str, StrategyVersion] = {}
    for path in specs:
        baseline = path.name[:2]
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        spec = parse_spec(raw)
        hypothesis = hypotheses.for_candidate(baseline)
        if (
            hypothesis.expected_strategy_id != spec.strategy_id
            or hypothesis.expected_spec_sha256 != spec.spec_hash()
        ):
            raise RuntimeError(
                f"{hypothesis.hypothesis_id} does not match canonical {baseline} strategy identity"
            )
        parsed[baseline] = spec
        versions[baseline] = create_version(spec, {})
    return {
        "sources": sources,
        "hypotheses": hypotheses,
        "specs": parsed,
        "versions": versions,
    }


def _version_payload(version: StrategyVersion) -> dict[str, object]:
    return {
        "sv_id": version.sv_id,
        "strategy_id": version.strategy_id,
        "spec_hash": version.spec_hash,
        "resolved_parameters": dict(version.resolved_parameters),
    }


def _persisted_result_content(result: dict[str, Any]) -> dict[str, Any]:
    """Return content covered by ``content_sha256``.

    ``reused`` is response metadata: retained ``lab_run.json`` always stores false,
    while a verified reuse response reports true without changing retained bytes.
    """
    return {key: value for key, value in result.items() if key not in {"content_sha256", "reused"}}


def _write_result(path: Path, result: dict[str, Any]) -> None:
    result["content_sha256"] = _canonical_hash(_persisted_result_content(result))
    _write_json(path, result)


def _normalize(value: object) -> str:
    number = Decimal(str(value))
    if not number.is_finite():
        raise RuntimeError(f"non-finite parameter value: {value}")
    if number == number.to_integral():
        return str(int(number))
    return format(number.normalize(), "f")


def _metric(value: object, name: str) -> Decimal:
    metric = Decimal(str(value))
    if not metric.is_finite():
        raise RuntimeError(f"completed metric {name} must be finite")
    return metric


def preflight(
    dataset: Path = DATASET,
    frozen_manifest: Path = FROZEN_MANIFEST,
    quality_report: Path = QUALITY_REPORT,
    specs: Sequence[Path] = SPECS,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    dataset = _confined(dataset, repo_root / "data/normalized", "dataset")
    frozen_manifest = _confined(
        frozen_manifest, repo_root / "artifacts/datasets", "frozen manifest"
    )
    quality_report = _confined(quality_report, repo_root / "artifacts/datasets", "quality report")
    specs = tuple(
        _confined(spec, repo_root / "fixtures/strategies/baselines", "canonical spec")
        for spec in specs
    )
    ai_mode = os.environ.get("TIOS_AI_MODE")
    if ai_mode not in (None, "mock"):
        raise RuntimeError("TIOS_AI_MODE must be absent or mock")
    manifest = json.loads(frozen_manifest.read_text(encoding="utf-8"))
    quality = json.loads(quality_report.read_text(encoding="utf-8"))
    if quality.get("overall") != "PASS":
        raise RuntimeError("QUALITY_REPORT overall must be PASS")
    if manifest.get("quality_report_sha256") != sha256(quality_report):
        raise RuntimeError("frozen manifest QUALITY_REPORT hash mismatch")
    table = manifest.get("tables", {}).get(dataset.stem)
    if not table or table.get("parquet_sha256") != sha256(dataset):
        raise RuntimeError("dataset does not match frozen manifest")

    spec_hashes: dict[str, str] = {}
    strategy_ids: set[str] = set()
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        report = validate_yaml(text)
        if report.verdict != "VALID":
            raise RuntimeError(f"invalid canonical spec {spec.name}: {report.errors}")
        strategy_id = str(yaml.safe_load(text)["strategy_id"])
        strategy_ids.add(strategy_id)
        spec_hashes[spec.name] = sha256(spec)
    if strategy_ids != EXPECTED_STRATEGIES:
        raise RuntimeError("canonical baseline set must be exactly B2/B3/B4")

    lineage = _resolve_lineage(repo_root, specs)
    sources = cast(ResearchSourceRegistry, lineage["sources"])
    hypotheses = cast(HypothesisRegistry, lineage["hypotheses"])
    parsed = cast(dict[str, CanonicalStrategySpec], lineage["specs"])
    versions = cast(dict[str, StrategyVersion], lineage["versions"])
    paths = _repo_paths(repo_root)
    version_payloads = {
        baseline: _version_payload(version) for baseline, version in sorted(versions.items())
    }

    return {
        "dataset_sha256": sha256(dataset),
        "frozen_manifest_sha256": sha256(frozen_manifest),
        "quality_report_sha256": sha256(quality_report),
        "spec_sha256": spec_hashes,
        "canonical_spec_sha256": {
            baseline: spec.spec_hash() for baseline, spec in sorted(parsed.items())
        },
        "strategy_version_ids": {
            baseline: version.sv_id for baseline, version in sorted(versions.items())
        },
        "strategy_versions_sha256": _canonical_hash(version_payloads),
        "source_registry_sha256": sha256(paths["sources"]),
        "source_registry_digest": sources.digest(),
        "hypothesis_registry_sha256": sha256(paths["hypotheses"]),
        "hypothesis_registry_digest": hypotheses.digest(),
        "vectorbt_environment_sha256": sha256(paths["vectorbt_environment"]),
        "probe_source_sha256": sha256(paths["probe"]),
        "registration_source_sha256": sha256(paths["registration"]),
        "runner_source_sha256": sha256(paths["runner"]),
        "safety_policy_sha256": _canonical_hash(SAFETY),
        "expected_trial_config_sha256": _canonical_hash(EXPECTED_TRIAL_CONFIG),
        "validation_evidence_sha256": _canonical_hash(_validation_hashes(repo_root)),
    }


def batch_id(hashes: dict[str, Any]) -> str:
    return "LAB-" + _canonical_hash(hashes)


def sweep_command(dataset: Path, out: Path, repo_root: Path = ROOT) -> list[str]:
    paths = _repo_paths(repo_root.resolve())
    return [
        str(paths["vectorbt_python"]),
        str(paths["probe"]),
        "--dataset",
        str(dataset),
        "--out",
        str(out),
    ]


def command_allowed(
    command: Sequence[str], dataset: Path, out: Path, repo_root: Path = ROOT
) -> bool:
    return list(command) == sweep_command(dataset, out, repo_root)


def _ledger_records(batch_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        json.loads(line)
        for line in (batch_dir / "trial_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return (
        [row["record"] for row in rows if row.get("kind") == "experiment"],
        [row["record"] for row in rows if row.get("kind") == "run"],
    )


def _bind_experiment_lineage(batch_dir: Path, lineage: dict[str, Any]) -> str:
    path = batch_dir / "trial_ledger.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    hypotheses = cast(HypothesisRegistry, lineage["hypotheses"])
    versions = cast(dict[str, StrategyVersion], lineage["versions"])
    for row in rows:
        if row.get("kind") != "experiment":
            continue
        experiment = row["record"]
        baseline = str(experiment["experiment_id"]).split("-")[2]
        experiment["hypothesis_ref"] = hypotheses.for_candidate(baseline).hypothesis_id
        experiment["strategy_version_ref"] = versions[baseline].sv_id
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_path = batch_dir / "trial_ledger_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["ledger_sha256"] = sha256(path)
    _write_json(summary_path, summary)
    return cast(str, summary["ledger_sha256"])


def _evidence(batch: str, path: Path, batch_dir: Path) -> int:
    registry = EvidenceRegistry(path)
    experiments, runs = _ledger_records(batch_dir)
    by_id = {record["experiment_id"]: record for record in experiments}
    for run in sorted(runs, key=lambda record: record["run_id"]):
        experiment = by_id[run["experiment_id"]]
        registry.add(
            EvidenceRecord(
                evidence_id=f"EV-{batch}-{run['run_id']}",
                hypothesis_id=experiment["hypothesis_ref"],
                strategy_version_id=experiment["strategy_version_ref"],
                market="crypto_spot",
                instrument="BTCUSDT",
                timeframe="5m",
                run_ref=run["run_id"],
                dataset_ref="DS-CRYPTO-SPOT-BAKEOFF-V1",
            )
        )
    return len(registry.list())


def _validate_trial_outputs(batch_dir: Path) -> dict[str, int]:
    total = 0
    failed = 0
    for baseline, expected in EXPECTED_TRIAL_CONFIG.items():
        rows: list[dict[str, Any]] = pq.read_table(  # type: ignore[no-untyped-call]
            batch_dir / f"{baseline}_sweep_all_trials.parquet"
        ).to_pylist()
        keys = [str(row["trial_key"]) for row in rows]
        if len(keys) != len(set(keys)):
            raise RuntimeError(f"duplicate {baseline} trial keys")
        if set(keys) != set(expected) or len(rows) != len(expected):
            raise RuntimeError(f"{baseline} retained population does not match v0 configuration")
        for row in rows:
            status = row.get("status", "COMPLETED")
            if status not in {"COMPLETED", "FAILED"}:
                raise RuntimeError(f"invalid {baseline} trial status: {status}")
            if status == "FAILED" and not row.get("failure_reason"):
                raise RuntimeError(f"failed {baseline} trial lacks failure_reason")
            parameter_names = tuple(
                part.split("=", 1)[0] for part in str(row["trial_key"]).split(",")
            )
            normalized_key = ",".join(f"{name}={_normalize(row[name])}" for name in parameter_names)
            if row["trial_key"] != normalized_key:
                raise RuntimeError(f"{baseline} trial_key does not match parameter columns")
            if status == "COMPLETED":
                _metric(row["total_return"], "total_return")
                _metric(row["trades"], "trades")
            failed += status == "FAILED"
        total += len(rows)
    if total != 66:
        raise RuntimeError("expected exactly 66 retained v0 trials")
    return {"trials": total, "failed_trials": failed, "completed_trials": total - failed}


def _artifact_hashes(batch_dir: Path) -> dict[str, str]:
    return {name: sha256(batch_dir / name) for name in sorted(EXPECTED_ARTIFACTS)}


def _evidence_rows(batch_dir: Path) -> list[dict[str, str]]:
    return [
        record.to_dict() for record in EvidenceRegistry(batch_dir / "trading_evidence.jsonl").list()
    ]


def _expected_evidence(batch: str, batch_dir: Path) -> list[dict[str, str]]:
    experiments, runs = _ledger_records(batch_dir)
    by_id = {record["experiment_id"]: record for record in experiments}
    return [
        EvidenceRecord(
            evidence_id=f"EV-{batch}-{run['run_id']}",
            hypothesis_id=by_id[run["experiment_id"]]["hypothesis_ref"],
            strategy_version_id=by_id[run["experiment_id"]]["strategy_version_ref"],
            market="crypto_spot",
            instrument="BTCUSDT",
            timeframe="5m",
            run_ref=run["run_id"],
            dataset_ref="DS-CRYPTO-SPOT-BAKEOFF-V1",
        ).to_dict()
        for run in sorted(runs, key=lambda record: record["run_id"])
    ]


def _provenance_payload(batch: str, batch_dir: Path, lineage: dict[str, Any]) -> dict[str, Any]:
    hypotheses = cast(HypothesisRegistry, lineage["hypotheses"])
    versions = cast(dict[str, StrategyVersion], lineage["versions"])
    experiments, runs = _ledger_records(batch_dir)
    by_id = {record["experiment_id"]: record for record in experiments}
    links = []
    for run in sorted(runs, key=lambda record: record["run_id"]):
        experiment = by_id[run["experiment_id"]]
        baseline = str(experiment["experiment_id"]).split("-")[2]
        hypothesis = hypotheses.for_candidate(baseline)
        version = versions[baseline]
        links.append(
            {
                "source_refs": list(hypothesis.source_refs),
                "hypothesis_id": hypothesis.hypothesis_id,
                "hypothesis_sha256": hypothesis.digest(),
                "semantic_transformation": hypothesis.semantic_transformation,
                "proxy_notes": list(hypothesis.proxy_notes),
                "strategy_id": version.strategy_id,
                "strategy_version_id": version.sv_id,
                "strategy_version_sha256": _canonical_hash(_version_payload(version)),
                "canonical_spec_sha256": version.spec_hash,
                "experiment_id": experiment["experiment_id"],
                "run_id": run["run_id"],
                "trial_key": run["trial_key"],
                "run_status": run["status"],
                "validation_state": "UNVALIDATED",
                "approval_state": "NOT_ELIGIBLE",
            }
        )
    return {
        "lab_id": batch,
        "lineage": "source->hypothesis->strategy_version->experiment->run",
        "faithful_paper_reproduction": False,
        "profit_claims_inherited": False,
        "validation_state": "UNVALIDATED",
        "approval_state": "NOT_ELIGIBLE",
        "links": links,
    }


def _scorecards_payload(batch: str, lineage: dict[str, Any]) -> dict[str, Any]:
    hypotheses = cast(HypothesisRegistry, lineage["hypotheses"])
    versions = cast(dict[str, StrategyVersion], lineage["versions"])
    assessment = cast(dict[str, Any], lineage["score_assessment"])
    score_states = cast(dict[str, str], assessment["score_states"])
    blockers = cast(list[str], assessment["blockers"])
    return {
        "lab_id": batch,
        "scoring_policy": "independent dimensions only; no blended approval score",
        "validation_state": "UNVALIDATED",
        "approval_state": "NOT_ELIGIBLE",
        "candidates": [
            {
                "candidate_id": baseline,
                "hypothesis_id": hypotheses.for_candidate(baseline).hypothesis_id,
                "strategy_version_id": versions[baseline].sv_id,
                "dimensions": dict(score_states),
                "blockers": list(blockers),
                "validation_state": "UNVALIDATED",
                "approval_state": "NOT_ELIGIBLE",
            }
            for baseline in ("B2", "B3", "B4")
        ],
    }


def _timestamps_valid(result: dict[str, Any], manifest: dict[str, Any]) -> bool:
    try:
        started = datetime.fromisoformat(str(result["started_at_utc"]))
        finished = datetime.fromisoformat(str(result["finished_at_utc"]))
    except (KeyError, ValueError):
        return False
    return (
        started.tzinfo is not None
        and finished.tzinfo is not None
        and started <= finished
        and manifest.get("started_at_utc") == result["started_at_utc"]
        and manifest.get("finished_at_utc") == result["finished_at_utc"]
    )


def _expected_run_id(baseline: str, run: dict[str, Any]) -> str:
    payload = json.dumps(
        {"baseline": baseline, "trial_key": run["trial_key"], "params": run["params"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"RUN-VECTORBT-{baseline.upper()}-{hashlib.sha256(payload).hexdigest()[:20].upper()}"


def _ledger_counts(batch_dir: Path, lineage: dict[str, Any]) -> dict[str, int]:
    experiment_rows, runs = _ledger_records(batch_dir)
    experiments = {row["experiment_id"] for row in experiment_rows}
    expected_experiments = {
        f"EXP-VECTORBT-{baseline.upper()}-F1" for baseline in EXPECTED_TRIAL_CONFIG
    }
    if experiments != expected_experiments:
        raise RuntimeError("completed batch ledger experiment mismatch")
    hypotheses = cast(HypothesisRegistry, lineage["hypotheses"])
    versions = cast(dict[str, StrategyVersion], lineage["versions"])
    for experiment in experiment_rows:
        baseline = str(experiment["experiment_id"]).split("-")[2]
        if (
            experiment.get("hypothesis_ref") != hypotheses.for_candidate(baseline).hypothesis_id
            or experiment.get("strategy_version_ref") != versions[baseline].sv_id
        ):
            raise RuntimeError("completed batch experiment lineage mismatch")
    if len(runs) != 66:
        raise RuntimeError("completed batch ledger run population mismatch")
    if len({run.get("run_id") for run in runs}) != 66:
        raise RuntimeError("completed batch ledger run identity mismatch")
    failed = 0
    for baseline, expected_keys in EXPECTED_TRIAL_CONFIG.items():
        experiment_id = f"EXP-VECTORBT-{baseline.upper()}-F1"
        population = [run for run in runs if run.get("experiment_id") == experiment_id]
        if {run.get("trial_key") for run in population} != set(expected_keys):
            raise RuntimeError("completed batch ledger trial population mismatch")
        for run in population:
            if run.get("run_id") != _expected_run_id(baseline, run):
                raise RuntimeError("completed batch ledger run identity mismatch")
            if run.get("status") not in {"COMPLETED", "FAILED"}:
                raise RuntimeError("completed batch ledger status mismatch")
            if run["status"] == "FAILED" and not run.get("failure_reason"):
                raise RuntimeError("completed batch ledger failure reason missing")
            failed += run["status"] == "FAILED"
    return {"completed_trials": 66 - failed, "failed_trials": failed}


def _verify_completed(
    result: dict[str, Any],
    batch_dir: Path,
    hashes: dict[str, Any],
    command: list[str],
    lineage: dict[str, Any],
) -> None:
    recorded_digest = result.get("content_sha256")
    actual_digest = _canonical_hash(_persisted_result_content(result))
    if recorded_digest != actual_digest:
        raise RuntimeError("completed lab_run content digest mismatch")
    if set(result) != EXPECTED_RESULT_FIELDS or result.get("reused") is not False:
        raise RuntimeError("completed lab_run semantic schema mismatch")
    if result.get("status") != "COMPLETED" or result.get("hashes") != hashes:
        raise RuntimeError("completed batch identity mismatch")
    if result.get("lab_id") != batch_dir.name:
        raise RuntimeError("completed batch lab_id mismatch")
    if any(result.get(key) != value for key, value in SAFETY.items()):
        raise RuntimeError("completed batch safety policy mismatch")
    if result.get("commands") != [command]:
        raise RuntimeError("completed batch command mismatch")
    assessment = cast(dict[str, Any], lineage["score_assessment"])
    if (
        result.get("blockers") != assessment["blockers"]
        or result.get("score_states") != assessment["score_states"]
    ):
        raise RuntimeError("completed batch blocker or score-state mismatch")
    manifest_path = batch_dir / "manifest.json"
    if result.get("artifact_manifest_sha256") != sha256(manifest_path):
        raise RuntimeError("completed batch manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "COMPLETED"
        or manifest.get("hashes") != hashes
        or any(manifest.get(key) != value for key, value in SAFETY.items())
    ):
        raise RuntimeError("completed batch manifest integrity failure")
    if not _timestamps_valid(result, manifest):
        raise RuntimeError("completed batch timestamps are invalid")
    recorded = manifest.get("artifacts")
    if not isinstance(recorded, dict) or set(recorded) != EXPECTED_ARTIFACTS:
        raise RuntimeError("completed batch artifact inventory mismatch")
    if recorded != _artifact_hashes(batch_dir):
        raise RuntimeError("completed batch artifact digest mismatch")
    inventory = {
        path.name
        for path in batch_dir.iterdir()
        if path.name not in {"manifest.json", "lab_run.json"}
    }
    if inventory != EXPECTED_ARTIFACTS:
        raise RuntimeError("completed batch filesystem inventory mismatch")
    trial_counts = _validate_trial_outputs(batch_dir)
    ledger_counts = _ledger_counts(batch_dir, lineage)
    if ledger_counts != {
        "completed_trials": trial_counts["completed_trials"],
        "failed_trials": trial_counts["failed_trials"],
    }:
        raise RuntimeError("completed batch ledger/trial count mismatch")
    summary = json.loads((batch_dir / "trial_ledger_summary.json").read_text(encoding="utf-8"))
    ledger_digest = sha256(batch_dir / "trial_ledger.jsonl")
    if (
        result.get("ledger_sha256") != ledger_digest
        or summary.get("ledger_sha256") != ledger_digest
    ):
        raise RuntimeError("completed batch ledger digest mismatch")
    expected_counts = {"experiments": 3, **trial_counts, "evidence_records": 66}
    if result.get("counts") != expected_counts:
        raise RuntimeError("completed batch semantic count mismatch")
    if (
        summary.get("runs") != 66
        or summary.get("completed_runs") != trial_counts["completed_trials"]
        or summary.get("failed_runs") != trial_counts["failed_trials"]
    ):
        raise RuntimeError("completed batch ledger count mismatch")
    if _evidence_rows(batch_dir) != _expected_evidence(batch_dir.name, batch_dir):
        raise RuntimeError("completed batch evidence semantics mismatch")
    if json.loads((batch_dir / "provenance.json").read_text(encoding="utf-8")) != (
        _provenance_payload(batch_dir.name, batch_dir, lineage)
    ):
        raise RuntimeError("completed batch provenance semantics mismatch")
    if json.loads((batch_dir / "scorecards.json").read_text(encoding="utf-8")) != (
        _scorecards_payload(batch_dir.name, lineage)
    ):
        raise RuntimeError("completed batch scorecard semantics mismatch")


def run_lab(
    dataset: Path = DATASET,
    output_root: Path = OUTPUT_ROOT,
    run_command: RunCommand = subprocess.run,
    frozen_manifest: Path = FROZEN_MANIFEST,
    quality_report: Path = QUALITY_REPORT,
    specs: Sequence[Path] = SPECS,
    repo_root: Path = ROOT,
    research_root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    repo_root, research_root = repo_root.resolve(), research_root.resolve()
    approved_research_root = (repo_root / "artifacts/research_lab/v0").resolve()
    if not research_root.is_relative_to(approved_research_root):
        raise ValueError("research_root must be within repo_root/artifacts/research_lab/v0")
    dataset = _confined(Path(dataset), repo_root / "data/normalized", "dataset")
    output_root = _confined(Path(output_root), research_root, "research output")
    hashes = preflight(dataset, frozen_manifest, quality_report, specs, repo_root)
    lineage = _resolve_lineage(repo_root, specs)
    lineage["score_assessment"] = _score_assessment(repo_root)
    lab_id = batch_id(hashes)
    batch_dir = output_root / lab_id
    command = sweep_command(dataset, batch_dir, repo_root)
    result_path = batch_dir / "lab_run.json"
    if result_path.exists():
        existing = cast(dict[str, Any], json.loads(result_path.read_text(encoding="utf-8")))
        if existing.get("status") != "COMPLETED":
            raise FileExistsError(f"retained incomplete or conflicting batch exists: {batch_dir}")
        _verify_completed(existing, batch_dir, hashes, command, lineage)
        return {**existing, "reused": True}
    if batch_dir.exists():
        raise FileExistsError(f"retained partial batch exists: {batch_dir}")

    batch_dir.mkdir(parents=True)
    started_at = datetime.now(tz=UTC).isoformat()
    manifest = {
        "lab_id": lab_id,
        "status": "RUNNING",
        "started_at_utc": started_at,
        "hashes": hashes,
        **SAFETY,
    }
    _write_json(batch_dir / "manifest.json", manifest)
    result: dict[str, Any] = {
        "lab_id": lab_id,
        "status": "RUNNING",
        "reused": False,
        "started_at_utc": started_at,
        "hashes": hashes,
        "commands": [command],
        "counts": {
            "experiments": 0,
            "trials": 0,
            "completed_trials": 0,
            "failed_trials": 0,
            "evidence_records": 0,
        },
        "ledger_sha256": None,
        "blockers": lineage["score_assessment"]["blockers"],
        "score_states": lineage["score_assessment"]["score_states"],
        **SAFETY,
    }
    _write_result(result_path, result)
    try:
        if not command_allowed(command, dataset, batch_dir, repo_root):
            raise RuntimeError("command is not allowlisted")
        run_command(command, check=True, capture_output=True, text=True, cwd=repo_root)
        trial_counts = _validate_trial_outputs(batch_dir)
        summary = register_trials(
            batch_dir,
            batch_dir / "trial_ledger.jsonl",
            batch_dir / "trial_ledger_summary.json",
            repo_root=repo_root,
            allowed_root=research_root,
        )
        if (
            summary["runs"] != 66
            or summary["experiments"] != 3
            or summary["failed_runs"] != trial_counts["failed_trials"]
        ):
            raise RuntimeError("expected exactly 66 retained trials across 3 experiments")
        summary["ledger_sha256"] = _bind_experiment_lineage(batch_dir, lineage)
        evidence_count = _evidence(lab_id, batch_dir / "trading_evidence.jsonl", batch_dir)
        _write_json(
            batch_dir / "provenance.json",
            _provenance_payload(lab_id, batch_dir, lineage),
        )
        _write_json(batch_dir / "scorecards.json", _scorecards_payload(lab_id, lineage))
        result.update(
            status="COMPLETED",
            finished_at_utc=datetime.now(tz=UTC).isoformat(),
            counts={"experiments": 3, **trial_counts, "evidence_records": evidence_count},
            ledger_sha256=summary["ledger_sha256"],
        )
        manifest.update(
            status="COMPLETED",
            finished_at_utc=result["finished_at_utc"],
            artifacts=_artifact_hashes(batch_dir),
        )
        _write_json(batch_dir / "manifest.json", manifest)
        result["artifact_manifest_sha256"] = sha256(batch_dir / "manifest.json")
    except Exception as error:
        result.update(
            status="FAILED",
            finished_at_utc=datetime.now(tz=UTC).isoformat(),
            error=f"{type(error).__name__}: {error}",
        )
        manifest.update(status="FAILED", error=result["error"])
        raise
    finally:
        if manifest["status"] != "COMPLETED":
            _write_json(batch_dir / "manifest.json", manifest)
        _write_result(result_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    print(json.dumps(run_lab(args.dataset, args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
