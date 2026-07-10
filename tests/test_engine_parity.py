import json
from pathlib import Path


def test_parity_report_retains_explained_divergence() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "bakeoff"
        / "parity"
        / "engine_parity.json"
    )
    data = json.loads(path.read_text())
    contexts = {
        (row["baseline"], row["scenario"], row["instrument"]): row
        for row in data["comparable_contexts"]
    }
    assert contexts[("B1", "F0_S0", "BTCUSDT")]["classification"] == (
        "EXPECTED_EXECUTION_TIMING_DIVERGENCE"
    )
    assert contexts[("B2", "F0_S0", "BTCUSDT")]["classification"] == (
        "EXPLAINED_ENGINE_EXECUTION_AND_DATA_GAP_DIVERGENCE"
    )
    assert data["status"] == "AVAILABLE_LANES_COMPLETE_WITH_BLOCKERS"
