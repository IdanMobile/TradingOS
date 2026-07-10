"""Build the mandatory six-cell cost sensitivity artifact from canonical trades."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet

ROOT = Path(__file__).resolve().parents[1]
TRADES = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "trades.parquet"
OUT = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "cost_sensitivity.json"
GRID = (
    ("F0/S0", "0", "0"),
    ("F1/S1", "0.001", "1"),
    ("F1/S2", "0.001", "5"),
    ("F1/S3", "0.001", "10"),
    ("F2/S2", "0.0015", "5"),
    ("F2/S3", "0.0015", "10"),
)


def main() -> None:
    rows = pyarrow.parquet.read_table(TRADES).to_pylist()
    by_trade: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_trade[int(row["trade_id"])].append(row)
    results = []
    for scenario, fee_text, bps_text in GRID:
        fee = Decimal(fee_text)
        bps = Decimal(bps_text) / Decimal("10000")
        net = Decimal(0)
        gross = Decimal(0)
        roundtrips = 0
        for fills in by_trade.values():
            buys = [row for row in fills if row["side"] == "buy"]
            sells = [row for row in fills if row["side"] == "sell"]
            if not buys or not sells:
                continue
            buy, sell = buys[0], sells[-1]
            qty = Decimal(str(buy["qty"]))
            buy_price = Decimal(str(buy["price"])) * (Decimal(1) + bps)
            sell_price = Decimal(str(sell["price"])) * (Decimal(1) - bps)
            gross_trade = (sell_price - buy_price) * qty
            fees = (buy_price + sell_price) * qty * fee
            gross += gross_trade
            net += gross_trade - fees
            roundtrips += 1
        results.append(
            {
                "scenario": scenario,
                "fee_rate_per_side": fee_text,
                "slippage_bps_per_side": bps_text,
                "diagnostic_only": scenario == "F0/S0",
                "roundtrips": roundtrips,
                "gross_pnl_quote": str(gross),
                "net_pnl_quote": str(net),
                "profitable": net > 0,
                "source": "B2 F0/S0 canonical trades; adverse slippage applied post-hoc",
            }
        )
    OUT.write_text(
        json.dumps(
            {
                "status": "COMPLETE_GRID_POST_HOC",
                "strategy": "B2MaCrossover",
                "source_trades": str(TRADES.relative_to(ROOT)),
                "scenarios": results,
                "interpretation": (
                    "Diagnostic F0/S0 is never approval evidence; all economic cells are retained."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
