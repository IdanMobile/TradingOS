#!/usr/bin/env python3
"""Deterministic operational status report for the fake-money demo lane.

Zero AI, no network: it reads the lane's own runtime artifacts (heartbeat.json,
lane_state.json, orders.jsonl) and renders a single "what is the lane doing right now"
snapshot — position, protective stop (the -15% hard stop and any venue-resting/trailing
stop), the strategy's rule-driven entry/exit triggers (volume-confirmed Donchian breakout),
recent signal activity, kill-switch state, heartbeat freshness — plus the realised
per-trade win/loss summary from `report_demo_trades`.

This surfaces the signals + TP/SL + trailing-stop-move visibility as a plain function, so
the routine "what happened / what is armed" question needs no AI. Read-only: no order,
credential, venue, or execution authority; it changes no lane state.

Usage:
    uv run python scripts/report_demo_status.py            # print + write default artifacts
    uv run python scripts/report_demo_status.py --no-write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import report_demo_trades as trades  # noqa: E402

LANE_DIR = ROOT / "artifacts" / "trading_domain" / "demo_lane"
DEFAULT_HEARTBEAT = LANE_DIR / "heartbeat.json"
DEFAULT_STATE = LANE_DIR / "lane_state.json"
DEFAULT_ORDERS = LANE_DIR / "orders.jsonl"
DEFAULT_JSON = ROOT / "artifacts" / "reports" / "DEMO_STATUS_REPORT.json"
DEFAULT_MD = ROOT / "artifacts" / "reports" / "DEMO_STATUS_REPORT.md"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _heartbeat_age_seconds(at: Any, now: datetime) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return round((now - parsed).total_seconds(), 1)


def _protective_stop(heartbeat: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """The armed protection: the -15% hard disaster stop plus any venue-resting/trailing stop.

    `resting_stop` carries the live venue stop and moves as the lane re-quantizes it, so its
    trigger is the current trailing-stop level; `disaster_stop_price` is the fixed -15% floor.
    """
    resting = state.get("resting_stop") or heartbeat.get("resting_stop")
    resting_trigger = None
    resting_state = None
    if isinstance(resting, dict):
        resting_trigger = resting.get("trigger_price") or resting.get("venue_trigger_price_usd")
        resting_state = resting.get("state")
    return {
        "disaster_stop_price_usd": heartbeat.get("disaster_stop_price"),
        "venue_resting_stop_trigger_usd": resting_trigger,
        "venue_resting_stop_state": resting_state,
    }


def build_status(
    heartbeat_path: Path = DEFAULT_HEARTBEAT,
    state_path: Path = DEFAULT_STATE,
    orders_path: Path = DEFAULT_ORDERS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure: the full operational status as data. IO lives in the CLI below."""
    now = now or datetime.now(UTC)
    heartbeat = _load(heartbeat_path)
    state = _load(state_path)
    lane_base = _num(state.get("lane_base", heartbeat.get("lane_base", "0")))
    mark = _num(heartbeat.get("mark_price"))
    entry = _num(heartbeat.get("entry_price"))
    is_long = lane_base > 0

    rule = heartbeat.get("rule_levels") or {}
    position: dict[str, Any] = {
        "side": "LONG" if is_long else "FLAT",
        "base_qty": lane_base if is_long else 0.0,
        "entry_price_usd": entry if is_long else None,
        "mark_price_usd": mark or None,
        "unrealised_pnl_usd": round(lane_base * mark - lane_base * entry, 2)
        if (is_long and mark > 0 and entry > 0)
        else None,
    }

    trade_report = trades.build_report(orders_path)
    return {
        "schema": "tios.demo_status_report.v1",
        "generated_at": now.isoformat(),
        "environment": "VENUE_DEMO",
        "real_money": False,
        "execution_authority": "NONE",
        "candidate": heartbeat.get("candidate"),
        "kill_switch": bool(heartbeat.get("kill_switch")),
        "heartbeat_at": heartbeat.get("at"),
        "heartbeat_age_seconds": _heartbeat_age_seconds(heartbeat.get("at"), now),
        "latest_closed_bar": heartbeat.get("latest_closed_bar"),
        "position": position,
        "protection": _protective_stop(heartbeat, state),
        "strategy_triggers": {
            "entry": "close > upper Donchian AND volume > threshold (volume-confirmed breakout)",
            "exit": "close < lower Donchian (40-bar) — rule-driven exit",
            "hard_stop": "-15% disaster stop from entry",
            "donchian_lower_usd": rule.get("donchian_lower"),
            "donchian_upper_usd": rule.get("donchian_upper"),
            "close_usd": rule.get("close"),
            "volume_base": rule.get("volume_base"),
            "volume_threshold": rule.get("volume_threshold"),
        },
        "signals": {
            "in_window": heartbeat.get("signals_in_window"),
            "fresh": heartbeat.get("fresh_signals"),
        },
        "trade_history": trade_report["summary"],
    }


