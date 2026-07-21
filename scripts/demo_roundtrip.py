#!/usr/bin/env python3
"""Bybit DEMO execution — prove order -> fill -> reconcile, and run an observable session.

Reuses the preflight's signing + demo-host lock, adds signed POSTs to place small spot market
orders on the Bybit demo account, polls to Filled, and reconciles wallet balances.

  * `run_roundtrip` — one market BUY, reconciled (leaves a tiny demo position).
  * `open_and_close_cycle` / `session` — a DUMMY signal that opens then closes a position each
    cycle, so it stays flat; run it to watch the lane work (also visible in the Bybit demo UI).

Safety rails: demo host only (api-demo.bybit.com); a GREEN preflight is required before any
order; every order is capped at MAX_NOTIONAL USDT. MACHINERY test — no strategy is validated;
real execution_authority stays NONE. See docs/program/DEMO_LANE_PLAN.md.

Run: python scripts/demo_roundtrip.py --cycles 3     # open+close 3 times, end flat

ponytail: stdlib only; transports are injectable so the flow is unit-tested offline with no
network. BTCUSDT base step is hardcoded (1e-6) — add an instrument-info lookup for more symbols.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402

MAX_NOTIONAL = 50.0  # hard cap (USDT) on any single demo order
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_QUOTE_QTY = 25.0  # spend this many (fake) USDT on the market buy
BASE_STEP_DECIMALS = 6  # BTCUSDT base precision (1e-6); lookup instrument-info for other symbols

PostTransport = Callable[[str, dict[str, str], bytes], bytes]


def sign_post(secret: str, timestamp: str, api_key: str, body: str) -> str:
    """Bybit V5 POST signature: HMAC-SHA256 over timestamp + apiKey + recvWindow + rawBody."""
    payload = f"{timestamp}{api_key}{pf.RECV_WINDOW}{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _order_create(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    order: dict[str, str],
) -> dict[str, Any]:
    pf.require_demo_base(base)
    body = json.dumps(order)
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": pf.RECV_WINDOW,
        "X-BAPI-SIGN": sign_post(secret, timestamp, api_key, body),
        "Content-Type": "application/json",
    }
    decoded = json.loads(post_transport(f"{base}/v5/order/create", headers, body.encode()))
    return decoded if isinstance(decoded, dict) else {}


def place_stop(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    *,
    symbol: str,
    trigger_price: str,
    base_qty: str,
) -> dict[str, Any]:
    """Rest a spot Sell stop (Bybit V5 conditional order) via the quarantined create transport.

    orderFilter=StopOrder, triggerDirection=2 (fire when the last price falls to/through
    triggerPrice), Market exit. The order-create endpoint literal stays confined to this module.
    """
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": base_qty,
        "marketUnit": "baseCoin",
        "orderFilter": "StopOrder",
        "triggerPrice": trigger_price,
        "triggerDirection": "2",
    }
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def cancel_order(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    *,
    order_id: str,
    symbol: str,
    order_filter: str = "StopOrder",
) -> dict[str, Any]:
    """Cancel an order by id (Bybit V5 /v5/order/cancel). Demo-host-locked; endpoint kept here."""
    pf.require_demo_base(base)
    body = json.dumps(
        {"category": "spot", "symbol": symbol, "orderId": order_id, "orderFilter": order_filter}
    )
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": pf.RECV_WINDOW,
        "X-BAPI-SIGN": sign_post(secret, timestamp, api_key, body),
        "Content-Type": "application/json",
    }
    decoded = json.loads(post_transport(f"{base}/v5/order/cancel", headers, body.encode()))
    return decoded if isinstance(decoded, dict) else {}


def place_market_buy(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
) -> dict[str, Any]:
    """Spot market BUY sized in quote (USDT). Demo-host-locked and notional-capped."""
    if quote_qty > MAX_NOTIONAL:
        raise ValueError(f"order notional {quote_qty} exceeds the {MAX_NOTIONAL} USDT cap")
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Buy",
        "orderType": "Market",
        "qty": str(quote_qty),
        "marketUnit": "quoteCoin",  # qty is the USDT amount to spend
    }
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def place_market_sell(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
    base_qty: float,
) -> dict[str, Any]:
    """Spot market SELL sized in base (e.g. BTC) — closes a position back to cash."""
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": str(base_qty),
        "marketUnit": "baseCoin",
    }
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def order_status(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    timestamp: str,
    order_id: str,
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
) -> dict[str, Any]:
    """Fetch one order's live status (signed GET /v5/order/realtime)."""
    resp = pf._signed_get(
        transport,
        base,
        "/v5/order/realtime",
        {"category": "spot", "symbol": symbol, "orderId": order_id},
        api_key,
        secret,
        timestamp,
    )
    orders = resp.get("result", {}).get("list", [])
    return orders[0] if orders else {}


def wallet(transport: pf.Transport, api_key: str, secret: str, timestamp: str) -> dict[str, str]:
    resp = pf._signed_get(
        transport,
        pf.DEMO_BASE,
        "/v5/account/wallet-balance",
        {"accountType": "UNIFIED"},
        api_key,
        secret,
        timestamp,
    )
    return pf._balances(resp)


def _now() -> str:
    return str(int(time.time() * 1000))


def _round_down(value: float, decimals: int) -> float:
    factor = 10**decimals
    return math.floor(value * factor) / factor


_TERMINAL = {"Filled", "Cancelled", "Rejected", "PartiallyFilledCanceled"}


