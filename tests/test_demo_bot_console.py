"""The Operations console must label retained demo activity as historical evidence."""

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
    assert got["activity_classification"] == "HISTORICAL_EVIDENCE"
    assert got["evidence_venue"] == "BYBIT_DEMO"
    assert got["current_network_state"] == "QUARANTINED"
    assert got["venue_connection"] == got["execution_authority"] == "NONE"


def test_build_demo_bot_empty_without_log(tmp_path: Path) -> None:
    got = build_demo_bot(tmp_path)
    assert got["total_orders"] == 0 and got["orders"] == []
    assert got["activity_classification"] == "NONE" and got["evidence_venue"] is None
    assert got["current_network_state"] == "QUARANTINED"
    assert got["venue_connection"] == got["execution_authority"] == "NONE"


def test_operations_projection_includes_demo_bot(tmp_path: Path) -> None:
    operations = build_operations(tmp_path)
    assert operations["execution_authority"] == operations["venue_connection"] == "NONE"
    assert operations["demo_bot"]["current_network_state"] == "QUARANTINED"


def test_dashboard_labels_demo_activity_as_historical_and_quarantined() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    assert "Historical demo evidence" in html
    assert "Network quarantined" in html
    assert "Live demo bot orders" not in html
    assert "run scripts/demo_strategy_bot.py" not in html
