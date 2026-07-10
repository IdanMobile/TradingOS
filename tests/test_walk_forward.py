import json
from pathlib import Path


def test_walk_forward_summary_retains_all_windows() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "walk_forward"
        / "summary.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE_ENGINE_RUNS"
    assert len(data["windows"]) == 18
    assert all(row["fee_audit"]["status"] == "PASS" for row in data["windows"])
