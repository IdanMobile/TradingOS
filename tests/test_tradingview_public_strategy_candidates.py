"""TradingView public strategy candidates stay research-only and reproducible later."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
BATCH = (
    ROOT
    / "artifacts/source_intake/tradingview_public_strategies/selected_candidates_2026_07_11.json"
)


def _batch() -> dict[str, object]:
    payload = json.loads(BATCH.read_text())
    assert isinstance(payload, dict)
    return payload


def test_tradingview_public_strategy_batch_is_nonexecution_research() -> None:
    payload = _batch()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    assert payload["schema"] == "tios-tradingview-public-strategy-candidate-batch-v1"
    assert payload["source_ref"] == "SRC-TRADINGVIEW-PUBLIC-STRATEGIES"
    assert payload["intake_plan_ref"] == "INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES"
    assert payload["hypothesis_ref"] == "RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER"
    assert payload["candidate_count"] == len(candidates) == 8
    assert payload["execution_authority"] == "NONE"
    assert payload["paper_demo_live"] == "DISABLED"
    assert payload["approval_eligible"] is False
    assert payload["local_reproduction_status"] == "NOT_STARTED"
    assert "protected_or_invite_only_code_copying" in payload["prohibited_actions"]


def test_tradingview_public_strategy_candidates_have_next_reproduction_steps() -> None:
    payload = _batch()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    ids = [str(candidate["candidate_id"]) for candidate in candidates]
    assert len(ids) == len(set(ids))
    families = {str(candidate["family"]) for candidate in candidates}
    assert {"trend_following", "mean_reversion", "momentum_long_short"} <= families
    for candidate in candidates:
        assert str(candidate["canonical_url"]).startswith("https://www.tradingview.com/script/")
        assert candidate["access_status"] == "OPEN_SOURCE_PAGE_OBSERVED"
        assert candidate["tester_status"] == "STRATEGY_REPORT_AVAILABLE_NOT_CAPTURED"
        assert str(candidate["why_selected"]).strip()
        steps = candidate["next_steps"]
        assert isinstance(steps, list)
        assert any("source hash" in str(step) for step in steps)
        assert any("Strategy Tester" in str(step) or "tester" in str(step) for step in steps)
