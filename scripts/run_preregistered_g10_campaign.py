"""Run and verify the frozen 66-trial G10 campaign without venue or network access."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_g10_candidate import BASELINES, build_evidence, sha256  # noqa: E402

from tios.evidence import (  # noqa: E402
    ARTIFACT_SCHEMA,
    validate_substantive_research_metadata,
)

DEFAULT_CAMPAIGN = ROOT / "research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml"
CAMPAIGN_ROOT = ROOT / "artifacts/validation/campaigns"
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _write_hashed_json(
    directory: Path, stem: str, payload: Mapping[str, object]
) -> tuple[Path, str]:
    encoded = _json_bytes(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    path = directory / f"{stem}_{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return path, digest


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _load_campaign(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "research").resolve()):
        raise RuntimeError("campaign must be inside research/")
    payload = yaml.safe_load(resolved.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError("campaign must be a mapping")
    return payload


def _pinned_files(campaign: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    scope = campaign["scope"]
    dataset = scope["dataset"]
    engine = scope["engine"]
    lab = scope["retained_population"]
    yield dataset["file"], dataset["file_sha256"]
    yield dataset["manifest"], dataset["manifest_sha256"]
    yield engine["environment_manifest"], engine["environment_manifest_sha256"]
    for key in ("lab_run", "manifest", "trial_ledger"):
        yield lab[key], lab[f"{key}_sha256"]
    for item in lab["trial_parquets"].values():
        yield item["file"], item["file_sha256"]
    for item in campaign["candidate_roster"]:
        yield item["canonical_spec"], item["canonical_spec_file_sha256"]
    implementation = campaign["implementation"]
    for key in (
        "extractor",
        "evaluator",
        "method_module",
        "provenance_validator",
        "campaign_runner",
    ):
        yield implementation[key], implementation[f"{key}_sha256"]


def _verify_pins(campaign: Mapping[str, Any]) -> None:
    mismatches = [
        path
        for path, expected in _pinned_files(campaign)
        if not (ROOT / path).is_file() or sha256(ROOT / path) != expected
    ]
    if mismatches:
        raise RuntimeError(f"pinned file mismatch: {', '.join(mismatches)}")


def _git_state() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def _extractor_constants(path: Path) -> dict[str, object]:
    wanted = {
        "FEES",
        "INIT_CASH",
        "SLICES",
        "B2_FAST",
        "B2_SLOW",
        "B3_WINDOW",
        "B3_DEVIATION",
        "B4_LOOKBACK",
        "B4_EXIT_WINDOW",
    }
    values: dict[str, object] = {}
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in wanted:
            values[target.id] = ast.literal_eval(node.value)
    if set(values) != wanted:
        raise RuntimeError("extractor constants are incomplete")
    return values


def _verify_environment(campaign: Mapping[str, Any]) -> None:
    engine = campaign["scope"]["engine"]
    lines = (ROOT / engine["environment_manifest"]).read_text().splitlines()
    expected_python = next(line.split(": ", 1)[1] for line in lines if line.startswith("python: "))
    expected_packages = {line.lower() for line in lines if "==" in line}
    code = """
