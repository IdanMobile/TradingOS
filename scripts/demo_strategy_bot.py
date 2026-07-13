#!/usr/bin/env python3
"""Strategy-driven Bybit DEMO bot — a real signal placing real demo orders.

Pulls real market klines, runs a Donchian breakout signal (a copied public strategy) over the
last N closed bars, and drives the demo execution lane: BUY when the strategy enters while flat,
SELL to close when it exits. You watch the strategy trade — in this log and in the Bybit demo UI.

This replays recent REAL bars through the live demo so you see trades without waiting hours;
each demo order fills at the current market price (logged alongside the signal-bar price). It is
a MACHINERY + CANDIDATE test — the Donchian strategy is NOT validated (it fails DSR like every
public TA system); real execution_authority stays NONE, demo/fake money only, orders capped.

Safety: demo host only; GREEN preflight required; MAX_NOTIONAL cap per order; MAX_TRADES cap
per run. See docs/program/DEMO_LANE_PLAN.md.

Run: python scripts/demo_strategy_bot.py --symbol BTCUSDT --interval 1 --bars 120

ponytail: reuses ext.donchian_breakout (tested signal) + rt execution primitives; the only new
code is the public-kline fetch and the position-tracking walk. Public klines need no auth.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import scripts.run_external_strategy_search as ext  # noqa: E402

MAX_TRADES = 8  # cap real demo orders placed per run
DEFAULT_BARS = 120
ACTIVITY_LOG = pf.ROOT / "artifacts" / "demo_bot" / "activity.jsonl"


def _record(entry: dict) -> None:
    """Append one bot order to the persisted activity log the console reads."""
    ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ACTIVITY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def public_get(url: str, _headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, method="GET")  # noqa: S310 (https, public market data)
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        out: bytes = response.read()
        return out


def fetch_klines(
    transport: pf.Transport, base: str, symbol: str, interval: str, limit: int
) -> ext.Candles:
    """Public spot klines -> chronological Candles of Decimals (Bybit returns newest-first)."""
    url = f"{base}/v5/market/kline?category=spot&symbol={symbol}&interval={interval}&limit={limit}"
    rows = list(reversed(json.loads(transport(url, {}))["result"]["list"]))
    return {
        "open": [Decimal(r[1]) for r in rows],
        "high": [Decimal(r[2]) for r in rows],
        "low": [Decimal(r[3]) for r in rows],
        "close": [Decimal(r[4]) for r in rows],
        "volume": [Decimal(r[5]) for r in rows],
    }


def _buy(api_key: str, secret: str, symbol: str, quote_qty: float, get, post, sleep) -> dict:  # type: ignore[no-untyped-def]
    base_coin = symbol.removesuffix("USDT")
    before = rt.wallet(get, api_key, secret, rt._now())
    placed = rt.place_market_buy(
        post, api_key, secret, rt._now(), symbol=symbol, quote_qty=quote_qty
    )
    if placed.get("retCode") != 0:
        return {"ok": False, "error": str(placed.get("retMsg"))}
    status = rt._poll_filled(get, api_key, secret, str(placed["result"]["orderId"]), symbol, sleep)
    mid = rt.wallet(get, api_key, secret, rt._now())
    net = rt._round_down(rt._delta(before, mid, base_coin), rt.BASE_STEP_DECIMALS)
    return {"ok": net > 0, "qty": net, "fill_price": status.get("avgPrice")}


def _sell(api_key: str, secret: str, symbol: str, base_qty: float, get, post, sleep) -> dict:  # type: ignore[no-untyped-def]
    placed = rt.place_market_sell(
        post, api_key, secret, rt._now(), symbol=symbol, base_qty=base_qty
    )
    if placed.get("retCode") != 0:
        return {"ok": False, "error": str(placed.get("retMsg"))}
    status = rt._poll_filled(get, api_key, secret, str(placed["result"]["orderId"]), symbol, sleep)
    return {"ok": status.get("orderStatus") == "Filled", "fill_price": status.get("avgPrice")}


def run_bot(
    api_key: str,
    secret: str,
    *,
    symbol: str = "BTCUSDT",
    interval: str = "1",
    entry_w: int = 20,
    exit_w: int = 10,
    quote_qty: float = rt.DEFAULT_QUOTE_QTY,
    bars: int = DEFAULT_BARS,
    log: Callable[[str], None] = print,
    record: Callable[[dict], None] = lambda _e: None,
    get_transport: pf.Transport = pf._urllib_transport,
    market_transport: pf.Transport = public_get,
    post_transport: rt.PostTransport = rt._post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Preflight, fetch real bars, walk the Donchian signal, and trade transitions on the demo."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    candles = fetch_klines(market_transport, pf.DEMO_BASE, symbol, interval, bars)
    entries, exits = ext.donchian_breakout(entry_w, exit_w)(candles)
    close = candles["close"]
    signal_label = f"donchian({entry_w}/{exit_w})"

    def _remember(trade: dict) -> None:
        trades.append(trade)
        record({"recorded_at": datetime.now(UTC).isoformat(), "symbol": symbol,
                "signal": signal_label, **trade})  # fmt: skip

    log(
        f"preflight GREEN — {symbol} {interval}m Donchian({entry_w}/{exit_w}) over {len(close)} "
        f"real bars — enter on new {entry_w}-bar high, exit on {exit_w}-bar low"
    )
    holding = 0.0
    trades: list[dict] = []
    # Walk closed bars (skip warmup and the still-forming last bar); stop at the trade cap.
    for t in range(max(entry_w, exit_w), len(close) - 1):
        if len(trades) >= MAX_TRADES:
            break
        if holding <= 0 and entries[t]:
            result = _buy(api_key, secret, symbol, quote_qty, get_transport, post_transport, sleep)
            if result["ok"]:
                holding = result["qty"]
                log(f"  ENTRY @ {close[t]} — BUY {result['qty']} filled@{result['fill_price']}")
                _remember({"side": "BUY", "signal_price": str(close[t]), **result})
        elif holding > 0 and exits[t]:
            result = _sell(api_key, secret, symbol, holding, get_transport, post_transport, sleep)
            if result["ok"]:
                log(f"  EXIT  @ {close[t]} — SELL {holding} filled@{result['fill_price']}")
                _remember({"side": "SELL", "signal_price": str(close[t]), "qty": holding, **result})
                holding = 0.0
    if holding > 0:  # leave the demo account flat
        result = _sell(api_key, secret, symbol, holding, get_transport, post_transport, sleep)
        if result["ok"]:
            log(f"  FLATTEN SELL {holding} {symbol} filled@{result['fill_price']}")
            _remember({"side": "SELL", "reason": "flatten", "qty": holding, **result})
            holding = 0.0
    log(f"done — {len(trades)} demo order(s); final {'FLAT' if holding == 0 else holding}")
    return {
        "ok": True,
        "symbol": symbol,
        "interval": interval,
        "signal": f"donchian({entry_w}/{exit_w})",
        "bars": len(close),
        "trades": trades,
        "note": "Machinery + candidate test on demo/fake money. Donchian is NOT validated "
        "(fails DSR); real execution_authority stays NONE.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Strategy-driven Bybit demo bot.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1", help="kline interval minutes (1,5,15,60,...)")
    parser.add_argument("--entry-window", type=int, default=20)
    parser.add_argument("--exit-window", type=int, default=10)
    parser.add_argument("--bars", type=int, default=DEFAULT_BARS)
    parser.add_argument("--quote", type=float, default=rt.DEFAULT_QUOTE_QTY)
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = run_bot(
        api_key,
        secret,
        symbol=args.symbol,
        interval=args.interval,
        entry_w=args.entry_window,
        exit_w=args.exit_window,
        quote_qty=args.quote,
        bars=args.bars,
        record=_record,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
