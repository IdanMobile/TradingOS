import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_seed_validation_probe_retains_top_contexts_without_approval() -> None:
    path = ROOT / "artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json"
    data = json.loads(path.read_text())
    assert data["status"] == "EVIDENCE_RETAINED_NOT_VALIDATED"
    assert data["execution_authority"] == "NONE"
    assert data["paper_orders"] == "DISABLED"
    assert data["live_orders"] == "DISABLED"
    contexts = data["contexts"]
    assert [row["context"]["candidate_id"] for row in contexts] == [
        "STRAT-QC2-donchian-breakout",
        "STRAT-QC2-donchian-breakout",
        "STRAT-FT1-sample-strategy",
    ]
    assert contexts[0]["context"]["dataset"] == "ETHUSDT_1h"
    assert contexts[0]["context"]["trial_key"] == "window=40"
    assert Decimal(contexts[0]["full_period"]["total_return"]) > Decimal("1")
    assert contexts[0]["approval_status"] == "NOT_ELIGIBLE"
    assert any("not a promotion-grade" in blocker for blocker in contexts[0]["blockers"])


def test_seed_validation_probe_has_temporal_cost_and_neighborhood_evidence() -> None:
    path = ROOT / "artifacts/validation/seed_candidates/SEED_VALIDATION_PROBE_2026_07_11.json"
    data = json.loads(path.read_text())
    for row in data["contexts"]:
        assert set(row["temporal_splits"]) == {
            "train_first_third",
            "validation_middle_third",
            "holdout_final_third",
        }
        assert set(row["cost_stress"]) == {"0", "0.001", "0.002", "0.003"}
        assert row["parameter_neighborhood_top"]
        assert "total_return" in row["buy_hold_benchmark"]
