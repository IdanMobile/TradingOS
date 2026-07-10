import json
from pathlib import Path


def test_benchmark_comparison_preserves_negative_evidence() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "baseline_comparison.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE"
    assert data["candidate_beats_cash"] is False
    assert data["candidate_beats_buy_and_hold"] is False
