"""Run or verify the frozen canonical 67-trial baseline campaign offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_g10_candidate import (  # noqa: E402
    build_method_contract,
    evaluate_family,
)

from tios.evidence import (  # noqa: E402
    ARTIFACT_SCHEMA,
    validate_substantive_research_metadata,
)

DEFAULT_CAMPAIGN = ROOT / "research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml"
CAMPAIGN_ROOT = ROOT / "artifacts/validation/campaigns"
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"
SCOPES = ("b2", "b3", "b4", "all")
FAMILIES = SCOPES[:-1]
EXPECTED_COSTS = {
    "F0/S0": (0.0, 0),
    "F1/S1": (0.001, 1),
    "F1/S2": (0.001, 5),
    "F1/S3": (0.001, 10),
    "F2/S2": (0.0015, 5),
    "F2/S3": (0.0015, 10),
}
EXPECTED_FOLDS = ("WF-2022", "WF-2023", "WF-2024", "WF-2025", "WF-2026-H1")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


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
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("campaign must be a mapping")
    return payload


def _pinned_files(campaign: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    dataset = campaign["scope"]["dataset"]
    engine = campaign["scope"]["engine"]
    yield dataset["file"], dataset["file_sha256"]
    yield dataset["source_manifest"], dataset["source_manifest_sha256"]
    yield dataset["restore_script"], dataset["restore_script_sha256"]
    yield engine["environment_manifest"], engine["environment_manifest_sha256"]
    for item in campaign["candidate_roster"]:
        yield item["canonical_spec"], item["canonical_spec_file_sha256"]
    implementation = campaign["implementation"]
    for key in (
        "extractor",
        "evaluator",
        "method_module",
        "provenance_validator",
        "campaign_runner",
        "method_sources",
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


def _verify_environment(campaign: Mapping[str, Any]) -> None:
    engine = campaign["scope"]["engine"]
    lines = (ROOT / engine["environment_manifest"]).read_text().splitlines()
    expected_python = next(line.split(": ", 1)[1] for line in lines if line.startswith("python: "))
    expected_packages = {line.lower() for line in lines if "==" in line}
    code = """
import importlib.metadata as metadata, json, platform
packages = sorted({
    f"{d.metadata['Name'].lower().replace('_', '-')}=={d.version}"
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
        raise RuntimeError(
            "vectorbt environment drift: "
            f"python={actual['python']!r}, "
            f"missing={sorted(expected_packages - actual_packages)}, "
            f"extra={sorted(actual_packages - expected_packages)}"
        )


def _verify_scope(campaign: Mapping[str, Any]) -> None:
    if (
        campaign.get("execution_authority") != "NONE"
        or campaign.get("network_during_campaign") != "PROHIBITED"
        or campaign.get("credentials_required") is not False
        or campaign.get("venue_connection") != "NONE"
        or campaign.get("orders") != "DISABLED"
        or campaign.get("promotion_eligible") is not False
        or campaign.get("winner_selected") is not False
    ):
        raise RuntimeError("campaign safety boundary changed")
    roster = {item["family"]: item for item in campaign["candidate_roster"]}
    expected_counts = {"b2": 35, "b3": 16, "b4": 16}
    if (
        set(roster) != set(FAMILIES)
        or {family: item["raw_trial_count"] for family, item in roster.items()} != expected_counts
    ):
        raise RuntimeError("campaign roster differs from the frozen 35/16/16 population")
    if campaign["method"]["raw_trial_count"] != sum(expected_counts.values()):
        raise RuntimeError("declared raw trial count is wrong")
    costs = {
        item["id"]: (item["fee_rate_per_side"], item["slippage_bps_per_side"])
        for item in campaign["method"]["cost_model"]["scenarios"]
    }
    if costs != EXPECTED_COSTS or campaign["method"]["cost_model"]["selection_scenario"] != (
        "F1/S1"
    ):
        raise RuntimeError("cost surface differs from the frozen six-cell grid")
    folds = campaign["method"]["walk_forward"]["folds"]
    if tuple(fold["id"] for fold in folds) != EXPECTED_FOLDS:
        raise RuntimeError("walk-forward folds differ from the frozen calendar")
    if campaign["method"]["prospective_holdout"]["current_campaign_consumes_holdout"]:
        raise RuntimeError("V2 must not consume its prospective holdout")
    if campaign["pre_freeze_exposure"]["status"] != (
        "IMPLEMENTATION_SMOKE_ACCESSED_FULL_HISTORICAL_DATA"
    ):
        raise RuntimeError("pre-freeze full-history exposure must remain disclosed")
    if campaign["search_lineage"]["upstream_family_admission_complete"] is not False:
        raise RuntimeError("campaign may not claim complete upstream search lineage")


def _verify_dataset_offline(campaign: Mapping[str, Any]) -> None:
    dataset = campaign["scope"]["dataset"]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / dataset["restore_script"]),
            "--manifest",
            str(ROOT / dataset["source_manifest"]),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    if report != {
        "dataset_id": dataset["dataset_id"],
        "fetched_archives": 0,
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "status": "PASS",
    }:
        raise RuntimeError("offline dataset verification returned an unexpected result")


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


def preflight(campaign_path: Path, *, require_clean: bool = True) -> dict[str, object]:
    campaign = _load_campaign(campaign_path)
    if campaign.get("status") != "PREREGISTERED_NOT_RUN":
        raise RuntimeError("campaign is not in PREREGISTERED_NOT_RUN state")
    _verify_scope(campaign)
    _verify_pins(campaign)
    _verify_environment(campaign)
    _verify_dataset_offline(campaign)
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
        "output_dir": output_dir,
    }


