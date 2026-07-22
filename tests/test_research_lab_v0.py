from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_research_lab_v0 as lab  # noqa: E402
from register_vectorbt_trials import register_trials  # noqa: E402

from tios.research_assets import (  # noqa: E402
    HypothesisError,
    HypothesisRegistry,
    ResearchSourceRegistry,
)

RAN_START = "2026-07-10T12:34:56+00:00"
RAN_FINISH = "2026-07-10T12:35:56+00:00"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo(tmp_path: Path, quality_status: str = "PASS") -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    dataset = root / "data/normalized/BTCUSDT_5m.parquet"
    dataset.parent.mkdir(parents=True)
    dataset.write_bytes(b"frozen-dataset")
    reports = root / "artifacts/datasets"
    reports.mkdir(parents=True)
    quality = reports / "QUALITY_REPORT.json"
    quality.write_text(json.dumps({"overall": quality_status}), encoding="utf-8")
    manifest = reports / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "quality_report_sha256": _sha256(quality),
                "tables": {dataset.stem: {"parquet_sha256": _sha256(dataset)}},
            }
        ),
        encoding="utf-8",
    )
    specs = root / "fixtures/strategies/baselines"
    specs.mkdir(parents=True)
    for source in lab.SPECS:
        shutil.copy2(source, specs / source.name)
    environment = root / "engines/vectorbt/env_manifest.txt"
    environment.parent.mkdir(parents=True)
    shutil.copy2(lab.VECTORBT_ENV, environment)
    for relative in (
        "engines/vectorbt/probe_sweep.py",
        "scripts/register_vectorbt_trials.py",
        "scripts/run_research_lab_v0.py",
        "research/PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml",
        "research/RESEARCH_HYPOTHESES_V1.yaml",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).parents[1] / relative, target)
    return root, dataset, root / "artifacts/research_lab/v0"


def _specs(root: Path) -> tuple[Path, ...]:
    return tuple(sorted((root / "fixtures/strategies/baselines").glob("*.yaml")))


def _parameters(baseline: str, key: str) -> dict[str, object]:
    return {
        name: float(value) if "." in value else int(value)
        for name, value in (part.split("=") for part in key.split(","))
    }


def _write_trials(
    source: Path,
    *,
    reverse: bool = False,
    duplicate: bool = False,
    failed: tuple[str, str] | None = None,
    count_delta: int = 0,
    key_mismatch: bool = False,
    nonfinite: bool = False,
) -> None:
    source.mkdir(parents=True, exist_ok=True)
    for baseline, expected in lab.EXPECTED_TRIAL_CONFIG.items():
        keys = list(reversed(expected)) if reverse else list(expected)
        if duplicate and baseline == "b2":
            keys[-1] = keys[0]
        if baseline == "b2" and count_delta == -1:
            keys.pop()
        if baseline == "b2" and count_delta == 1:
            keys.append("fast=999,slow=1000")
        rows = []
        for key in keys:
            index = expected.index(key) if key in expected else len(expected)
            is_failed = failed == (baseline, key)
            parameters = _parameters(baseline, key)
            if key_mismatch and baseline == "b2" and index == 0:
                parameters["slow"] = 999
            rows.append(
                {
                    "trial_key": key,
                    **parameters,
                    "status": "FAILED" if is_failed else "COMPLETED",
                    "failure_reason": "RuntimeError: isolated trial" if is_failed else None,
                    "total_return": float("nan")
                    if nonfinite and baseline == "b2" and index == 0
                    else (None if is_failed else index / 100),
                    "trades": None if is_failed else index,
                }
            )
        pq.write_table(  # type: ignore[no-untyped-call]
            pa.Table.from_pylist(rows), source / f"{baseline}_sweep_all_trials.parquet"
        )
        (source / f"{baseline}_sweep_meta.json").write_text(
            json.dumps(
                {
                    "started_at_utc": RAN_START,
                    "finished_at_utc": RAN_FINISH,
                    "ran_utc": RAN_FINISH,
                }
            )
            + "\n",
            encoding="utf-8",
        )


