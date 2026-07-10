import json
from pathlib import Path


def test_parameter_robustness_contains_all_retained_variants() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "robustness"
        / "summary.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE_ENGINE_RUNS"
    assert len(data["variants"]) == 5
    assert all(row["fee_audit"]["status"] == "PASS" for row in data["variants"])
