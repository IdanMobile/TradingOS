#!/usr/bin/env python3
"""Funding-carry DEMO bot — the one edge with a real reason to make money, on fake money.

Delta-neutral funding carry: LONG spot + SHORT perp of the same size. Price risk cancels; while
short the perp you COLLECT the funding rate (when it is positive). This runs one demonstration
cycle on the Bybit demo: read the live funding rate, open both legs, report the delta-neutral
position + the funding it would earn, then close both legs back to flat.

This is the first bot whose signal is an actual economic edge (not price prediction). It is still
a DEMO/machinery + candidate run — carry's validation is not genuine (off-sample counterparty
tail), real execution_authority stays NONE, demo/fake money only, notional capped, demo-host
locked. The perp leg exercises the S4-class capability *on demo only*. See DEMO_LANE_PLAN.md.

Run: python scripts/demo_carry_bot.py

ponytail: reuses rt order/poll/wallet primitives + the persisted activity log the console reads;
new code is the linear-perp order + funding-rate read + the two-leg open/close.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import scripts.demo_strategy_bot as sbot  # noqa: E402

CARRY_MAX_NOTIONAL = 300.0  # demo cap per leg (perps need >= 0.001 BTC ~ $65, so above spot cap)
DEFAULT_BASE_QTY = 0.001  # BTCUSDT perp minimum order size
SYMBOL = "BTCUSDT"


def fetch_carry_signal(transport: pf.Transport, base: str, symbol: str) -> dict:
    """Live linear-perp funding rate + prices (public, no auth)."""
    row = json.loads(transport(f"{base}/v5/market/tickers?category=linear&symbol={symbol}", {}))
    ticker = row["result"]["list"][0]
    return {
        "funding_rate": float(ticker["fundingRate"]),
        "mark_price": float(ticker["markPrice"]),
        "last_price": float(ticker["lastPrice"]),
    }


def _order(
    post: rt.PostTransport, api_key: str, secret: str, order: dict[str, object], notional: float
) -> dict:
    if notional > CARRY_MAX_NOTIONAL:
        raise ValueError(f"leg notional {notional:.2f} exceeds the {CARRY_MAX_NOTIONAL} USDT cap")
    return rt._order_create(post, api_key, secret, rt._now(), pf.DEMO_BASE, order)


def perp_position(get: pf.Transport, api_key: str, secret: str, symbol: str) -> dict:
    resp = pf._signed_get(
        get, pf.DEMO_BASE, "/v5/position/list", {"category": "linear", "symbol": symbol},
        api_key, secret, rt._now(),
    )  # fmt: skip
    positions = resp.get("result", {}).get("list", [])
    return positions[0] if positions else {}


def _poll_leg(
    get: pf.Transport, api_key: str, secret: str, category: str, symbol: str, order_id: str, sleep
) -> dict:  # type: ignore[no-untyped-def]
    """Category-aware status. Unknown or missing status remains unverified."""
    status: dict = {}
    for _ in range(5):
        sleep(0.4)
        params = {"category": category, "symbol": symbol, "orderId": order_id}
        resp = pf._signed_get(
            get, pf.DEMO_BASE, "/v5/order/realtime", params, api_key, secret, rt._now()
        )
        rows = resp.get("result", {}).get("list", [])
        if not rows:
            resp = pf._signed_get(
                get,
                pf.DEMO_BASE,
                "/v5/order/history",
                params,
                api_key,
                secret,
                rt._now(),
            )
            rows = resp.get("result", {}).get("list", [])
        status = rows[0] if rows else {}
        if status.get("orderStatus") in {"Filled", "Cancelled", "Rejected"}:
            break
    return status


def run_carry(
    api_key: str,
    secret: str,
    *,
    symbol: str = SYMBOL,
    base_qty: float = DEFAULT_BASE_QTY,
    get_transport: pf.Transport = pf._urllib_transport,
    market_transport: pf.Transport = sbot.public_get,
    post_transport: rt.PostTransport = rt._post_transport,
    sleep=rt.time.sleep,  # type: ignore[attr-defined]
    log=print,  # type: ignore[assignment]
    record=lambda _e: None,  # type: ignore[assignment]
) -> dict:
    """Preflight, read funding, open long-spot/short-perp, report, then close both legs."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    signal = fetch_carry_signal(market_transport, pf.DEMO_BASE, symbol)
    funding, price = signal["funding_rate"], signal["last_price"]
    favorable = funding > 0  # short-perp collects funding when it is positive
    log(
        f"funding {funding * 100:.4f}%/8h, mark {price:.1f} — carry "
        f"{'FAVORABLE (short perp earns)' if favorable else 'unfavorable (would pay)'}"
    )
    if not favorable:
        return {
            "ok": False,
            "stage": "signal",
            "signal": signal,
            "carry_favorable": False,
            "legs": [],
            "note": "No orders: the current funding sign would make the short-perp leg pay.",
        }
    base_coin = symbol.removesuffix("USDT")
    quote = round(base_qty * price * 1.01, 2)  # spend a hair over to receive ~base_qty spot

    def remember(side: str, result: dict) -> None:
        record({"recorded_at": datetime.now(UTC).isoformat(), "symbol": symbol,
                "signal": f"funding_carry({funding * 100:.3f}%)", "side": side,
                "signal_price": str(price), "fill_price": result.get("fill"),
                "qty": result.get("qty")})  # fmt: skip

    legs: list[dict] = []

    def leg(name: str, order: dict, notional: float) -> dict:
        placed = _order(post_transport, api_key, secret, order, notional)
        if placed.get("retCode") != 0:
            log(f"  {name}: REJECTED — {placed.get('retMsg')}")
            out = {"ok": False, "qty": order.get("qty"), "fill": None}
            legs.append({"leg": name, **out})
            return out
        status = _poll_leg(
            get_transport, api_key, secret, str(order["category"]), symbol,
            str(placed["result"]["orderId"]), sleep,
        )  # fmt: skip
        filled = status.get("orderStatus") == "Filled"
        fill = status.get("avgPrice") if filled else None
        out = {"ok": filled, "qty": order.get("qty"), "fill": fill}
        log(f"  {name}: {'Filled' if filled else status.get('orderStatus')} "
            f"{order.get('qty')} @ {fill}")  # fmt: skip
        remember(name, out)
        legs.append({"leg": name, **out})
        return out

    # OPEN delta-neutral: buy spot + short perp.
    spot_open = leg(
        "SPOT_BUY",
        {"category": "spot", "symbol": symbol, "side": "Buy", "orderType": "Market",
         "qty": str(quote), "marketUnit": "quoteCoin"}, quote,
    )  # fmt: skip
    if not spot_open["ok"]:
        return {"ok": False, "stage": "spot_open", "signal": signal, "legs": legs}
    perp_open = leg(
        "PERP_SHORT",
        {"category": "linear", "symbol": symbol, "side": "Sell", "orderType": "Market",
         "qty": str(base_qty)}, base_qty * price,
    )  # fmt: skip
    position = perp_position(get_transport, api_key, secret, symbol)
    log(
        f"  position: perp {position.get('side', '?')} {position.get('size', '?')} "
        f"{base_coin}, spot long ~{base_qty} — delta-neutral; would collect {funding * 100:.3f}%/8h"
    )

    # CLOSE both legs back to flat, including immediate unwind after an asymmetric open.
    spot_qty = rt._round_down(base_qty, rt.BASE_STEP_DECIMALS)
    sell_order = {
        "category": "spot", "symbol": symbol, "side": "Sell",
        "orderType": "Market", "qty": str(spot_qty), "marketUnit": "baseCoin",
    }  # fmt: skip
    close_order = {
        "category": "linear", "symbol": symbol, "side": "Buy",
        "orderType": "Market", "qty": str(base_qty), "reduceOnly": True,
    }  # fmt: skip
    if perp_open["ok"]:
        leg("PERP_CLOSE", close_order, base_qty * price)
    leg("SPOT_SELL", sell_order, spot_qty * price)

    final_position = perp_position(get_transport, api_key, secret, symbol)
    final_wallet = rt.wallet(get_transport, api_key, secret, rt._now())
    perp_flat = float(final_position.get("size", 0) or 0) == 0
    spot_delta = abs(rt._delta(pre["balances"], final_wallet, base_coin))
    reconciled_flat = perp_flat and spot_delta <= 10 ** (-rt.BASE_STEP_DECIMALS)

    return {
        "ok": (
            perp_open["ok"]
            and all(leg_result.get("ok") for leg_result in legs)
            and len(legs) == 4
            and reconciled_flat
        ),
        "signal": signal,
        "carry_favorable": favorable,
        "legs": legs,
        "reconciliation": {"perp_flat": perp_flat, "spot_base_delta": spot_delta},
        "note": "Delta-neutral carry, demo/fake money, ends flat. Machinery + candidate — carry's "
        "validation is NOT genuine (counterparty tail); real execution_authority stays NONE.",
    }


def main() -> int:
    argparse.ArgumentParser(description="Funding-carry demo bot.").parse_args()
    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = run_carry(api_key, secret, record=sbot._record)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
