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


def test_preflight_failures_and_path_escapes_do_not_invoke_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, dataset, research = _repo(tmp_path, "FAIL")
    called = False

    def forbidden(*_: Any, **__: Any) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        raise AssertionError("sweep must not run")

    with pytest.raises(RuntimeError, match="overall must be PASS"):
        _run(root, dataset, research, forbidden)
    assert not called

    monkeypatch.setenv("TIOS_AI_MODE", "real")
    with pytest.raises(RuntimeError, match="absent or mock"):
        _run(root, dataset, research, forbidden)
    monkeypatch.delenv("TIOS_AI_MODE")
    outside = tmp_path / "outside"
    with pytest.raises(ValueError, match="research output"):
        lab.run_lab(dataset, outside, forbidden, repo_root=root, research_root=research)
    with pytest.raises(ValueError, match="source"):
        register_trials(outside, outside / "ledger", outside / "summary", repo_root=root)
    broad_output = root / "broad-output"
    with pytest.raises(ValueError, match="research_root"):
        lab.run_lab(
            dataset,
            broad_output,
            forbidden,
            repo_root=root,
            research_root=root,
        )
    broad_source = root / "broad-source"
    with pytest.raises(ValueError, match="allowed_root"):
        register_trials(
            broad_source,
            broad_source / "ledger",
            broad_source / "summary",
            repo_root=root,
            allowed_root=root,
        )
    assert not outside.exists()
    assert not broad_output.exists()
    assert not broad_source.exists()
    assert not called


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


