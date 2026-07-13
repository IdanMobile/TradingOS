"""Candidate-specific G10 integration checks (T-009-04 / RG-07)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_g10_candidate import (  # noqa: E402
    build_method_contract,
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
        "return_correlation_observation_count": 200,
        "return_correlations_upper_triangle": [
            0.0 for _ in range(len(trials) * (len(trials) - 1) // 2)
        ],
    }


def _trial(key: str, slice_returns: list[float], sharpe: float, total: float) -> dict:
    return {
        "trial_key": key,
        "status": "COMPLETED",
        "total_return": total,
        "trades": 1,
        "sharpe_per_bar": sharpe,
        "slice_mean_returns": slice_returns,
        "slice_return_statistics": [
            [2, 2 * value, 2 * (value * value + 1)] for value in slice_returns
        ],
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
    assert result["selected_trial_key"] == "c"
    assert result["pbo"]["max_abs_delta"] <= 1e-9
    assert result["dsr"]["max_abs_delta"] <= 1e-6


def test_numeric_pass_remains_method_blocked_without_search_lineage() -> None:
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
    assert result["promotion_verdict"] == "METHOD_BLOCKED"
    assert result["effective_independent_trials"] == 3
    assert result["search_lineage_complete"] is False
    assert result["selection_metrics_aligned"] is True
    assert "specialist review" in result["verdict_rule"]


def test_method_contract_fails_closed_on_missing_hierarchy() -> None:
    contract = build_method_contract(
        {"status": "INCOMPLETE", "effective_independent_trials": None},
        {"b2": {"selection_metrics_aligned": True, "effective_independent_trials": 2.5}},
    )
    assert contract["status"] == "METHOD_BLOCKED"
    assert contract["blockers"] == [
        "hierarchical_search_lineage_incomplete",
        "hierarchy_effective_independent_trials_unavailable",
    ]


def test_retained_candidate_evidence_fails_closed() -> None:
    path = ROOT / "artifacts/validation/G10_CANDIDATE_EVIDENCE_2026_07_13.json"
    data = json.loads(path.read_text())
    assert data["schema"] == "tios-g10-candidate-evidence-v2"
    assert data["g10_gate_status"] == "METHOD_BLOCKED"
    for family in ("b2", "b3", "b4"):
        result = data["families"][family]
        assert result["verdict"] in {"FAIL", "METHOD_BLOCKED"}
        assert result["promotion_verdict"] == "METHOD_BLOCKED"
        if result["effective_independent_trials"] is None:
            assert result["dsr"]["status"] == "METHOD_BLOCKED"
        else:
            assert 1 <= result["effective_independent_trials"] <= result["raw_trial_count"]
            assert result["dsr"]["max_abs_delta"] <= 1e-6
        assert result["search_lineage_complete"] is False
        assert result["selection_metrics_aligned"] is True
        assert result["pbo"]["max_abs_delta"] <= 1e-9
        assert result["trial_count"] >= 16
    assert data["method_contract"]["status"] == "METHOD_BLOCKED"
    assert data["search_lineage"]["status"] == "INCOMPLETE"
    assert data["search_lineage"]["raw_trial_count_retained"] == 66
    provenance = data["provenance"]
    assert provenance["dataset_id"] == "DS-CRYPTO-SPOT-BAKEOFF-V1"
    for key in (
        "dataset_sha256",
        "research_lab_batch",
        "retained_trial_parquet_sha256",
        "strategy_spec_sha256",
    ):
        assert provenance[key]
    assert set(provenance["strategy_spec_sha256"]) == {"b2", "b3", "b4"}
    assert "approves no strategy" in data["effect"]


def test_extractor_inputs_retain_sharpe_statistics_and_correlations() -> None:
    for family in ("b2", "b3", "b4"):
        data = json.loads(
            (ROOT / f"artifacts/validation/g10_candidate/g10_returns_{family}.json").read_text()
        )
        assert data["schema"] == "tios-g10-returns-v2"
        assert len(data["return_correlations_upper_triangle"]) == (
            len(data["trials"]) * (len(data["trials"]) - 1) // 2
        )
        for trial in data["trials"]:
            assert len(trial["slice_return_statistics"]) == data["slice_count"]
            assert all(len(statistics) == 3 for statistics in trial["slice_return_statistics"])
