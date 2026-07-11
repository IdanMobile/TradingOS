"""Cross-engine reproduction evidence checks (research-lab dimension)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retained_reproduction_evidence_is_complete_and_bounded() -> None:
    data = json.loads(
        (ROOT / "artifacts/validation/CROSS_ENGINE_REPRODUCTION_2026_07_11.json").read_text()
    )
    assert data["schema"] == "tios-cross-engine-reproduction-v2"
    assert data["verdict"] in {"PASS_WITH_SCOPE_NOTE", "PARTIAL", "FAIL"}
    assert data["vectorbt"]["exact_or_tie_explained"] is True
    assert data["vectorbt"]["unexplained_differing_bars"] == 0
    freqtrade = data["freqtrade_single_pair"]
    assert freqtrade["all_exits_signal_driven"] is True
    assert freqtrade["fill_match_ratio"] >= 0.995
    assert float(freqtrade["profit_total_abs"]) < 0
    assert data["economic_direction_agreement"] is True
    assert any("NOT claimed" in note for note in data["scope_notes"])
    for key in ("dataset_sha256", "spec_sha256", "single_pair_backtest_zip_sha256"):
        assert data["provenance"][key]
    assert "approves no strategy" in data["effect"]
    for reference in (
        "artifacts/validation/b2_repro_vectorbt.json",
        "artifacts/validation/repro/b2_btc_entries.json",
        data["provenance"]["retained_two_pair_run"],
    ):
        assert (ROOT / reference).exists(), reference


def test_latest_lab_batch_binds_reproduction_dimension() -> None:
    labs = ROOT / "artifacts/research_lab/v0"
    latest = max(labs.glob("LAB-*/lab_run.json"), key=lambda p: p.stat().st_mtime_ns)
    lab = json.loads(latest.read_text())
    assert lab["score_states"]["cross_engine_reproduction"] in {
        "PASS_WITH_SCOPE_NOTE",
        "PARTIAL",
        "FAIL",
    }
    assert "BLOCKED" not in set(lab["score_states"].values())
    assert lab["winner_selected"] is False
    assert lab["execution_authority"] == "NONE"
