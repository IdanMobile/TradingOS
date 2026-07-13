"""Candidate-specific G10 PBO/DSR evaluation with independent recomputation.

Completes the remaining half of T-009-04 (RG-07): runs the production G10 gate
against the retained B2/B3/B4 trial populations. The engine-side extractor
(`engines/vectorbt/g10_returns.py`, subprocess — core never imports engines)
rebuilds the exact sweep and emits per-trial slice returns; this script

1. verifies the dataset against the frozen manifest;
2. verifies recomputed per-trial `total_return`/`trades` match the retained
   research-lab Parquet exactly (ties the G10 inputs to the retained population);
3. uses non-annualized per-bar Sharpe for candidate selection, both CSCV halves,
   and DSR, retaining slice sufficient statistics and trial-return correlations;
4. independently recomputes both statistics with the separate implementations in
   this file (different combination enumeration, erf-based normal CDF, two-pass
   variance) and requires agreement within 1e-9;
5. writes `artifacts/validation/G10_CANDIDATE_EVIDENCE_<date>.json` with the
   known hierarchy, explicit missing upstream stages, and fail-closed status.

Offline research only. A PASS verdict here never promotes a strategy by itself:
it still requires validation-stats-specialist review (RG-07 reverify rule) and
every other promotion gate.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from itertools import combinations
from math import erf, sqrt
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    implied_independent_trials,
    probability_of_backtest_overfitting_from_return_statistics,
    sharpe_variance_from_trials,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/normalized/BTCUSDT_5m.parquet"
FROZEN_MANIFEST = ROOT / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
LAB_ROOT = ROOT / "artifacts/research_lab/v0"
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"
EXTRACTOR = ROOT / "engines/vectorbt/g10_returns.py"
ENGINE_ENV_MANIFEST = ROOT / "engines/vectorbt/env_manifest.txt"
OUT_DIR = ROOT / "artifacts/validation/g10_candidate"
BASELINES = ("b2", "b3", "b4")
SPEC_FILES = {
    "b2": ROOT / "fixtures/strategies/baselines/B2_ma_crossover.yaml",
    "b3": ROOT / "fixtures/strategies/baselines/B3_bollinger_mean_reversion.yaml",
    "b4": ROOT / "fixtures/strategies/baselines/B4_volatility_breakout.yaml",
}
TOLERANCE = 1e-9
# Conventional confidence thresholds from the primary papers (Bailey & López de
# Prado). Conservative: both must hold for PASS, and a PASS still requires
# stats-specialist review before it counts toward promotion (RG-07).
DSR_PASS_MINIMUM = 0.95
PBO_PASS_MAXIMUM = 0.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _normal_inv_cdf(probability: float) -> float:
    """Bisection inverse of the erf-based CDF — independent of statistics.NormalDist."""
    low, high = -40.0, 40.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if _normal_cdf(middle) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def independent_pbo(matrix: list[list[float]]) -> dict[str, Any]:
    """CSCV PBO re-derived independently (index-set enumeration over test halves)."""
    slice_count = len(matrix[0])
    trial_count = len(matrix)
    half = slice_count // 2
    logits: list[float] = []
    from math import log

    for test_columns in combinations(range(slice_count), half):
        test = frozenset(test_columns)
        train = [i for i in range(slice_count) if i not in test]
        # Enumerating TEST halves visits the same split family as enumerating
        # TRAIN halves (complementation), in a different order; PBO is order-free.
        train_scores = [sum(row[i] for i in train) / len(train) for row in matrix]
        best = max(range(trial_count), key=lambda i: (train_scores[i], -i))
        test_scores = [sum(row[i] for i in test) / half for row in matrix]
        rank = 1 + sum(score < test_scores[best] for score in test_scores)
        omega = rank / (trial_count + 1)
        logits.append(log(omega) - log(1.0 - omega))
    return {
        "split_count": len(logits),
        "pbo": sum(value <= 0 for value in logits) / len(logits),
        "mean_logit": sum(logits) / len(logits),
    }


def _independent_sharpe(statistics: list[list[float]]) -> float:
    count = sum(int(item[0]) for item in statistics)
    total = sum(float(item[1]) for item in statistics)
    squares = sum(float(item[2]) for item in statistics)
    if count < 2:
        raise ValueError("invalid retained return statistics")
    sample_variance = (squares - total * total / count) / (count - 1)
    if sample_variance <= 0 and total == 0 and squares == 0:
        return 0.0
    if sample_variance <= 0:
        raise ValueError("invalid retained return statistics")
    return (total / count) / sqrt(sample_variance)


def independent_pbo_from_return_statistics(
    matrix: list[list[list[float]]],
) -> dict[str, Any]:
    """Independent CSCV enumeration using per-bar Sharpe on retained statistics."""

    slice_count = len(matrix[0])
    trial_count = len(matrix)
    half = slice_count // 2
    logits: list[float] = []
    from math import log

    for test_columns in combinations(range(slice_count), half):
        test = frozenset(test_columns)
        train = [index for index in range(slice_count) if index not in test]
        train_scores = [_independent_sharpe([row[index] for index in train]) for row in matrix]
        selected = max(range(trial_count), key=lambda index: (train_scores[index], -index))
        test_scores = [_independent_sharpe([row[index] for index in test]) for row in matrix]
        rank = 1 + sum(score < test_scores[selected] for score in test_scores)
        omega = rank / (trial_count + 1)
        logits.append(log(omega) - log(1.0 - omega))
    return {
        "split_count": len(logits),
        "pbo": sum(value <= 0 for value in logits) / len(logits),
        "mean_logit": sum(logits) / len(logits),
    }


def independent_dsr(
    observed_sharpe: float,
    sharpes: list[float],
    sample_count: int,
    skewness: float,
    kurtosis: float,
    independent_trial_count: float | None = None,
) -> dict[str, float]:
    """DSR re-derived independently (two-pass variance, erf CDF, bisection inverse)."""
    raw_count = len(sharpes)
    count = independent_trial_count if independent_trial_count is not None else float(raw_count)
    mean = sum(sharpes) / raw_count
    variance = sum((value - mean) ** 2 for value in sharpes) / (raw_count - 1)
    euler_gamma = 0.5772156649015329
    natural_e = 2.718281828459045
    if count == 1 or variance == 0:
        threshold = 0.0
    else:
        threshold = sqrt(variance) * (
            (1 - euler_gamma) * _normal_inv_cdf(1 - 1 / count)
            + euler_gamma * _normal_inv_cdf(1 - 1 / (count * natural_e))
        )
    adjustment = 1 - skewness * observed_sharpe + ((kurtosis - 1) / 4) * observed_sharpe**2
    z_score = (observed_sharpe - threshold) * sqrt(sample_count - 1) / sqrt(adjustment)
    return {
        "expected_maximum_noise_sharpe": threshold,
        "z_score": z_score,
        "dsr": _normal_cdf(z_score),
    }


def _latest_lab_dir() -> Path:
    candidates = [
        path.parent
        for path in LAB_ROOT.glob("LAB-*/lab_run.json")
        if json.loads(path.read_text()).get("status") in {"COMPLETED", "COMPLETE"}
    ]
    if not candidates:
        raise RuntimeError("no completed research-lab batch found")
    return max(candidates, key=lambda item: (item / "lab_run.json").stat().st_mtime_ns)


def _verify_dataset() -> dict[str, str]:
    manifest = json.loads(FROZEN_MANIFEST.read_text())
    table = manifest.get("tables", {}).get(DATASET.stem)
    if not table:
        raise RuntimeError("dataset table missing from frozen manifest")
    digest = sha256(DATASET)
    if table.get("parquet_sha256") != digest:
        raise RuntimeError("dataset does not match frozen manifest")
    return {
        "dataset_id": str(manifest.get("dataset_id", "DS-CRYPTO-SPOT-BAKEOFF-V1")),
        "dataset_file": DATASET.name,
        "dataset_sha256": digest,
        "frozen_manifest_sha256": sha256(FROZEN_MANIFEST),
    }


def _verify_parity(lab_dir: Path, baseline: str, trials: list[dict[str, Any]]) -> str:
    parquet = lab_dir / f"{baseline}_sweep_all_trials.parquet"
    retained = {
        str(row[0]): (row[1], float(row[2]), int(row[3]))
        for row in duckdb.sql(
            f"select trial_key, status, total_return, trades from '{parquet}'"
        ).fetchall()
    }
    if set(retained) != {trial["trial_key"] for trial in trials}:
        raise RuntimeError(f"{baseline}: recomputed trial population differs from retained sweep")
    for trial in trials:
        status, total, trades = retained[trial["trial_key"]]
        if status != "COMPLETED" or trial["status"] != "COMPLETED":
            raise RuntimeError(f"{baseline}: non-COMPLETED trial {trial['trial_key']}")
        if abs(total - trial["total_return"]) > TOLERANCE or trades != trial["trades"]:
            raise RuntimeError(
                f"{baseline}: parity mismatch on {trial['trial_key']} "
                f"(retained {total}/{trades} vs recomputed "
                f"{trial['total_return']}/{trial['trades']})"
            )
    return sha256(parquet)


def evaluate_family(payload: dict[str, Any]) -> dict[str, Any]:
    """Pure evaluation of one family payload — testable without the engine."""
    trials = payload["trials"]
    matrix = [trial["slice_return_statistics"] for trial in trials]
    sharpes = [trial["sharpe_per_bar"] for trial in trials]
    selection = max(
        range(len(trials)),
        key=lambda i: (trials[i]["sharpe_per_bar"], -i),
    )
    candidate = trials[selection]
    primary_pbo = probability_of_backtest_overfitting_from_return_statistics(matrix)
    independent_pbo_result = independent_pbo_from_return_statistics(matrix)
    pbo_delta = abs(float(primary_pbo["pbo"]) - float(independent_pbo_result["pbo"]))
    if pbo_delta > TOLERANCE:
        raise RuntimeError(f"PBO independent recomputation disagrees by {pbo_delta}")
    retained_correlations = payload["return_correlations_upper_triangle"]
    expected_correlations = len(trials) * (len(trials) - 1) // 2
    if len(retained_correlations) != expected_correlations:
        raise RuntimeError("retained trial-return correlation count is incomplete")
    if int(payload["return_correlation_observation_count"]) < len(trials):
        raise RuntimeError("too few return observations for the retained correlation population")
    correlations_available = all(value is not None for value in retained_correlations)
    average_correlation = (
        sum(float(value) for value in retained_correlations) / len(retained_correlations)
        if correlations_available
        else None
    )
    effective_trials = (
        implied_independent_trials(len(trials), average_correlation)
        if average_correlation is not None
        else None
    )
    sharpe_variance = sharpe_variance_from_trials(sharpes)
    if effective_trials is None:
        primary_dsr: dict[str, float] = {}
        independent_dsr_result: dict[str, float] = {}
        dsr_delta = None
        numeric_verdict = (
            "FAIL" if float(primary_pbo["pbo"]) > PBO_PASS_MAXIMUM else "METHOD_BLOCKED"
        )
    else:
        dsr_arguments = {
            "observed_sharpe": candidate["sharpe_per_bar"],
            "sharpe_variance": sharpe_variance,
            "independent_trials": effective_trials,
            "sample_count": payload["sample_count"],
            "skewness": candidate["returns_skewness"],
            "kurtosis": candidate["returns_kurtosis"],
        }
        primary_dsr = deflated_sharpe_ratio(**dsr_arguments)
        independent_dsr_result = independent_dsr(
            candidate["sharpe_per_bar"],
            sharpes,
            payload["sample_count"],
            candidate["returns_skewness"],
            candidate["returns_kurtosis"],
            effective_trials,
        )
        dsr_delta = max(
            abs(primary_dsr[key] - independent_dsr_result[key])
            for key in ("expected_maximum_noise_sharpe", "z_score", "dsr")
        )
        if dsr_delta > 1e-6:  # bisection inverse-CDF is ~1e-9; z-scale amplifies to <1e-6
            raise RuntimeError(f"DSR independent recomputation disagrees by {dsr_delta}")
        numeric_verdict = (
            "PASS"
            if float(primary_dsr["dsr"]) >= DSR_PASS_MINIMUM
            and float(primary_pbo["pbo"]) <= PBO_PASS_MAXIMUM
            else "FAIL"
        )
    return {
        "trial_count": len(trials),
        "raw_trial_count": len(trials),
        "effective_independent_trials": effective_trials,
        "independent_trials_basis": (
            "DSR_2014_APPENDIX_3_AVERAGE_RETURN_CORRELATION"
            if effective_trials is not None
            else "UNAVAILABLE_UNDEFINED_TRIAL_RETURN_CORRELATIONS"
        ),
        "effective_independent_trials_scope": "RETAINED_FAMILY_GRID_ONLY",
        "average_trial_return_correlation": average_correlation,
        "correlation_observation_count": payload["return_correlation_observation_count"],
        "search_lineage_complete": False,
        "declared_selection_metric": "non_annualized_per_bar_sharpe",
        "pbo_slice_metric": "non_annualized_per_bar_sharpe",
        "dsr_metric": "sharpe_per_bar",
        "selection_metrics_aligned": True,
        "slice_count": payload["slice_count"],
        "slice_length_bars": payload["slice_length_bars"],
        "bars_excluded_tail": payload["bars_excluded_tail"],
        "sample_count": payload["sample_count"],
        "selection_procedure": (
            "max full-sample non-annualized per-bar Sharpe over retained family grid"
        ),
        "selected_trial_key": candidate["trial_key"],
        "selected_total_return": candidate["total_return"],
        "selected_sharpe_per_bar": candidate["sharpe_per_bar"],
        "selected_returns_skewness": candidate["returns_skewness"],
        "selected_returns_kurtosis": candidate["returns_kurtosis"],
        "sharpe_variance_across_trials": sharpe_variance,
        "pbo": {
            "primary": {
                "pbo": primary_pbo["pbo"],
                "split_count": primary_pbo["split_count"],
            },
            "independent": independent_pbo_result,
            "max_abs_delta": pbo_delta,
        },
        "dsr": {
            "status": "COMPUTED" if primary_dsr else "METHOD_BLOCKED",
            "primary": primary_dsr,
            "independent": independent_dsr_result,
            "max_abs_delta": dsr_delta,
        },
        "numeric_verdict": numeric_verdict,
        "verdict": numeric_verdict,
        "promotion_verdict": "METHOD_BLOCKED",
        "verdict_rule": (
            f"PASS requires DSR >= {DSR_PASS_MINIMUM} and PBO <= {PBO_PASS_MAXIMUM}; "
            "a PASS additionally requires validation-stats-specialist review before "
            "promotion use (RG-07)"
        ),
    }


def build_search_lineage(lab_dir: Path) -> dict[str, Any]:
    """Retain the known lab stage and state exactly which upstream stages are absent."""

    records = [
        json.loads(line)
        for line in (lab_dir / "trial_ledger.jsonl").read_text().splitlines()
        if line.strip()
    ]
    experiments = [row["record"] for row in records if row.get("kind") == "experiment"]
    runs = [row["record"] for row in records if row.get("kind") == "run"]
    if not experiments or not runs or any(row.get("status") != "COMPLETED" for row in runs):
        raise RuntimeError("research-lab lineage is incomplete")
    return {
        "status": "INCOMPLETE",
        "raw_trial_count_retained": len(runs),
        "effective_independent_trials": None,
        "retained_stages": [
            {
                "stage_id": "accelerator_family_parameter_grids",
                "experiment_ids": sorted(str(row["experiment_id"]) for row in experiments),
                "raw_trial_count": len(runs),
                "selection_procedure": sorted(
                    {str(row["selection_procedure"]) for row in experiments}
                ),
                "source": str((lab_dir / "trial_ledger.jsonl").relative_to(ROOT)),
            }
        ],
        "missing_stages": [
            (
                "the pre-lab hypothesis/family process that admitted B2/B3/B4 and "
                "excluded alternatives"
            ),
            (
                "the complete dataset, engine, scenario, and transformation search "
                "attempted before this lab batch"
            ),
        ],
    }


def build_method_contract(lineage: dict[str, Any], families: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if lineage.get("status") != "COMPLETE":
        blockers.append("hierarchical_search_lineage_incomplete")
    if lineage.get("effective_independent_trials") is None:
        blockers.append("hierarchy_effective_independent_trials_unavailable")
    if any(not result.get("selection_metrics_aligned") for result in families.values()):
        blockers.append("selection_metric_not_aligned")
    if any(result.get("effective_independent_trials") is None for result in families.values()):
        blockers.append("family_effective_independent_trials_unavailable")
    return {
        "status": "METHOD_BLOCKED" if blockers else "METHOD_READY_FOR_SPECIALIST_REVIEW",
        "governed_selection_metric": "non_annualized_per_bar_sharpe",
        "metric_applies_to": ["candidate_selection", "PBO_IS", "PBO_OOS", "DSR"],
        "blockers": blockers,
    }


def main() -> dict[str, Any]:
    provenance = _verify_dataset()
    lab_dir = _latest_lab_dir()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(ENGINE_PYTHON),
            str(EXTRACTOR),
            "--dataset",
            str(DATASET),
            "--out",
            str(OUT_DIR),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    families: dict[str, Any] = {}
    parquet_hashes: dict[str, str] = {}
    input_hashes: dict[str, str] = {}
    for baseline in BASELINES:
        inputs_path = OUT_DIR / f"g10_returns_{baseline}.json"
        payload = json.loads(inputs_path.read_text())
        parquet_hashes[baseline] = _verify_parity(lab_dir, baseline, payload["trials"])
        input_hashes[baseline] = sha256(inputs_path)
        families[baseline] = evaluate_family(payload)
    search_lineage = build_search_lineage(lab_dir)
    method_contract = build_method_contract(search_lineage, families)
    date_tag = datetime.now(tz=UTC).strftime("%Y_%m_%d")
    evidence = {
        "schema": "tios-g10-candidate-evidence-v2",
        "gate": "G10",
        "task": "T-009-04 candidate-specific integration (RG-07)",
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "status": "COMPLETE",
        "g10_gate_status": method_contract["status"],
        "validation_package_family": "b2",
        "method_contract": method_contract,
        "search_lineage": search_lineage,
        "method_sources": {
            "dsr": {
                "url": "https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf",
                "scope": "Equations 1-2 and Appendix 3 average-correlation implied trials",
            },
            "pbo": {
                "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
                "scope": "CSCV probability-of-backtest-overfitting selection procedure",
            },
            "retrieved_at_utc": "2026-07-13",
        },
        "provenance": {
            **provenance,
            "research_lab_batch": lab_dir.name,
            "retained_trial_parquet_sha256": parquet_hashes,
            "g10_returns_input_sha256": input_hashes,
            "engine_env_manifest_sha256": sha256(ENGINE_ENV_MANIFEST),
            "extractor": str(EXTRACTOR.relative_to(ROOT)),
            "extractor_sha256": sha256(EXTRACTOR),
            "methods_implementation": "src/tios/validation/multiple_testing.py",
            "method_fixtures": "artifacts/validation/G10_METHOD_FIXTURES_2026_07_11.json",
            "strategy_spec_sha256": {
                baseline: sha256(path) for baseline, path in SPEC_FILES.items() if path.is_file()
            },
        },
        "assumptions": [
            "slice matrix uses 16 equal contiguous time slices of per-bar mean returns; "
            "the tail remainder bars are excluded from slices and documented per family",
            "Sharpe is per-bar (not annualized) so DSR sample_count equals bar count",
            "the governed selection metric is non-annualized per-bar Sharpe for candidate "
            "selection, both PBO halves, and DSR; no winner is thereby promoted",
            "population is the vectorbt accelerator sweep; cross-engine reproduction "
            "remains a separate, still-blocked dimension",
            "family-scope implied independent trials use the DSR paper's Appendix-3 "
            "average-correlation interpolation over retained full bar-return correlations",
            "complete upstream hierarchical search lineage and its effective independent "
            "trial count are not present in the retained evidence",
        ],
        "failure_modes": [
            "parity mismatch vs retained Parquet aborts the run (no partial evidence)",
            "primary-vs-independent disagreement beyond tolerance aborts the run",
            "non-COMPLETED trials abort the run",
        ],
        "families": families,
        "effect": (
            "This retains corrected numeric diagnostics for the candidate populations. "
            "G10 remains METHOD_BLOCKED because the upstream search lineage and its "
            "effective independent-trial count are unresolved. It approves no "
            "strategy, selects no winner, and enables no execution path."
        ),
    }
    out = ROOT / "artifacts/validation" / f"G10_CANDIDATE_EVIDENCE_{date_tag}.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: families[k]["verdict"] for k in families} | {"artifact": str(out)}))
    return evidence


if __name__ == "__main__":
    main()