def _poll_filled(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    order_id: str,
    symbol: str,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for _ in range(12):
        sleep(0.5)
        status = order_status(transport, api_key, secret, _now(), order_id, symbol=symbol)
        if status.get("orderStatus") in _TERMINAL:
            break
    return status


def _post_transport(url: str, headers: dict[str, str], body: bytes) -> bytes:
    raise RuntimeError(pf.NETWORK_QUARANTINE)


def _delta(before: dict[str, str], after: dict[str, str], coin: str) -> float:
    return float(after.get(coin, "0") or 0) - float(before.get(coin, "0") or 0)


def run_roundtrip(
    api_key: str,
    secret: str,
    *,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Preflight -> snapshot -> market buy -> poll to Filled -> snapshot -> reconcile."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    before = pre["balances"]
    placed = place_market_buy(
        post_transport, api_key, secret, _now(), symbol=symbol, quote_qty=quote_qty
    )
    if placed.get("retCode") != 0:
        return {"ok": False, "stage": "place", "error": str(placed.get("retMsg")), "raw": placed}
    order_id = str(placed.get("result", {}).get("orderId", ""))
    status = _poll_filled(get_transport, api_key, secret, order_id, symbol, sleep)
    after = wallet(get_transport, api_key, secret, _now())
    base_coin = symbol.removesuffix("USDT")
    return {
        "ok": status.get("orderStatus") == "Filled",
        "stage": "done",
        "order_id": order_id,
        "order_status": status.get("orderStatus"),
        "symbol": symbol,
        "filled_qty": status.get("cumExecQty"),
        "avg_price": status.get("avgPrice"),
        "fee": status.get("cumExecFee"),
        "reconcile": {
            f"{base_coin}_delta": round(_delta(before, after, base_coin), 8),
            "USDT_delta": round(_delta(before, after, "USDT"), 4),
        },
        "balances_before": before,
        "balances_after": after,
    }


def open_and_close_cycle(
    api_key: str,
    secret: str,
    *,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """One dummy-signal cycle: BUY a small amount, then SELL it back to flat. Reconciled."""
    base_coin = symbol.removesuffix("USDT")
    before = wallet(get_transport, api_key, secret, _now())
    buy = place_market_buy(
        post_transport, api_key, secret, _now(), symbol=symbol, quote_qty=quote_qty
    )
    if buy.get("retCode") != 0:
        return {"ok": False, "stage": "buy", "error": str(buy.get("retMsg"))}
    buy_status = _poll_filled(
        get_transport, api_key, secret, str(buy["result"]["orderId"]), symbol, sleep
    )
    mid = wallet(get_transport, api_key, secret, _now())
    net_base = _round_down(_delta(before, mid, base_coin), BASE_STEP_DECIMALS)
    if net_base <= 0:
        return {"ok": False, "stage": "sell", "error": "no base received to close"}
    sell = place_market_sell(
        post_transport, api_key, secret, _now(), symbol=symbol, base_qty=net_base
    )
    if sell.get("retCode") != 0:
        return {"ok": False, "stage": "sell", "error": str(sell.get("retMsg")), "held": net_base}
    sell_status = _poll_filled(
        get_transport, api_key, secret, str(sell["result"]["orderId"]), symbol, sleep
    )
    after = wallet(get_transport, api_key, secret, _now())
    return {
        "ok": sell_status.get("orderStatus") == "Filled",
        "qty": net_base,
        "entry_price": buy_status.get("avgPrice"),
        "exit_price": sell_status.get("avgPrice"),
        "buy_fee": buy_status.get("cumExecFee"),
        "sell_fee": sell_status.get("cumExecFee"),
        "usdt_net": round(_delta(before, after, "USDT"), 4),
        "residual_base": round(_delta(before, after, base_coin), 8),
    }


def session(
    api_key: str,
    secret: str,
    *,
    cycles: int = 3,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    log: Callable[[str], None] = print,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run `cycles` dummy open+close cycles, logging each. Ends flat. Requires a GREEN preflight."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    log(f"preflight GREEN on {pre['host']} — running {cycles} demo open+close cycle(s)")
    results: list[dict[str, Any]] = []
    for index in range(1, cycles + 1):
        cycle = open_and_close_cycle(
            api_key,
            secret,
            quote_qty=quote_qty,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
        )
        results.append(cycle)
        if cycle.get("ok"):
            log(
                f"cycle {index}: BUY {cycle['qty']} BTC @ {cycle['entry_price']} -> "
                f"SELL @ {cycle['exit_price']}  net {cycle['usdt_net']} USDT (fees)"
            )
        else:
            log(f"cycle {index}: STOPPED at {cycle.get('stage')} — {cycle.get('error')}")
        sleep(1.0)
    filled = sum(1 for c in results if c.get("ok"))
    return {
        "ok": filled == cycles,
        "cycles_requested": cycles,
        "cycles_filled": filled,
        "total_usdt_net": round(sum(float(c.get("usdt_net", 0) or 0) for c in results), 4),
        "cycles": results,
        "note": "Demo/fake money, ends flat. Machinery test only — no strategy is validated; "
        "real execution_authority stays NONE.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bybit demo execution round-trip / session.")
    parser.add_argument("--cycles", type=int, default=3, help="open+close cycles to run")
    parser.add_argument("--quote", type=float, default=DEFAULT_QUOTE_QTY, help="USDT per order")
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = session(api_key, secret, cycles=args.cycles, quote_qty=args.quote)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
