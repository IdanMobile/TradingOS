"""TradingView public-strategy replay artifacts remain offline evidence only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts/run_tradingview_public_strategy_replay.py"
ARTIFACT_ROOT = ROOT / "artifacts/external_replay/tradingview_public_strategies"


def _latest_replay() -> dict[str, object]:
    candidates = sorted(
        ARTIFACT_ROOT.glob("TVPINE-*/replay_run.json"),
        key=lambda path: path.stat().st_mtime_ns,
    )
    assert candidates
    payload = json.loads(candidates[-1].read_text())
    assert isinstance(payload, dict)
    return payload


def test_tradingview_replay_runner_is_nonexecution() -> None:
    spec = importlib.util.spec_from_file_location("tv_replay", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["tv_replay"] = module
    spec.loader.exec_module(module)

    result = module.run_replay()
    assert result["mode"] == "OFFLINE_RESEARCH_ONLY"
    assert result["execution_authority"] == "NONE"
    assert result["venue_connection"] == "NONE"
    assert result["paper_orders"] == "DISABLED"
    assert result["live_orders"] == "DISABLED"
    assert result["counts"] == {"candidates": 2, "datasets": 6, "events": 57046, "trials": 12}


def test_tradingview_replay_artifact_is_retained_not_validated() -> None:
    replay = _latest_replay()
    assert replay["schema"] == "tios-tradingview-public-strategy-replay-run-v1"
    assert replay["status"] == "COMPLETED"
    assert replay["execution_authority"] == "NONE"
    assert replay["paper_orders"] == "DISABLED"
    assert replay["live_orders"] == "DISABLED"
    assert replay["counts"]["trials"] == 12

    scorecard = json.loads((ROOT / str(replay["scorecard_path"])).read_text())
    assert scorecard["status"] == "EVIDENCE_RETAINED_NOT_VALIDATED"
    assert scorecard["validation_state"] == "UNVALIDATED"
    assert scorecard["approval_status"] == "NOT_ELIGIBLE"
    assert scorecard["promotion_eligible"] is False
    assert scorecard["execution_authority"] == "NONE"
    assert scorecard["winner_selected"] is False
    assert "protected_or_invite_only_code_copying" in scorecard["prohibited"]
    assert "order_routing" in scorecard["prohibited"]
    assert scorecard["best_total_return"] == "-0.3148736790074447392711432558"

    candidate_ids = {config["candidate_id"] for config in scorecard["candidate_configs"]}
    assert candidate_ids == {
        "TVPINE-RAGINGPORRA-RSI-MEAN-REVERSION",
        "TVPINE-SKYREXIO-BB-ENHANCED",
    }
    assert all((ROOT / trial["events_path"]).is_file() for trial in scorecard["trials"])
