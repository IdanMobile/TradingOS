"""The Operations console must project the demo bot's persisted order activity."""

from __future__ import annotations

import json
from pathlib import Path

from tios.services.dashboard_api.operations import build_demo_bot, build_operations


def _order(side: str, at: str) -> str:
    return json.dumps(
        {
            "recorded_at": at,
            "symbol": "BTCUSDT",
            "signal": "donchian(10/5)",
            "side": side,
            "signal_price": "63839.1",
            "fill_price": "63804.7",
            "qty": 0.000391,
        }
    )


def test_build_demo_bot_reads_activity_newest_first(tmp_path: Path) -> None:
    log = tmp_path / "artifacts" / "demo_bot" / "activity.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(
        _order("BUY", "2026-07-13T00:00:00+00:00")
        + "\nnot-json\n"  # malformed lines are skipped, not fatal
        + _order("SELL", "2026-07-13T00:01:00+00:00")
        + "\n"
    )
    got = build_demo_bot(tmp_path)
    assert got["total_orders"] == 2 and got["buys"] == 1 and got["sells"] == 1
    assert got["last_activity_utc"] == "2026-07-13T00:01:00+00:00"
    assert got["orders"][0]["side"] == "SELL"  # newest first
    assert got["execution_authority"] == "NONE" and got["venue"] == "BYBIT_DEMO"


def test_build_demo_bot_empty_without_log(tmp_path: Path) -> None:
    got = build_demo_bot(tmp_path)
    assert got["total_orders"] == 0 and got["orders"] == []


def test_operations_projection_includes_demo_bot(tmp_path: Path) -> None:
    assert "demo_bot" in build_operations(tmp_path)
