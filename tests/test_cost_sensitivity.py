import json
from pathlib import Path


def test_cost_sensitivity_contains_complete_grid() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "cost_sensitivity.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE_GRID_POST_HOC"
    assert [row["scenario"] for row in data["scenarios"]] == [
        "F0/S0",
        "F1/S1",
        "F1/S2",
        "F1/S3",
        "F2/S2",
        "F2/S3",
    ]
    assert data["scenarios"][0]["diagnostic_only"] is True