def render_markdown(status: dict[str, Any]) -> str:
    p = status["position"]
    prot = status["protection"]
    trig = status["strategy_triggers"]
    th = status["trade_history"]
    sig = status["signals"]
    fresh_age = status["heartbeat_age_seconds"]
    lines = [
        "# Demo lane — operational status",
        "",
        f"Generated {status['generated_at']} · fake-money VENUE_DEMO · authority NONE (read-only).",
        f"Heartbeat {status['heartbeat_at']} (age {fresh_age}s) "
        f"· latest bar {status['latest_closed_bar']} "
        f"· kill switch {'ON' if status['kill_switch'] else 'off'}.",
        "",
        "## Position",
        f"- **{p['side']}**"
        + (
            f" {p['base_qty']} ETH @ entry ${p['entry_price_usd']}, mark ${p['mark_price_usd']}, "
            f"unrealised ${p['unrealised_pnl_usd']}"
            if p["side"] == "LONG"
            else " — no open position (flat)."
        ),
        "",
        "## Protection (TP/SL)",
        f"- Hard disaster stop: ${prot['disaster_stop_price_usd']} (-15% from entry).",
        f"- Venue-resting/trailing stop: trigger ${prot['venue_resting_stop_trigger_usd']} "
        f"({prot['venue_resting_stop_state'] or 'none armed while flat'}).",
        "",
        "## Strategy triggers (deterministic, no AI)",
        f"- Entry: {trig['entry']} — upper ${trig['donchian_upper_usd']}, "
        f"volume {trig['volume_base']} vs threshold {trig['volume_threshold']}.",
        f"- Exit: {trig['exit']} "
        f"— lower ${trig['donchian_lower_usd']}, close ${trig['close_usd']}.",
        f"- Hard stop: {trig['hard_stop']}.",
        f"- Signals: {sig['in_window']} in window, {sig['fresh']} fresh.",
        "",
        "## Realised trade history",
        f"- {th['closed_trades']} closed · {th['wins']}W / {th['losses']}L "
        f"· win rate {th['win_rate_pct']}% · realised P&L ${th['realised_pnl_usd']} "
        f"· fees ${th['total_fees_usd']} · best ${th['best_trade_usd']} "
        f"/ worst ${th['worst_trade_usd']} · {th['open_trades']} open.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic operational status for the demo lane."
    )
    parser.add_argument("--heartbeat", type=Path, default=DEFAULT_HEARTBEAT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--orders", type=Path, default=DEFAULT_ORDERS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--no-write", action="store_true", help="print only; write no artifacts")
    args = parser.parse_args(argv)

    status = build_status(args.heartbeat, args.state, args.orders)
    print(render_markdown(status))
    if not args.no_write:
        for path, text in (
            (args.json, json.dumps(status, indent=2)),
            (args.md, render_markdown(status)),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        print(f"wrote {args.json} and {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
