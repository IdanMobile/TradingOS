import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_seed_candidate_g10_is_retained_without_execution_authority() -> None:
    path = ROOT / "artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json"
    data = json.loads(path.read_text())
    assert data["candidate_id"] == "STRAT-QC2-donchian-breakout"
    assert data["dataset"] == "ETHUSDT_1h"
    assert data["selected_trial_key"] == "window=40"
    assert data["execution_authority"] == "NONE"
    assert data["paper_orders"] == "DISABLED"
    assert data["live_orders"] == "DISABLED"
    assert data["trial_count"] == 4
    assert data["g10_gate_status"] in {"FAIL", "PASS_REQUIRES_REVIEW"}
    assert "Approves no strategy" in data["effect"]


def test_seed_candidate_g10_has_independent_recomputations() -> None:
    path = ROOT / "artifacts/validation/seed_candidates/SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json"
    data = json.loads(path.read_text())
    assert data["pbo"]["max_abs_delta"] <= 1e-9
    assert data["dsr"]["max_abs_delta"] <= 1e-6
    assert data["pbo"]["primary"]["split_count"] == data["pbo"]["independent"]["split_count"]
    assert "stats-specialist review" in data["verdict_rule"]