def test_batch_completes_while_retaining_an_isolated_trial_failure(tmp_path: Path) -> None:
    root, dataset, research = _repo(tmp_path)
    failed_key = lab.EXPECTED_TRIAL_CONFIG["b4"][2]

    def partial_sweep(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        _write_trials(Path(command[command.index("--out") + 1]), failed=("b4", failed_key))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = _run(root, dataset, research, partial_sweep)
    assert result["status"] == "COMPLETED"
    assert result["counts"]["failed_trials"] == 1
    assert result["counts"]["completed_trials"] == 65
    ledger = research / str(result["lab_id"]) / "trial_ledger.jsonl"
    failed = [
        json.loads(line)["record"]
        for line in ledger.read_text().splitlines()
        if '"status":"FAILED"' in line
    ]
    assert [(run["trial_key"], run["failure_reason"]) for run in failed] == [
        (failed_key, "RuntimeError: isolated trial")
    ]
    batch_dir = ledger.parent
    evidence = [
        json.loads(line) for line in (batch_dir / "trading_evidence.jsonl").read_text().splitlines()
    ]
    provenance = json.loads((batch_dir / "provenance.json").read_text())
    assert len(evidence) == len(provenance["links"]) == 66
    assert failed[0]["run_id"] in {row["run_ref"] for row in evidence}
    assert [link for link in provenance["links"] if link["run_id"] == failed[0]["run_id"]][0][
        "run_status"
    ] == "FAILED"


def test_registration_failure_and_partial_output_are_retained(tmp_path: Path) -> None:
    root, dataset, research = _repo(tmp_path)

    def duplicate_sweep(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        _write_trials(Path(command[command.index("--out") + 1]), duplicate=True)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with pytest.raises(RuntimeError, match="duplicate b2 trial keys"):
        _run(root, dataset, research, duplicate_sweep)
    batch_dir = next(research.iterdir())
    assert (batch_dir / "b2_sweep_all_trials.parquet").exists()
    assert json.loads((batch_dir / "lab_run.json").read_text())["status"] == "FAILED"

    source = research / "partial"
    _write_trials(source)
    ledger, summary = source / "ledger.jsonl", source / "summary.json"
    ledger.write_text("retained\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="partial"):
        register_trials(source, ledger, summary, repo_root=root, allowed_root=research)
    assert ledger.read_text() == "retained\n"


def test_completed_batch_is_safe_reused_and_tamper_detected(tmp_path: Path) -> None:
    root, dataset, research = _repo(tmp_path)
    first = _run(root, dataset, research)
    result_path = research / str(first["lab_id"]) / "lab_run.json"
    retained_before_reuse = result_path.read_bytes()
    second = _run(root, dataset, research)
    batch_dir = research / str(first["lab_id"])

    assert first["status"] == "COMPLETED"
    assert first["counts"] == {
        "experiments": 3,
        "trials": 66,
        "completed_trials": 66,
        "failed_trials": 0,
        "evidence_records": 66,
    }
    assert second["reused"] is True
    assert result_path.read_bytes() == retained_before_reuse
    assert json.loads(retained_before_reuse)["reused"] is False
    assert (
        first["content_sha256"]
        == second["content_sha256"]
        == lab._canonical_hash(  # noqa: SLF001
            lab._persisted_result_content(second)  # noqa: SLF001
        )
    )
    assert {key: first[key] for key in lab.SAFETY} == lab.SAFETY
    assert first["started_at_utc"] != RAN_START
    assert first["started_at_utc"] <= first["finished_at_utc"]
    (batch_dir / "b4_sweep_meta.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact digest mismatch"):
        _run(root, dataset, research)


def test_completed_lineage_uses_real_hypotheses_versions_and_all_run_ids(
    tmp_path: Path,
) -> None:
    root, dataset, research = _repo(tmp_path)
    result = _run(root, dataset, research)
    batch_dir = research / str(result["lab_id"])
    records = [
        json.loads(line) for line in (batch_dir / "trial_ledger.jsonl").read_text().splitlines()
    ]
    experiments = [row["record"] for row in records if row["kind"] == "experiment"]
    runs = [row["record"] for row in records if row["kind"] == "run"]
    evidence = [
        json.loads(line) for line in (batch_dir / "trading_evidence.jsonl").read_text().splitlines()
    ]
    provenance = json.loads((batch_dir / "provenance.json").read_text())
    scorecards = json.loads((batch_dir / "scorecards.json").read_text())

    assert len(runs) == len(evidence) == len(provenance["links"]) == 66
    assert {row["run_ref"] for row in evidence} == {run["run_id"] for run in runs}
    assert all(row["run_ref"].startswith("RUN-") for row in evidence)
    assert all(experiment["hypothesis_ref"].startswith("HYP-") for experiment in experiments)
    assert all(experiment["strategy_version_ref"].startswith("SV-") for experiment in experiments)
    assert not any(
        "PARAMETER-SENSITIVITY" in experiment["hypothesis_ref"]
        or "BASELINE-V1" in experiment["strategy_version_ref"]
        for experiment in experiments
    )
    assert {link["run_status"] for link in provenance["links"]} == {"COMPLETED"}
    assert all(link["source_refs"] for link in provenance["links"])
    assert scorecards["validation_state"] == "UNVALIDATED"
    assert scorecards["approval_state"] == "NOT_ELIGIBLE"
    assert all(card["approval_state"] == "NOT_ELIGIBLE" for card in scorecards["candidates"])
    assert not any("approval_score" in card for card in scorecards["candidates"])


@pytest.mark.parametrize("artifact", ["provenance.json", "scorecards.json"])
def test_lineage_artifact_tampering_is_detected(tmp_path: Path, artifact: str) -> None:
    root, dataset, research = _repo(tmp_path)
    result = _run(root, dataset, research)
    path = research / str(result["lab_id"]) / artifact
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact digest mismatch"):
        _run(root, dataset, research)


def test_alternate_repo_root_derives_interpreter_probe_and_cwd(tmp_path: Path) -> None:
    root, dataset, research = _repo(tmp_path)
    observed: dict[str, object] = {}

    def sweep(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        _write_trials(Path(command[command.index("--out") + 1]))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    _run(root, dataset, research, sweep)
    command = observed["command"]
    assert isinstance(command, list)
    assert command[:2] == [
        str(root / "engines/vectorbt/.venv/bin/python"),
        str(root / "engines/vectorbt/probe_sweep.py"),
    ]
    assert observed["cwd"] == root


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            "counts",
            {
                "experiments": 3,
                "trials": 66,
                "completed_trials": 65,
                "failed_trials": 1,
                "evidence_records": 3,
            },
        ),
        ("blockers", []),
        ("score_states", {"data_integrity_and_freshness": "PASS"}),
        ("commands", [["python", "unsafe.py"]]),
        ("mode", "PAPER"),
    ],
)
def test_reuse_rejects_resealed_semantic_field_tampering(
    tmp_path: Path, field: str, replacement: object
) -> None:
    root, dataset, research = _repo(tmp_path)
    result = _run(root, dataset, research)
    result_path = research / str(result["lab_id"]) / "lab_run.json"
    stored = json.loads(result_path.read_text())
    stored[field] = replacement
    _reseal_result(result_path, stored)
    with pytest.raises(RuntimeError):
        _run(root, dataset, research)


def test_reuse_rejects_resealed_evidence_and_inventory_tampering(tmp_path: Path) -> None:
    root, dataset, research = _repo(tmp_path)
    result = _run(root, dataset, research)
    batch_dir = research / str(result["lab_id"])
    evidence_path = batch_dir / "trading_evidence.jsonl"
    rows = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    rows[0]["run_ref"] = "EXP-VECTORBT-B4-F1"
    evidence_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"]["trading_evidence.jsonl"] = _sha256(evidence_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result_path = batch_dir / "lab_run.json"
    stored = json.loads(result_path.read_text())
    stored["artifact_manifest_sha256"] = _sha256(manifest_path)
    _reseal_result(result_path, stored)
    with pytest.raises(RuntimeError, match="evidence semantics"):
        _run(root, dataset, research)

    # A fresh batch proves unrecorded filesystem additions are also rejected.
    root2, dataset2, research2 = _repo(tmp_path / "inventory")
    result2 = _run(root2, dataset2, research2)
    (research2 / str(result2["lab_id"]) / "unexpected.txt").write_text("tamper")
    with pytest.raises(RuntimeError, match="filesystem inventory"):
        _run(root2, dataset2, research2)


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
