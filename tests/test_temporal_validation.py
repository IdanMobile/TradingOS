import json
from pathlib import Path


def test_temporal_validation_has_three_executed_windows() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "oos_report.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE_ENGINE_RUNS"
    assert set(data["windows"]) == {"development", "validation", "holdout"}
    assert data["holdout_touched_before_optimization"] is False
    assert all(float(row["profit_total_abs"]) < 0 for row in data["windows"].values())