def _invoke_extractor(
    campaign: Mapping[str, Any], output: Path, generated_at: str
) -> dict[str, Path]:
    dataset = ROOT / campaign["scope"]["dataset"]["file"]
    extractor = ROOT / campaign["implementation"]["extractor"]
    subprocess.run(
        [
            str(ENGINE_PYTHON),
            str(extractor),
            "--dataset",
            str(dataset),
            "--out",
            str(output),
            "--generated-at",
            generated_at,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {scope: output / f"canonical_returns_{scope}.json" for scope in SCOPES}


def _cost_ids(payload: Mapping[str, Any]) -> set[str]:
    surface = payload.get("cost_surface")
    if isinstance(surface, Mapping):
        cells = surface.get("cells")
        if isinstance(cells, list):
            return {str(item["scenario"]) for item in cells}
        return {str(key) for key in surface}
    if isinstance(surface, list):
        return {str(item["scenario"]) for item in surface}
    return set()


def _fold_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    walk = payload.get("walk_forward")
    if not isinstance(walk, Mapping):
        return ()
    folds = walk.get("folds")
    if not isinstance(folds, list):
        return ()
    return tuple(str(item.get("fold_id", item.get("id"))) for item in folds)


def _load_and_validate_payloads(
    campaign: Mapping[str, Any], paths: Mapping[str, Path]
) -> dict[str, dict[str, Any]]:
    expected_counts = {
        item["family"]: item["raw_trial_count"] for item in campaign["candidate_roster"]
    } | {"all": campaign["method"]["raw_trial_count"]}
    payloads: dict[str, dict[str, Any]] = {}
    required = {
        "trials",
        "slice_count",
        "slice_length_bars",
        "bars_total",
        "bars_excluded_tail",
        "sample_count",
        "return_correlation_observation_count",
        "return_correlations_upper_triangle",
        "execution_audit",
        "cost_surface",
        "walk_forward",
    }
    for scope, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"extractor did not emit {path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not required.issubset(payload) or len(payload["trials"]) != expected_counts[scope]:
            raise RuntimeError(f"{scope}: extractor payload is incomplete")
        if payload.get("baseline", payload.get("scope")) != scope:
            raise RuntimeError(f"{scope}: extractor scope label is wrong")
        if (
            payload.get("execution_authority") != "NONE"
            or payload.get("promotion_eligible") is not False
            or payload.get("winner_selected") is not False
            or payload["bars_total"] != campaign["scope"]["dataset"]["rows"]
            or payload["sample_count"] != campaign["scope"]["dataset"]["rows"]
        ):
            raise RuntimeError(f"{scope}: extractor safety or dataset declaration is wrong")
        if _cost_ids(payload) != set(EXPECTED_COSTS):
            raise RuntimeError(f"{scope}: cost surface is incomplete")
        cost_surface = payload["cost_surface"]
        cells = cost_surface["cells"]
        observed_costs = {
            cell["scenario"]: (
                cell["fee_rate_per_side"],
                cell["slippage_bps_per_side"],
            )
            for cell in cells
        }
        if (
            observed_costs != EXPECTED_COSTS
            or cost_surface["primary_statistical_cell"] != "F1/S1"
            or any(len(cell["trials"]) != expected_counts[scope] for cell in cells)
            or any(
                "turnover_on_initial_cash" not in trial or "gross_executed_notional" not in trial
                for cell in cells
                for trial in cell["trials"]
            )
        ):
            raise RuntimeError(f"{scope}: cost cell contract differs from the freeze")
        if _fold_ids(payload) != EXPECTED_FOLDS:
            raise RuntimeError(f"{scope}: walk-forward folds are incomplete")
        if payload["walk_forward"].get("status") != "COMPLETED":
            raise RuntimeError(f"{scope}: walk-forward did not complete")
        audit = payload["execution_audit"]
        if audit.get("non_adjacent_transitions") != 7 or audit.get("estimated_missing_bars") != 213:
            raise RuntimeError(f"{scope}: dataset gap audit differs from the freeze")
        expected_correlations = expected_counts[scope] * (expected_counts[scope] - 1) // 2
        if len(payload["return_correlations_upper_triangle"]) != expected_correlations:
            raise RuntimeError(f"{scope}: return correlation population is incomplete")
        if scope == "b3":
            structural = {
                trial["trial_key"]
                for trial in payload["trials"]
                if trial["structural_zero_trade_retained"]
            }
            if structural != {
                "window=3,deviation=1.5",
                "window=3,deviation=2",
                "window=5,deviation=2",
            }:
                raise RuntimeError("b3: structural zero-trade retention differs from the freeze")
        payloads[scope] = payload
    return payloads


def _metadata(
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
            "manifest_sha256": dataset["source_manifest_sha256"],
            "range_start": dataset["range_start_utc"],
            "range_end": dataset["range_end_utc"],
            "availability": dataset["availability"],
        },
        "strategy": {
            "canonical_spec_sha256": roster["canonical_spec_file_sha256"],
            "parameters": {
                key: value
                for key, value in roster.items()
                if key
                not in {
                    "family",
                    "strategy_id",
                    "canonical_spec",
                    "canonical_spec_file_sha256",
                }
            },
            "search_campaign_ref": (
                f"{_relative(context['campaign_path'])}@sha256:{context['campaign_sha256']}"
            ),
            "implementation_conformance": campaign["scope"]["semantic_conformance"],
        },
        "method": {
            "cost_model": campaign["method"]["cost_model"],
            "split": {
                "cscv": campaign["method"]["cscv"],
                "walk_forward": campaign["method"]["walk_forward"],
                "prospective_holdout": campaign["method"]["prospective_holdout"],
            },
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
    generated_at = datetime.now(tz=UTC).isoformat()
    CAMPAIGN_ROOT.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{campaign['campaign_id']}.", dir=CAMPAIGN_ROOT))
    try:
        prereg_path = temp_dir / f"preregistration_{context['campaign_sha256']}.yaml"
        prereg_path.write_bytes(Path(context["campaign_path"]).read_bytes())
        work = temp_dir / "work_inputs"
        paths = _invoke_extractor(campaign, work, generated_at)
        payloads = _load_and_validate_payloads(campaign, paths)
        numeric = {scope: evaluate_family(payload) for scope, payload in payloads.items()}
        lineage = {"status": "INCOMPLETE", "effective_independent_trials": None}
        method_contract = build_method_contract(lineage, numeric)
        if method_contract["status"] != "METHOD_BLOCKED":
            raise RuntimeError("incomplete upstream lineage must keep G10 method-blocked")

        input_records: dict[str, dict[str, str]] = {}
        for scope, source in paths.items():
            digest = sha256(source)
            destination = temp_dir / "inputs" / f"{scope}_trials_{digest}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            input_records[scope] = {
                "all_trials_ref": _relative(output_dir / destination.relative_to(temp_dir)),
                "all_trials_sha256": digest,
            }
        shutil.rmtree(work)

        family_records: dict[str, object] = {}
        for family in FAMILIES:
            payload = payloads[family]
            result: dict[str, object] = {
                "schema": "tios-canonical-baseline-family-result-v2",
                "campaign_id": campaign["campaign_id"],
                "preregistration_sha256": context["campaign_sha256"],
                "generated_at_utc": generated_at,
                "family": family,
                "declared_v2_scope_lineage": {
                    "status": "COMPLETE",
                    "raw_trial_count": len(payload["trials"]),
                    **input_records[family],
                },
                "upstream_family_admission": {
                    "status": "INCOMPLETE",
                    "promotion_effect": "METHOD_BLOCKED",
                },
                "semantic_conformance": campaign["scope"]["semantic_conformance"],
                "execution_audit": payload["execution_audit"],
                "cost_surface": payload["cost_surface"],
                "walk_forward": payload["walk_forward"],
                "method_contract": method_contract,
                "numeric_result": numeric[family],
                "g10_gate_status": "METHOD_BLOCKED",
                "execution_authority": "NONE",
                "promotion_eligible": False,
                "winner_selected": False,
            }
            result_path, result_hash = _write_hashed_json(
                temp_dir / "families", f"{family}_result", result
            )
            metadata = _metadata(
                context=context,
                family=family,
                output_sha256=result_hash,
                all_trials_ref=input_records[family]["all_trials_ref"],
                generated_at=generated_at,
            )
            metadata_path, metadata_hash = _write_hashed_json(
                temp_dir / "families", f"{family}_metadata", metadata
            )
            family_records[family] = {
                "numeric_verdict": numeric[family]["numeric_verdict"],
                "g10_gate_status": "METHOD_BLOCKED",
                "result_ref": _relative(output_dir / result_path.relative_to(temp_dir)),
                "result_sha256": result_hash,
                "metadata_ref": _relative(output_dir / metadata_path.relative_to(temp_dir)),
                "metadata_sha256": metadata_hash,
                **input_records[family],
            }

        wide_payload = payloads["all"]
        campaign_result: dict[str, object] = {
            "schema": "tios-canonical-baseline-campaign-result-v2",
            "campaign_id": campaign["campaign_id"],
            "preregistration_sha256": context["campaign_sha256"],
            "generated_at_utc": generated_at,
            "declared_v2_scope_lineage": {
                "status": "COMPLETE",
                "raw_trial_count": len(wide_payload["trials"]),
                **input_records["all"],
            },
            "upstream_family_admission_complete": False,
            "execution_audit": wide_payload["execution_audit"],
            "cost_surface": wide_payload["cost_surface"],
            "walk_forward": wide_payload["walk_forward"],
            "family_numeric_verdicts": {
                family: numeric[family]["numeric_verdict"] for family in FAMILIES
            },
            "campaign_wide_numeric_result": numeric["all"],
            "method_contract": method_contract,
            "pre_freeze_exposure": campaign["pre_freeze_exposure"],
            "prospective_holdout": campaign["method"]["prospective_holdout"],
            "g10_gate_status": "METHOD_BLOCKED",
            "execution_authority": "NONE",
            "promotion_eligible": False,
            "winner_selected": False,
            "effect": (
                "Offline canonical-rule diagnostics only. Missing upstream search lineage, "
                "empirical S4 execution evidence, and future prospective observations prevent "
                "promotion regardless of numeric output."
            ),
        }
        campaign_result_path, campaign_result_hash = _write_hashed_json(
            temp_dir, "campaign_result", campaign_result
        )
        campaign_record = {
            "numeric_verdict": numeric["all"]["numeric_verdict"],
            "g10_gate_status": "METHOD_BLOCKED",
            "result_ref": _relative(output_dir / campaign_result_path.relative_to(temp_dir)),
            "result_sha256": campaign_result_hash,
            **input_records["all"],
        }
        index: dict[str, object] = {
            "schema": "tios-canonical-baseline-campaign-index-v2",
            "campaign_id": campaign["campaign_id"],
            "status": "COMPLETED",
            "generated_at_utc": generated_at,
            "git_commit": context["git_commit"],
            "git_dirty_at_start": context["git_dirty"],
            "preregistration_ref": _relative(output_dir / prereg_path.name),
            "preregistration_sha256": context["campaign_sha256"],
            "declared_v2_scope_lineage": "COMPLETE",
            "upstream_family_admission_complete": False,
            "raw_trial_count": campaign["method"]["raw_trial_count"],
            "cost_scenario_count": len(EXPECTED_COSTS),
            "walk_forward_fold_count": len(EXPECTED_FOLDS),
            "deterministic_recomputation_supported": True,
            "g10_gate_status": "METHOD_BLOCKED",
            "families": family_records,
            "campaign_wide": campaign_record,
            "pre_freeze_exposure_status": campaign["pre_freeze_exposure"]["status"],
            "prospective_holdout_status": campaign["method"]["prospective_holdout"]["status"],
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


def _verify_record(record: Mapping[str, str], label: str, *, metadata: bool) -> None:
    for ref_key, hash_key in (
        ("result_ref", "result_sha256"),
        ("all_trials_ref", "all_trials_sha256"),
    ):
        if sha256(ROOT / record[ref_key]) != record[hash_key]:
            raise RuntimeError(f"{label}: {ref_key} hash mismatch")
    if metadata:
        metadata_path = ROOT / record["metadata_ref"]
        if sha256(metadata_path) != record["metadata_sha256"]:
            raise RuntimeError(f"{label}: metadata hash mismatch")
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        validate_substantive_research_metadata(payload)
        if payload["output_sha256"] != record["result_sha256"]:
            raise RuntimeError(f"{label}: metadata/output hash mismatch")


def verify_campaign(campaign_path: Path) -> Path:
    campaign = _load_campaign(campaign_path)
    _verify_scope(campaign)
    _verify_pins(campaign)
    output_dir = CAMPAIGN_ROOT / campaign["campaign_id"]
    indexes = list(output_dir.glob("campaign_index_*.json"))
    if len(indexes) != 1:
        raise RuntimeError("exactly one immutable campaign index is required")
    index_path = indexes[0]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if sha256(index_path) != index_path.stem.rsplit("_", 1)[1]:
        raise RuntimeError("campaign index hash mismatch")
    prereg = ROOT / index["preregistration_ref"]
    if sha256(prereg) != index["preregistration_sha256"]:
        raise RuntimeError("preregistration snapshot hash mismatch")
    for family, record in index["families"].items():
        _verify_record(record, family, metadata=True)
    _verify_record(index["campaign_wide"], "all", metadata=False)
    if campaign.get("status") == "COMPLETED":
        completion = campaign["completion"]
        if (
            completion["index_ref"] != _relative(index_path)
            or completion["index_sha256"] != sha256(index_path)
            or completion["preregistration_sha256"] != index["preregistration_sha256"]
        ):
            raise RuntimeError("campaign completion record differs from immutable index")
    return index_path


def recompute_verify_campaign(campaign_path: Path) -> Path:
    index_path = verify_campaign(campaign_path)
    campaign = _load_campaign(campaign_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    temp_dir = Path(tempfile.mkdtemp(prefix=".canonical-recompute.", dir=CAMPAIGN_ROOT))
    try:
        paths = _invoke_extractor(campaign, temp_dir, index["generated_at_utc"])
        _load_and_validate_payloads(campaign, paths)
        records = dict(index["families"]) | {"all": index["campaign_wide"]}
        for scope, path in paths.items():
            if sha256(path) != records[scope]["all_trials_sha256"]:
                raise RuntimeError(f"{scope}: deterministic recomputation mismatch")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--recompute-verify", action="store_true")
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
    elif args.recompute_verify:
        index = recompute_verify_campaign(args.campaign)
        print(
            json.dumps(
                {"status": "RECOMPUTE_VERIFY_PASS", "index": _relative(index)}, sort_keys=True
            )
        )
    else:
        index = run_campaign(args.campaign)
        print(json.dumps({"status": "COMPLETED", "index": _relative(index)}, sort_keys=True))


if __name__ == "__main__":
    main()