import importlib.metadata as metadata, json, platform
packages = sorted({
    f\"{d.metadata['Name'].lower().replace('_', '-')}=={d.version}\"
    for d in metadata.distributions()
})
print(json.dumps({'python': 'Python ' + platform.python_version(), 'packages': packages}))
"""
    actual = json.loads(
        subprocess.run(
            [str(ENGINE_PYTHON), "-c", code],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    actual_packages = set(actual["packages"])
    if actual["python"] != expected_python or actual_packages != expected_packages:
        missing = sorted(expected_packages - actual_packages)
        extra = sorted(actual_packages - expected_packages)
        raise RuntimeError(
            f"vectorbt environment drift: python={actual['python']!r}, "
            f"missing={missing}, extra={extra}"
        )


def _verify_declared_scope(campaign: Mapping[str, Any]) -> None:
    roster = {item["family"]: item for item in campaign["candidate_roster"]}
    if set(roster) != set(BASELINES):
        raise RuntimeError("campaign families differ from evaluator families")
    constants = _extractor_constants(ROOT / campaign["implementation"]["extractor"])
    expected_parameters = {
        "b2": {"fast": list(constants["B2_FAST"]), "slow": list(constants["B2_SLOW"])},
        "b3": {
            "window": list(constants["B3_WINDOW"]),
            "deviation": list(constants["B3_DEVIATION"]),
        },
        "b4": {
            "lookback": list(constants["B4_LOOKBACK"]),
            "exit_window": list(constants["B4_EXIT_WINDOW"]),
        },
    }
    counts = {
        "b2": sum(
            fast < slow
            for fast in expected_parameters["b2"]["fast"]
            for slow in expected_parameters["b2"]["slow"]
        ),
        "b3": len(expected_parameters["b3"]["window"])
        * len(expected_parameters["b3"]["deviation"]),
        "b4": len(expected_parameters["b4"]["lookback"])
        * len(expected_parameters["b4"]["exit_window"]),
    }
    for family, item in roster.items():
        declared = {key: value for key, value in item["parameters"].items() if key != "constraint"}
        if declared != expected_parameters[family] or item["raw_trial_count"] != counts[family]:
            raise RuntimeError(f"{family}: roster differs from extractor")
    if sum(counts.values()) != campaign["method"]["raw_trial_count"]:
        raise RuntimeError("declared raw trial count is wrong")
    cost = campaign["method"]["cost_model"]
    split = campaign["method"]["split"]
    if (
        float(cost["fee_rate_per_side"]) != constants["FEES"]
        or float(cost["initial_cash"]) != constants["INIT_CASH"]
        or split["cscv_contiguous_slice_count"] != constants["SLICES"]
    ):
        raise RuntimeError("cost or split contract differs from extractor")


def _verify_dataset_and_lab(campaign: Mapping[str, Any]) -> Path:
    scope = campaign["scope"]
    dataset = scope["dataset"]
    manifest = json.loads((ROOT / dataset["manifest"]).read_text())
    table = manifest["tables"][Path(dataset["file"]).stem]
    if (
        table["parquet_sha256"] != dataset["file_sha256"]
        or table["rows"] != scope["split_observations"]["bars_total"]
    ):
        raise RuntimeError("dataset declaration differs from frozen manifest")
    lab = scope["retained_population"]
    lab_dir = (ROOT / lab["lab_run"]).parent
    if lab_dir.name != lab["lab_id"]:
        raise RuntimeError("retained lab id/path mismatch")
    records = [json.loads(line) for line in (ROOT / lab["trial_ledger"]).read_text().splitlines()]
    runs = [row["record"] for row in records if row.get("kind") == "run"]
    if len(runs) != campaign["method"]["raw_trial_count"] or any(
        row["status"] != "COMPLETED" for row in runs
    ):
        raise RuntimeError("retained run population is incomplete")
    experiments = lab["experiment_ids_by_family"]
    roster = {item["family"]: item["raw_trial_count"] for item in campaign["candidate_roster"]}
    for family, experiment_id in experiments.items():
        family_runs = [row for row in runs if row["experiment_id"] == experiment_id]
        if len(family_runs) != roster[family] or {row["scenario"] for row in family_runs} != {
            "F1/S0"
        }:
            raise RuntimeError(f"{family}: retained lab population differs from campaign")
    return lab_dir


def preflight(campaign_path: Path, *, require_clean: bool = True) -> dict[str, object]:
    campaign = _load_campaign(campaign_path)
    if campaign.get("status") != "PREREGISTERED_NOT_RUN":
        raise RuntimeError("campaign is not in PREREGISTERED_NOT_RUN state")
    if (
        campaign.get("execution_authority") != "NONE"
        or campaign.get("promotion_eligible") is not False
        or campaign.get("winner_selected") is not False
    ):
        raise RuntimeError("campaign safety boundary changed")
    _verify_pins(campaign)
    _verify_environment(campaign)
    _verify_declared_scope(campaign)
    lab_dir = _verify_dataset_and_lab(campaign)
    commit, dirty = _git_state()
    if require_clean and dirty:
        raise RuntimeError("campaign must start from a clean Git commit")
    output_dir = CAMPAIGN_ROOT / campaign["campaign_id"]
    if output_dir.exists():
        raise RuntimeError(f"campaign output already exists: {output_dir}")
    return {
        "campaign": campaign,
        "campaign_path": campaign_path.resolve(),
        "campaign_sha256": sha256(campaign_path.resolve()),
        "git_commit": commit,
        "git_dirty": dirty,
        "lab_dir": lab_dir,
        "output_dir": output_dir,
    }


def _family_metadata(
    *,
    context: Mapping[str, object],
    family: str,
    output_sha256: str,
    all_trials_ref: str,
    generated_at: str,
) -> dict[str, object]:
    campaign = context["campaign"]
    assert isinstance(campaign, Mapping)
    roster = next(item for item in campaign["candidate_roster"] if item["family"] == family)
    dataset = campaign["scope"]["dataset"]
    table = json.loads((ROOT / dataset["manifest"]).read_text())["tables"][
        Path(dataset["file"]).stem
    ]
    implementation = campaign["implementation"]
    code_hashes = {
        implementation[key]: implementation[f"{key}_sha256"]
        for key in (
            "campaign_runner",
            "evaluator",
            "extractor",
            "method_module",
            "provenance_validator",
        )
    }
    metadata: dict[str, object] = {
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_id": f"{campaign['campaign_id']}-{family.upper()}-{output_sha256[:12]}",
        "generated_at": generated_at,
        "code": {
            "git_commit": context["git_commit"],
            "dirty": context["git_dirty"],
            "module_sha256": implementation["campaign_runner_sha256"],
            "module_sha256_by_path": code_hashes,
        },
        "dataset": {
            "dataset_id": dataset["dataset_id"],
            "data_sha256": dataset["file_sha256"],
            "manifest_sha256": dataset["manifest_sha256"],
            "range_start": table["coverage_start_utc"],
            "range_end": table["coverage_end_utc"],
            "availability": dataset["availability"],
        },
        "strategy": {
            "canonical_spec_sha256": roster["canonical_spec_file_sha256"],
            "parameters": roster["parameters"],
            "search_campaign_ref": (
                f"{_relative(context['campaign_path'])}@sha256:{context['campaign_sha256']}"
            ),
            "implementation_conformance": campaign["scope"]["semantic_conformance"],
        },
        "method": {
            "cost_model": campaign["method"]["cost_model"],
            "split": campaign["method"]["split"],
            "selection_metric": campaign["method"]["governed_selection_metric"],
            "selection_scope": campaign["method"]["selection_scope"],
            "all_trials_population_ref": all_trials_ref,
        },
        "output_sha256": output_sha256,
        "execution_authority": "NONE",
        "promotion_eligible": False,
    }
    validate_substantive_research_metadata(metadata)
    return metadata


def run_campaign(campaign_path: Path) -> Path:
    context = preflight(campaign_path)
    campaign = context["campaign"]
    assert isinstance(campaign, Mapping)
    output_dir = context["output_dir"]
    assert isinstance(output_dir, Path)
    CAMPAIGN_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{campaign['campaign_id']}.", dir=CAMPAIGN_ROOT))
    try:
        prereg_path = temp_dir / f"preregistration_{context['campaign_sha256']}.yaml"
        prereg_path.write_bytes(Path(context["campaign_path"]).read_bytes())
        work_inputs = temp_dir / "work_inputs"
        evidence = build_evidence(context["lab_dir"], work_inputs)
        expected_counts = {
            item["family"]: item["raw_trial_count"] for item in campaign["candidate_roster"]
        }
        if evidence["search_lineage"]["raw_trial_count_retained"] != sum(expected_counts.values()):
            raise RuntimeError("evaluator did not retain the complete declared population")
        generated_at = str(evidence["generated_at_utc"])
        family_records: dict[str, object] = {}
        for family in BASELINES:
            source = work_inputs / f"g10_returns_{family}.json"
            payload = json.loads(source.read_text())
            if len(payload["trials"]) != expected_counts[family]:
                raise RuntimeError(f"{family}: extractor trial count differs from campaign")
            input_hash = sha256(source)
            final_input = temp_dir / "inputs" / f"{family}_trials_{input_hash}.json"
            final_input.parent.mkdir(parents=True, exist_ok=True)
            source.replace(final_input)
            input_ref = _relative(output_dir / final_input.relative_to(temp_dir))
            family_result: dict[str, object] = {
                "schema": "tios-g10-preregistered-family-result-v1",
                "campaign_id": campaign["campaign_id"],
                "preregistration_sha256": context["campaign_sha256"],
                "generated_at_utc": generated_at,
                "family": family,
                "declared_scope_lineage": {
                    "status": "COMPLETE",
                    "raw_trial_count": expected_counts[family],
                    "all_trials_population_ref": input_ref,
                    "all_trials_population_sha256": input_hash,
                },
                "upstream_family_admission": {
                    "status": "INCOMPLETE",
                    "promotion_effect": "METHOD_BLOCKED",
                },
                "semantic_conformance": campaign["scope"]["semantic_conformance"],
                "method_contract": evidence["method_contract"],
                "numeric_result": evidence["families"][family],
                "g10_gate_status": "METHOD_BLOCKED",
                "execution_authority": "NONE",
                "promotion_eligible": False,
                "winner_selected": False,
                "effect": (
                    "Legacy accelerator-proxy diagnostic only; not canonical strategy "
                    "conformance, promotion evidence, or execution authority."
                ),
            }
            result_path, result_hash = _write_hashed_json(
                temp_dir / "families", f"{family}_result", family_result
            )
            result_ref = _relative(output_dir / result_path.relative_to(temp_dir))
            metadata = _family_metadata(
                context=context,
                family=family,
                output_sha256=result_hash,
                all_trials_ref=input_ref,
                generated_at=generated_at,
            )
            metadata_path, metadata_hash = _write_hashed_json(
                temp_dir / "families", f"{family}_metadata", metadata
            )
            family_records[family] = {
                "numeric_verdict": evidence["families"][family]["numeric_verdict"],
                "g10_gate_status": "METHOD_BLOCKED",
                "result_ref": result_ref,
                "result_sha256": result_hash,
                "metadata_ref": _relative(output_dir / metadata_path.relative_to(temp_dir)),
                "metadata_sha256": metadata_hash,
                "all_trials_ref": input_ref,
                "all_trials_sha256": input_hash,
            }
        shutil.rmtree(work_inputs)
        index: dict[str, object] = {
            "schema": "tios-g10-preregistered-campaign-index-v1",
            "campaign_id": campaign["campaign_id"],
            "status": "COMPLETED",
            "generated_at_utc": generated_at,
            "git_commit": context["git_commit"],
            "git_dirty_at_start": context["git_dirty"],
            "preregistration_ref": _relative(output_dir / prereg_path.name),
            "preregistration_sha256": context["campaign_sha256"],
            "declared_scope_lineage": "COMPLETE",
            "upstream_family_admission_complete": False,
            "selection_scope": campaign["method"]["selection_scope"],
            "raw_trial_count": sum(expected_counts.values()),
            "g10_gate_status": "METHOD_BLOCKED",
            "families": family_records,
            "execution_authority": "NONE",
            "promotion_eligible": False,
            "winner_selected": False,
            "reproducibility_limitations": campaign["scope"]["reproducibility_limitations"],
        }
        index_path, _ = _write_hashed_json(temp_dir, "campaign_index", index)
        temp_dir.replace(output_dir)
        return output_dir / index_path.name
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def verify_campaign(campaign_path: Path) -> Path:
    campaign = _load_campaign(campaign_path)
    output_dir = CAMPAIGN_ROOT / campaign["campaign_id"]
    indexes = list(output_dir.glob("campaign_index_*.json"))
    if len(indexes) != 1:
        raise RuntimeError("exactly one immutable campaign index is required")
    index_path = indexes[0]
    index = json.loads(index_path.read_text())
    if sha256(index_path) != index_path.stem.rsplit("_", 1)[1]:
        raise RuntimeError("campaign index hash mismatch")
    prereg = ROOT / index["preregistration_ref"]
    if sha256(prereg) != index["preregistration_sha256"]:
        raise RuntimeError("preregistration snapshot hash mismatch")
    for family, record in index["families"].items():
        result = ROOT / record["result_ref"]
        metadata_path = ROOT / record["metadata_ref"]
        all_trials = ROOT / record["all_trials_ref"]
        if sha256(result) != record["result_sha256"]:
            raise RuntimeError(f"{family}: result hash mismatch")
        if sha256(metadata_path) != record["metadata_sha256"]:
            raise RuntimeError(f"{family}: metadata hash mismatch")
        if sha256(all_trials) != record["all_trials_sha256"]:
            raise RuntimeError(f"{family}: all-trials hash mismatch")
        metadata = json.loads(metadata_path.read_text())
        validate_substantive_research_metadata(metadata)
        if metadata["output_sha256"] != record["result_sha256"]:
            raise RuntimeError(f"{family}: metadata/output hash mismatch")
    if campaign["status"] == "COMPLETED":
        completion = campaign["completion"]
        if (
            completion["index_ref"] != _relative(index_path)
            or completion["index_sha256"] != sha256(index_path)
            or completion["preregistration_sha256"] != index["preregistration_sha256"]
        ):
            raise RuntimeError("campaign completion record differs from immutable index")
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        context = preflight(args.campaign)
        print(
            json.dumps(
                {
                    "campaign_id": context["campaign"]["campaign_id"],
                    "status": "PREFLIGHT_PASS",
                    "git_commit": context["git_commit"],
                    "network": "NOT_USED",
                    "execution_authority": "NONE",
                },
                sort_keys=True,
            )
        )
    elif args.verify_only:
        index = verify_campaign(args.campaign)
        print(json.dumps({"status": "VERIFY_PASS", "index": _relative(index)}, sort_keys=True))
    else:
        index = run_campaign(args.campaign)
        print(json.dumps({"status": "COMPLETED", "index": _relative(index)}, sort_keys=True))


if __name__ == "__main__":
    main()
