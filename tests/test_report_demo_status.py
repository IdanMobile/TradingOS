"""Deterministic checks for the demo lane operational status report."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.report_demo_status as status  # noqa: E402

NOW = datetime(2026, 7, 25, 12, 5, tzinfo=UTC)


def _write(path: Path, obj: object) -> Path:
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def _fill(side: str, usdt: float, eth: float, price: str, at: str) -> dict[str, object]:
    return {
        "ok": True,
        "order_status": "Filled",
        "side": side,
        "avg_price": price,
        "fee": "0.05",
        "recorded_at": at,
        "reconcile": {"USDT_delta": usdt, "ETH_delta": eth},
    }


def _orders(tmp_path: Path) -> Path:
    p = tmp_path / "orders.jsonl"
    rows = [
        _fill("Buy", -25.0, 0.0134, "1862.37", "2026-07-20T14:15:58+00:00"),
        _fill("Sell", 25.5379, -0.0134, "1906.30", "2026-07-23T13:01:01+00:00"),
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_flat_position_reports_flat_and_history(tmp_path: Path) -> None:
    hb = _write(
        tmp_path / "hb.json",
        {
            "at": "2026-07-25T12:01:00+00:00",
            "lane_base": "0",
            "entry_price": "1862.37",
            "mark_price": "1857.81",
            "disaster_stop_price": "1583.0145",
            "resting_stop": None,
            "kill_switch": False,
            "candidate": "ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1",
            "latest_closed_bar": "2026-07-25T12:00:00+00:00",
            "signals_in_window": 2,
            "fresh_signals": 0,
            "rule_levels": {
                "donchian_lower": "1847.8",
                "donchian_upper": "1909.92",
                "close": "1857.96",
                "volume_base": "557.9",
                "volume_threshold": "3557.7",
            },
        },
    )
    st = _write(tmp_path / "state.json", {"lane_base": "0", "resting_stop": None})
    report = status.build_status(hb, st, _orders(tmp_path), now=NOW)

    assert report["position"]["side"] == "FLAT"
    assert report["position"]["unrealised_pnl_usd"] is None
    assert report["execution_authority"] == "NONE" and report["real_money"] is False
    assert report["protection"]["disaster_stop_price_usd"] == "1583.0145"
    assert report["heartbeat_age_seconds"] == 240.0  # 12:05 - 12:01
    assert report["trade_history"]["closed_trades"] == 1 and report["trade_history"]["wins"] == 1
    md = status.render_markdown(report)
    assert "FLAT" in md and "no open position" in md and "authority NONE" in md


def test_long_position_reports_stop_and_unrealised(tmp_path: Path) -> None:
    hb = _write(
        tmp_path / "hb.json",
        {
            "at": "2026-07-25T12:01:00+00:00",
            "lane_base": "0.0134",
            "entry_price": "1862.37",
            "mark_price": "1900.00",
            "disaster_stop_price": "1583.01",
            "resting_stop": {"trigger_price": "1583.01", "state": "ACTIVE"},
            "kill_switch": False,
            "signals_in_window": 1, "fresh_signals": 0,
            "rule_levels": {"donchian_lower": "1847.8", "donchian_upper": "1909.92"},
        },
    )  # fmt: skip
    st = _write(
        tmp_path / "state.json",
        {"lane_base": "0.0134", "resting_stop": {"trigger_price": "1583.01", "state": "ACTIVE"}},
    )
    report = status.build_status(hb, st, tmp_path / "none.jsonl", now=NOW)

    assert report["position"]["side"] == "LONG"
    assert report["position"]["base_qty"] == 0.0134
    # unrealised = 0.0134 * (1900 - 1862.37) ~= 0.50
    assert report["position"]["unrealised_pnl_usd"] == round(0.0134 * (1900.0 - 1862.37), 2)
    assert report["protection"]["venue_resting_stop_trigger_usd"] == "1583.01"
    assert report["protection"]["venue_resting_stop_state"] == "ACTIVE"
    md = status.render_markdown(report)
    assert "LONG" in md and "trailing stop" in md.lower()
