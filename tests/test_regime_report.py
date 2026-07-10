import json
from pathlib import Path


def test_regime_report_is_ex_post_and_complete() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "validation"
        / "B2_F0_S0"
        / "regime_report.json"
    )
    data = json.loads(path.read_text())
    assert data["status"] == "COMPLETE_EX_POST_SEGMENTATION"
    assert data["regimes"]
    assert "not predictive claims" in data["interpretation"]
