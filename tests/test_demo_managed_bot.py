"""Offline checks for the always-on managed demo bot (no network, no real key)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_managed_bot as mb  # noqa: E402

KEY, SECRET = "demo-key", "demo-secret"


def _klines(closes: list[float]) -> dict:
    rows = [[str(i * 60000), str(c), str(c + 5), str(c - 5), str(c), "10", "0"]
            for i, c in enumerate(closes)]  # fmt: skip
    return {"retCode": 0, "result": {"list": list(reversed(rows))}}  # Bybit: newest-first


def _transports(cycle_closes: list[list[float]]):  # type: ignore[no-untyped-def]
    market_iter = iter([json.dumps(_klines(c)).encode() for c in cycle_closes])
    wallets = iter([
        {"retCode": 0, "result": {"list": [{"coin": [{"coin": "BTC", "walletBalance": "0"}]}]}},
        {"retCode": 0, "result": {"list": [{"coin": [{"coin": "BTC", "walletBalance": "0"}]}]}},
        {"retCode": 0, "result": {"list": [{"coin": [{"coin": "BTC", "walletBalance": "0.003"}]}]}},
    ])  # fmt: skip

    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}}
            ).encode()
        if "wallet-balance" in url:
            return json.dumps(next(wallets)).encode()
        if "order/realtime" in url:
            fill = {"orderStatus": "Filled", "avgPrice": "130", "cumExecQty": "0.003"}
            return json.dumps({"retCode": 0, "result": {"list": [fill]}}).encode()
        raise AssertionError(url)

    def market(url: str, headers: dict[str, str]) -> bytes:
        return next(market_iter)

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        return json.dumps({"retCode": 0, "result": {"orderId": "OID"}}).encode()

    return get, market, post


def _run(cycle_closes: list[list[float]]) -> dict:
    get, market, post = _transports(cycle_closes)
    return mb.run_managed(
        KEY, SECRET, entry_w=20, exit_w=10, atr_w=14, quote_qty=100.0, cycles=len(cycle_closes),
        get_transport=get, market_transport=market, post_transport=post,
        sleep=lambda _s: None, log=lambda _m: None,
    )  # fmt: skip


def test_bot_enters_on_breakout_then_scales_out_all_tps() -> None:
    breakout = [100.0] * 50 + [130, 130]  # close[-2]=130 breaks the 20-bar high -> entry
    surge = [100.0] * 51 + [100000]  # price far above every TP -> all four TPs trigger -> flat
    report = _run([breakout, surge])
    sides = [t["side"] for t in report["trades"]]
    assert sides[0] == "BUY"
    assert any("TP" in s for s in sides[1:])  # scaled out at take-profits, not the stop


def test_bot_stops_out_when_price_breaks_the_stop() -> None:
    breakout = [100.0] * 50 + [130, 130]
    crash = [100.0] * 51 + [1]  # far below the stop -> stop-out closes the remainder
    report = _run([breakout, crash])
    sides = [t["side"] for t in report["trades"]]
    assert sides == ["BUY", "STOP_SELL"]


def test_managed_bot_stops_when_preflight_is_not_green() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Wallet": ["Withdraw"]}}}
            ).encode()
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    def boom(url: str, headers: dict[str, str]) -> bytes:
        raise AssertionError("must not fetch market or trade when preflight fails")

    report = mb.run_managed(KEY, SECRET, cycles=1, get_transport=get, market_transport=boom)
    assert report["ok"] is False and report["stage"] == "preflight"