def _fake_sweep(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
    _write_trials(Path(command[command.index("--out") + 1]))
    return subprocess.CompletedProcess(command, 0, stdout="fake sweep\n", stderr="")


def _reseal_result(path: Path, result: dict[str, Any]) -> None:
    result["content_sha256"] = lab._canonical_hash(  # noqa: SLF001
        lab._persisted_result_content(result)  # noqa: SLF001
    )
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(
    root: Path, dataset: Path, research: Path, runner: lab.RunCommand = _fake_sweep
) -> dict[str, Any]:
    return lab.run_lab(
        dataset,
        research,
        runner,
        root / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json",
        root / "artifacts/datasets/QUALITY_REPORT.json",
        _specs(root),
        root,
        research,
    )


def test_hypothesis_registry_resolves_primary_sources_and_proxy_gaps(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    sources = ResearchSourceRegistry.load(
        root / "research/PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
    )
    path = root / "research/RESEARCH_HYPOTHESES_V1.yaml"
    registry = HypothesisRegistry.load(path, sources)

    assert {record.hypothesis_id for record in registry.list()} == {
        "HYP-B2-MA-CROSSOVER-PROXY",
        "HYP-B3-RSI-MEAN-REVERSION-PROXY",
        "HYP-B4-ATR-BREAKOUT-PROXY",
    }
    assert all(sources.get(ref) for record in registry.list() for ref in record.source_refs)
    assert all(
        any("simplified executable proxy" in note for note in record.proxy_notes)
        for record in registry.list()
    )
    assert "Bollinger bands, not RSI" in " ".join(registry.for_candidate("B3").proxy_notes)
    assert "no ATR calculation" in " ".join(registry.for_candidate("B4").proxy_notes)
    assert registry.digest() == HypothesisRegistry.load(path, sources).digest()
    assert all(len(record.digest()) == 64 for record in registry.list())
    assert all(
        not record.faithful_paper_reproduction
        and not record.profit_claims_inherited
        and not record.locally_reproduced
        and not record.approval_eligible
        for record in registry.list()
    )
    assert {
        record.candidate_id: (record.expected_strategy_id, record.expected_spec_sha256)
        for record in registry.list()
    } == {
        "B2": (
            "STRAT-B2-ma-crossover",
            "c79cf7b9d635feb8d7d6d5db88713aad2f47028d247362b811aed2742f103f06",
        ),
        "B3": (
            "STRAT-B3-bollinger-mr",
            "523b5f6a61afe7b71b2507f0640815b619f4f14aa35d73665e865cf140b2102d",
        ),
        "B4": (
            "STRAT-B4-vol-breakout",
            "dce462ca70fd6f479a7bbb068837718d9e5ce7bf3a01e2b040a11af58935c046",
        ),
    }

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["hypotheses"][0]["source_refs"] = ["SRC-MISSING"]
    invalid = tmp_path / "invalid-hypotheses.yaml"
    invalid.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(HypothesisError, match="unknown source"):
        HypothesisRegistry.load(invalid, sources)


def test_source_registry_resolves_links_and_rejects_invalid_graphs() -> None:
    path = Path(__file__).parents[1] / "research/PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
    registry = ResearchSourceRegistry.load(path)
    records = registry.list()
    first, second = records[:2]

    assert {record.source_id for record in registry.related(first.source_id)} == set(
        first.related_source_ids
    )
    assert registry.supersedes(first.source_id) == ()
    with pytest.raises(ValueError, match="unknown source"):
        ResearchSourceRegistry([replace(first, related_source_ids=("SRC-MISSING",)), *records[1:]])
    with pytest.raises(ValueError, match="cannot reference itself"):
        ResearchSourceRegistry([replace(first, supersedes=(first.source_id,)), *records[1:]])
    with pytest.raises(ValueError, match="cyclic supersession"):
        ResearchSourceRegistry(
            [
                replace(first, supersedes=(second.source_id,)),
                replace(second, supersedes=(first.source_id,)),
                *records[2:],
            ]
        )


def test_batch_id_covers_code_policy_and_expected_configuration() -> None:
    hashes = {
        "dataset": "a",
        "registration_source_sha256": "b",
        "runner_source_sha256": "c",
        "safety_policy_sha256": "d",
        "expected_trial_config_sha256": "e",
    }
    assert lab.batch_id(hashes) == lab.batch_id(dict(reversed(list(hashes.items()))))
    for key in (
        "registration_source_sha256",
        "runner_source_sha256",
        "safety_policy_sha256",
        "expected_trial_config_sha256",
    ):
        assert lab.batch_id(hashes) != lab.batch_id({**hashes, key: "changed"})


def test_preflight_identity_changes_with_code_and_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, dataset, _ = _repo(tmp_path)
    arguments = (
        dataset,
        root / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json",
        root / "artifacts/datasets/QUALITY_REPORT.json",
        _specs(root),
        root,
    )
    original_hashes = lab.preflight(*arguments)
    original = lab.batch_id(original_hashes)
    assert {
        "source_registry_digest",
        "hypothesis_registry_digest",
        "canonical_spec_sha256",
        "strategy_version_ids",
        "strategy_versions_sha256",
    }.issubset(original_hashes)
    assert all(
        version_id.startswith("SV-")
        for version_id in original_hashes["strategy_version_ids"].values()
    )
    registration = root / "scripts/register_vectorbt_trials.py"
    original_registration = registration.read_text(encoding="utf-8")
    registration.write_text(original_registration + "\n# changed\n", encoding="utf-8")
    assert lab.batch_id(lab.preflight(*arguments)) != original
    registration.write_text(original_registration, encoding="utf-8")
    hypothesis_path = root / "research/RESEARCH_HYPOTHESES_V1.yaml"
    original_hypotheses = hypothesis_path.read_text(encoding="utf-8")
    hypothesis_path.write_text(
        original_hypotheses.replace(
            "Moving-average crossover proxy", "Moving-average crossover executable proxy"
        ),
        encoding="utf-8",
    )
    assert lab.batch_id(lab.preflight(*arguments)) != original
    hypothesis_path.write_text(original_hypotheses, encoding="utf-8")
    monkeypatch.setitem(lab.SAFETY, "mode", "CHANGED_FOR_IDENTITY_TEST")
    assert lab.batch_id(lab.preflight(*arguments)) != original
    monkeypatch.setitem(lab.SAFETY, "mode", "OFFLINE_RESEARCH_ONLY")
    monkeypatch.setitem(
        lab.EXPECTED_TRIAL_CONFIG,
        "b2",
        [*lab.EXPECTED_TRIAL_CONFIG["b2"], "fast=999,slow=1000"],
    )
    assert lab.batch_id(lab.preflight(*arguments)) != original


def test_preflight_rejects_hypothesis_strategy_and_spec_drift(tmp_path: Path) -> None:
    root, dataset, _ = _repo(tmp_path)
    arguments = (
        dataset,
        root / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json",
        root / "artifacts/datasets/QUALITY_REPORT.json",
        _specs(root),
        root,
    )
    hypothesis_path = root / "research/RESEARCH_HYPOTHESES_V1.yaml"
    hypotheses = hypothesis_path.read_text(encoding="utf-8")
    hypothesis_path.write_text(
        hypotheses.replace("STRAT-B2-ma-crossover", "STRAT-B2-drifted"), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="does not match canonical B2"):
        lab.preflight(*arguments)
    hypothesis_path.write_text(hypotheses, encoding="utf-8")

    spec_path = root / "fixtures/strategies/baselines/B3_bollinger_mean_reversion.yaml"
    spec = spec_path.read_text(encoding="utf-8")
    spec_path.write_text(
        spec.replace("first 2 bars produce no signal", "first two bars produce no signal"),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="does not match canonical B3"):
        lab.preflight(*arguments)


def test_run_lab_is_retired_before_hashing_output_or_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "must-not-exist"
    called: list[str] = []

    def forbidden(*_: Any, **__: Any) -> Any:
        called.append("called")
        raise AssertionError("hashing or evaluation must not occur")

    monkeypatch.setattr(lab, "preflight", forbidden)
    monkeypatch.setattr(lab, "_resolve_lineage", forbidden)
    monkeypatch.setattr(lab, "sha256", forbidden)
    with pytest.raises(RuntimeError) as error:
        lab.run_lab(
            tmp_path / "missing.parquet",
            output,
            forbidden,
            repo_root=tmp_path,
            research_root=output,
        )
    assert str(error.value) == lab.LEGACY_RESEARCH_LAB_V0_CLOSURE_REASON
    assert not called
    assert not output.exists()


def test_registration_is_order_independent_normalized_and_idempotent(tmp_path: Path) -> None:
    root, _, research = _repo(tmp_path)
    source = research / "source"
    _write_trials(source)
    ledger = source / "trial_ledger.jsonl"
    summary = source / "summary.json"
    first = register_trials(source, ledger, summary, repo_root=root, allowed_root=research)
    before = ledger.read_bytes()

    _write_trials(source, reverse=True)
    second = register_trials(source, ledger, summary, repo_root=root, allowed_root=research)

    assert first == second
    assert ledger.read_bytes() == before
    assert first["runs"] == 66
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    runs = [row["record"] for row in records if row["kind"] == "run"]
    assert len({run["run_id"] for run in runs}) == 66
    assert all(not Path(run["artifact_refs"][0]).is_absolute() for run in runs)
    assert all(value != "1.0" for run in runs for value in run["params"].values())
    assert {run["started_at"] for run in runs} == {RAN_START}
    assert {run["finished_at"] for run in runs} == {RAN_FINISH}


def test_duplicate_trials_fail_without_creating_registration_output(tmp_path: Path) -> None:
    root, _, research = _repo(tmp_path)
    source = research / "source"
    _write_trials(source, duplicate=True)
    ledger, summary = source / "ledger.jsonl", source / "summary.json"
    with pytest.raises(ValueError, match="duplicate trial_key"):
        register_trials(source, ledger, summary, repo_root=root, allowed_root=research)
    assert not ledger.exists()
    assert not summary.exists()


@pytest.mark.parametrize("count_delta", [-1, 1])
def test_standalone_registration_rejects_65_or_67_trials(tmp_path: Path, count_delta: int) -> None:
    root, _, research = _repo(tmp_path)
    source = research / "source"
    _write_trials(source, count_delta=count_delta)
    with pytest.raises(ValueError, match="population must match v0 exactly"):
        register_trials(
            source,
            source / "ledger.jsonl",
            source / "summary.json",
            repo_root=root,
            allowed_root=research,
        )


def test_registration_rejects_key_parameter_mismatch_and_nonfinite_metrics(
    tmp_path: Path,
) -> None:
    root, _, research = _repo(tmp_path)
    mismatch = research / "mismatch"
    _write_trials(mismatch, key_mismatch=True)
    with pytest.raises(ValueError, match="does not match normalized parameters"):
        register_trials(
            mismatch,
            mismatch / "ledger.jsonl",
            mismatch / "summary.json",
            repo_root=root,
            allowed_root=research,
        )

    nonfinite = research / "nonfinite"
    _write_trials(nonfinite, nonfinite=True)
    with pytest.raises(ValueError, match="must be finite"):
        register_trials(
            nonfinite,
            nonfinite / "ledger.jsonl",
            nonfinite / "summary.json",
            repo_root=root,
            allowed_root=research,
        )


def test_failed_trial_is_retained_and_other_trials_complete(tmp_path: Path) -> None:
    root, _, research = _repo(tmp_path)
    source = research / "source"
    failed_key = lab.EXPECTED_TRIAL_CONFIG["b3"][4]
    _write_trials(source, failed=("b3", failed_key))
    ledger, summary_path = source / "ledger.jsonl", source / "summary.json"
    summary = register_trials(source, ledger, summary_path, repo_root=root, allowed_root=research)
    runs = [
        json.loads(line)["record"]
        for line in ledger.read_text().splitlines()
        if json.loads(line)["kind"] == "run"
    ]
    failed = [run for run in runs if run["status"] == "FAILED"]
    assert summary["failed_runs"] == 1
    assert summary["completed_runs"] == 65
    assert len(failed) == 1
    assert failed[0]["trial_key"] == failed_key
    assert failed[0]["failure_reason"] == "RuntimeError: isolated trial"


def test_partial_registration_output_is_retained(tmp_path: Path) -> None:
    root, _, research = _repo(tmp_path)
    source = research / "partial"
    _write_trials(source)
    ledger, summary = source / "ledger.jsonl", source / "summary.json"
    ledger.write_text("retained\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="partial"):
        register_trials(source, ledger, summary, repo_root=root, allowed_root=research)
    assert ledger.read_text() == "retained\n"


def test_actual_bisection_and_all_signal_failures_are_retained() -> None:
    root = Path(__file__).resolve().parents[1]
    code = """
import pandas as pd
import engines.vectorbt.probe_sweep as probe

original = probe._run_portfolio_batch
def isolated(close, entries, exits):
    if "bad" in entries:
        raise RuntimeError("isolated")
    return pd.DataFrame({
        "trial_key": list(entries), "status": "COMPLETED", "failure_reason": None,
        "total_return": 0.0, "trades": 0,
    })
probe._run_portfolio_batch = isolated
rows = probe.run_portfolio(
    pd.Series([1.0]),
    {"good-a": None, "bad": None, "good-b": None},
    {"good-a": None, "bad": None, "good-b": None},
).to_dict("records")
assert [row["status"] for row in rows] == ["COMPLETED", "FAILED", "COMPLETED"]

class BrokenSignals:
    def rolling(self, width):
        raise RuntimeError("signal construction")

failed, count = probe.sweep_b2(BrokenSignals())
assert count == 34 and len(failed) == 34
assert set(failed["status"]) == {"FAILED"}
assert {"total_return", "trades"}.issubset(failed.columns)
assert failed["total_return"].isna().all() and failed["trades"].isna().all()
probe._run_portfolio_batch = original
"""
    subprocess.run(
        [str(root / "engines/vectorbt/.venv/bin/python"), "-c", code],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_command_allowlist_accepts_only_isolated_sweep(tmp_path: Path) -> None:
    dataset, out = tmp_path / "data.parquet", tmp_path / "out"
    command = lab.sweep_command(dataset, out)
    assert lab.command_allowed(command, dataset, out)
    assert not lab.command_allowed([*command, "--dry-run"], dataset, out)
    assert not lab.command_allowed(["freqtrade", "trade"], dataset, out)


def test_retained_latest_batch_declares_no_winner_and_no_execution_authority() -> None:
    # Guards the actual retained evidence the dashboard points at, not just tmp-generated
    # batches: the dashboard read model injects the safety flags from base defaults, so only
    # reading the artifact itself proves the retained batch declares them.
    batch = (
        Path(__file__).resolve().parents[1]
        / "artifacts/research_lab/v0"
        / "LAB-f04ef5d705e0de4d3fff5fe83ada90b2d91223dc89cfa35364c5fd8439ca3121"
    )
    lab_run = json.loads((batch / "lab_run.json").read_text())
    assert lab_run["status"] == "COMPLETED"
    assert {key: lab_run[key] for key in lab.SAFETY} == lab.SAFETY
    scorecards = json.loads((batch / "scorecards.json").read_text())
    assert scorecards["validation_state"] == "UNVALIDATED"
    assert scorecards["approval_state"] == "NOT_ELIGIBLE"
    assert {card["approval_state"] for card in scorecards["candidates"]} == {"NOT_ELIGIBLE"}
