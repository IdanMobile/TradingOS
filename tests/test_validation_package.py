import json
from pathlib import Path


def test_validation_package_is_explicitly_not_approvable() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "validation_summary.json"
    )
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["status"] == "INCOMPLETE_NOT_APPROVABLE"
    assert data["gates"]["G1"]["status"] == "PASS"
    assert data["gates"]["G5"]["status"] == "PASS"
    assert data["risk_preconditions"]["status"] == "PASS"
    assert data["risk_preconditions"]["no_live_capability"] is True
    assert data["risk_preconditions"]["promotion_eligible"] is False


def test_multiple_testing_method_evidence_is_retained_but_not_activated() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "multiple_testing_method_candidate.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "METHOD_EVIDENCE_RETAINED"
    assert data["g10_gate_status"] == "NOT_RUN"
    assert data["production_gate_activated"] is False
    evidence = data["retained_method_evidence"]
    assert evidence["status"] == "PASS"
    assert evidence["trial_count"] == evidence["expected_trial_count"] == 66
    assert evidence["all_trials_registered"] is True
    assert evidence["all_sweep_tables_retained"] is True
    assert evidence["winner_selected"] is False
    assert {method["source_id"] for method in data["methods"]} == {
        "SRC-PBO-2016",
        "SRC-DSR-2014",
    }


def test_validation_status_matches_retained_s2_evidence() -> None:
    path = (
        Path(__file__).resolve().parents[1] / "artifacts" / "validation" / "validation_status.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "INCOMPLETE_NOT_APPROVABLE"
    assert data["production_complete"] is False
    assert data["promotion_eligible"] is False
    assert "G10_RETENTION" in data["implemented_gates"]
    assert "G10" in data["not_implemented"]
    assert "G7" in data["implemented_gates"]
    assert (
        "LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa"
        in data["latest_research_lab_batch"]
    )
