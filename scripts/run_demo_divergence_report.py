#!/usr/bin/env python3
"""T-015-03 (measurement mode): demo-lane fills vs the frozen backtest's fill expectation.

The frozen reproduction fills at the *next bar open* after a signal bar closes. The live
lane detects the signal on its hourly cycle and market-buys minutes later. This report
measures that gap per fill — price divergence, timing lag, fee drag — because it is
exactly the number the backtest cannot know about itself, and it accumulates one row per
fill for the 30-day D-104 window.

Scope notes, stated rather than hidden:
- Lane fills happen on Bybit demo; the frozen backtest was built on Binance data. Feed
  divergence is therefore part of the measured number, not removed from it.
- Demo-venue liquidity is not production liquidity. Rows are execution-measurement
  evidence only (D-104) and cannot validate or promote a strategy.

Public kline GET only; no credential is read or needed.

    python scripts/run_demo_divergence_report.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANE_DIR = ROOT / "artifacts" / "trading_domain" / "demo_lane"
ORDERS = LANE_DIR / "orders.jsonl"
REPORT = LANE_DIR / "DIVERGENCE_REPORT.json"
KLINES = "https://api-demo.bybit.com/v5/market/kline"


def _public_get(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - fixed https host
        return json.loads(response.read())


def bar_open_at(hour_start: datetime, fetch: Any = _public_get) -> float | None:
    """Open price of the 1h ETHUSDT bar starting exactly at `hour_start` (public data)."""
    start_ms = int(hour_start.timestamp() * 1000)
    url = f"{KLINES}?category=spot&symbol=ETHUSDT&interval=60&start={start_ms}&limit=1"
    rows = fetch(url).get("result", {}).get("list", [])
    # Bybit kline row: [startTime, open, high, low, close, volume, turnover]
    return float(rows[0][1]) if rows and int(rows[0][0]) == start_ms else None


def fill_rows(orders: list[dict[str, Any]], fetch: Any = _public_get) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in orders:
        if order.get("ok") is not True:
            continue
        recorded = datetime.fromisoformat(str(order["recorded_at"]))
        # The signal bar closed at the top of this hour; the backtest fills at the open
        # of the bar that starts there.
        expected_bar_start = recorded.replace(minute=0, second=0, microsecond=0)
        expected = bar_open_at(expected_bar_start, fetch)
        actual = float(order["avg_price"])
        side = str(order.get("side"))

        divergence_bps = None
        if expected:
            raw = (actual - expected) / expected * 10_000
            # Signed so positive is always adverse: paid more on a buy, got less on a sell.
            divergence_bps = round(raw if side == "Buy" else -raw, 2)

        qty = float(order.get("cum_exec_qty") or 0)
        fee = float(order.get("fee") or 0)
        fee_bps = round(fee * actual / (qty * actual) * 10_000, 2) if qty else None

        rows.append(
            {
                "signal_ref": order.get("signal_ref"),
                "side": side,
                "recorded_at": order["recorded_at"],
                "expected_fill_open_usd": expected,
                "actual_fill_usd": actual,
                "divergence_bps_adverse_positive": divergence_bps,
                "lag_seconds_after_bar_close": int((recorded - expected_bar_start).total_seconds()),
                "fee_bps": fee_bps,
            }
        )
    return rows


def build_report(orders: list[dict[str, Any]], fetch: Any = _public_get) -> dict[str, Any]:
    rows = fill_rows(orders, fetch)
    measured = [
        r["divergence_bps_adverse_positive"]
        for r in rows
        if r["divergence_bps_adverse_positive"] is not None
    ]
    return {
        "schema_version": 1,
        "task": "T-015-03 execution-measurement mode (D-104 step 3)",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "window_days_target": 30,
        "fills_measured": len(rows),
        "mean_divergence_bps": round(sum(measured) / len(measured), 2) if measured else None,
        "worst_divergence_bps": max(measured) if measured else None,
        "rows": rows,
        "scope_notes": [
            "Lane fills on Bybit demo; frozen backtest built on Binance data - "
            "feed divergence is part of the number.",
            "Demo liquidity is not production liquidity.",
            "Execution-measurement evidence only (D-104); cannot validate or promote a strategy.",
        ],
        "execution_authority": "NONE",
        "promotion_eligible": False,
    }


def main() -> int:
    orders = (
        [
            json.loads(line)
            for line in ORDERS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if ORDERS.is_file()
        else []
    )
    report = build_report(orders)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("fills_measured", "mean_divergence_bps", "worst_divergence_bps")
            }
        )
    )
    for row in report["rows"]:
        divergence = row["divergence_bps_adverse_positive"]
        print(
            f"  {row['side']:4} {row['recorded_at']}  expected {row['expected_fill_open_usd']}"
            f"  actual {row['actual_fill_usd']}  divergence {divergence} bps"
            f"  lag {row['lag_seconds_after_bar_close']}s  fee {row['fee_bps']} bps"
        )
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
