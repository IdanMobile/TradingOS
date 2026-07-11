"""Candidate-specific G10 integration checks (T-009-04 / RG-07)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_g10_candidate import (  # noqa: E402
    evaluate_family,
    independent_dsr,
    independent_pbo,
)

FIXTURES = json.loads(
    (ROOT / "artifacts/validation/G10_METHOD_FIXTURES_2026_07_11.json").read_text()
)


def test_independent_pbo_matches_known_answer_fixture() -> None:
    fixture = FIXTURES["fixtures"]["pbo_cscv"]
    result = independent_pbo(fixture["performance_by_trial_slice"])
    assert result["split_count"] == fixture["expected_split_count"]
    assert result["pbo"] == pytest.approx(fixture["expected_pbo"], abs=1e-12)


def test_independent_dsr_matches_known_answer_fixture() -> None:
    fixture = FIXTURES["fixtures"]["dsr"]
    strong = independent_dsr(
        fixture["strong_observed_sharpe"],
        fixture["trial_sharpes"],
        fixture["sample_count"],
        fixture["skewness"],
        fixture["kurtosis"],
    )
    assert strong["dsr"] == pytest.approx(fixture["strong_expected_dsr"], abs=1e-6)
    assert strong["z_score"] == pytest.approx(fixture["strong_expected_z_score"], abs=1e-6)
    weak = independent_dsr(
        fixture["weak_observed_sharpe"],
        fixture["trial_sharpes"],
        fixture["sample_count"],
        fixture["skewness"],
        fixture["kurtosis"],
    )
    assert weak["dsr"] == pytest.approx(fixture["weak_expected_dsr"], abs=1e-6)


def _payload(trials: list[dict], slices: int = 4) -> dict:
    return {
        "trials": trials,
        "slice_count": slices,
        "slice_length_bars": 10,
        "bars_excluded_tail": 0,
        "sample_count": 200,
    }


def _trial(key: str, slice_returns: list[float], sharpe: float, total: float) -> dict:
    return {
        "trial_key": key,
        "status": "COMPLETED",
        "total_return": total,
        "trades": 1,
        "sharpe_per_bar": sharpe,
        "slice_mean_returns": slice_returns,
        "returns_skewness": 0.0,
        "returns_kurtosis": 3.0,
    }


def test_evaluate_family_fails_an_overfit_population() -> None:
    result = evaluate_family(
        _payload(
            [
                _trial("a", [10.0, 10.0, -10.0, -10.0], 0.01, 0.5),
                _trial("b", [-10.0, -10.0, 10.0, 10.0], 0.01, 0.4),
                _trial("c", [0.1, 0.1, 0.1, 0.1], 0.02, -0.1),
            ]
        )
    )
    assert result["verdict"] == "FAIL"
    assert result["selected_trial_key"] == "a"
    assert result["pbo"]["max_abs_delta"] <= 1e-9
    assert result["dsr"]["max_abs_delta"] <= 1e-6


def test_evaluate_family_passes_only_a_dominant_stable_candidate() -> None:
    result = evaluate_family(
        _payload(
            [
                _trial("winner", [5.0, 5.0, 5.0, 5.0], 2.0, 3.0),
                _trial("loser1", [-1.0, -1.0, -1.0, -1.0], 0.1, -0.5),
                _trial("loser2", [-2.0, -2.0, -2.0, -2.0], 0.12, -0.6),
            ]
        )
    )
    assert result["verdict"] == "PASS"
    assert "specialist review" in result["verdict_rule"]


def test_retained_candidate_evidence_is_complete_and_failing() -> None:
    path = ROOT / "artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_11.json"
    data = json.loads(path.read_text())
    assert data["schema"] == "tios-g10-candidate-evidence-v1"
    assert data["g10_gate_status"] == "FAIL"
    for family in ("b2", "b3", "b4"):
        result = data["families"][family]
        assert result["verdict"] == "FAIL"
        assert result["pbo"]["max_abs_delta"] <= 1e-9
        assert result["dsr"]["max_abs_delta"] <= 1e-6
        assert result["trial_count"] >= 16
    provenance = data["provenance"]
    assert provenance["dataset_id"] == "DS-CRYPTO-SPOT-BAKEOFF-V1"
    for key in (
        "dataset_sha256",
        "research_lab_batch",
        "retained_trial_parquet_sha256",
        "strategy_spec_sha256",
    ):
        assert provenance[key]
    assert "approves no strategy" in data["effect"]
