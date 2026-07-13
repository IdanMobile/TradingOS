#!/usr/bin/env python3
"""Demo P&L — did the bots win or lose? (fake money).

The bots trade BTC/USDT and end flat, and the Bybit demo account starts with 50,000 USDT + 1 BTC.
So net realized P&L (fees included) = (USDT_now - 50000) + (BTC_now - 1) x price. This queries the
live demo wallet + price, prints WIN/LOSS/FLAT, and writes a snapshot the console reads.

Run: python scripts/demo_pnl.py

ponytail: reuses rt.wallet + a public spot ticker; pure arithmetic. Snapshot lets the offline
dashboard show P&L without live network access.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import scripts.demo_strategy_bot as sbot  # noqa: E402

STARTING_USDT = 50000.0  # Bybit demo initial balances (the coins the bots touch)
STARTING_BTC = 1.0
PNL_SNAPSHOT = pf.ROOT / "artifacts" / "demo_bot" / "pnl.json"


def spot_price(market: pf.Transport, symbol: str) -> float:
    url = f"{pf.DEMO_BASE}/v5/market/tickers?category=spot&symbol={symbol}"
    return float(json.loads(market(url, {}))["result"]["list"][0]["lastPrice"])


def compute_pnl(usdt: float, btc: float, price: float) -> float:
    """Net realized P&L in USDT, fees included, given flat-ending BTC/USDT bots."""
    return round((usdt - STARTING_USDT) + (btc - STARTING_BTC) * price, 4)


def build_pnl(
    get: pf.Transport,
    market: pf.Transport,
    api_key: str,
    secret: str,
    symbol: str = "BTCUSDT",
) -> dict:
    balances = rt.wallet(get, api_key, secret, rt._now())
    usdt, btc = float(balances.get("USDT", 0)), float(balances.get("BTC", 0))
    price = spot_price(market, symbol)
    pnl = compute_pnl(usdt, btc, price)
    return {
        "realized_pnl_usdt": pnl,
        "result": "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT",
        "usdt_balance": round(usdt, 4),
        "btc_balance": btc,
        "btc_price": price,
        "starting_usdt": STARTING_USDT,
        "starting_btc": STARTING_BTC,
        "computed_at": datetime.now(UTC).isoformat(),
        "note": "Demo/fake money. Bots trade BTC/USDT and end flat, so this is net realized P&L "
        "including fees — a losing number here is fees paid by a strategy with no genuine edge.",
    }


def main() -> int:
    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = build_pnl(pf._urllib_transport, sbot.public_get, api_key, secret)
    PNL_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    PNL_SNAPSHOT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"net P&L {report['realized_pnl_usdt']:+.4f} USDT ({report['result']}) — "
        f"USDT {report['usdt_balance']}, BTC {report['btc_balance']} @ {report['btc_price']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
