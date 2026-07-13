"""Offline checks for the strategy-driven demo bot (no network, no real key)."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_strategy_bot as bot  # noqa: E402

KEY, SECRET = "demo-key", "demo-secret"


def _klines(closes: list[float]) -> dict:
    rows = [[str(i * 60000), str(c), str(c + 1), str(c - 1), str(c), "10", "0"]
            for i, c in enumerate(closes)]  # fmt: skip
    return {"retCode": 0, "result": {"list": list(reversed(rows))}}  # Bybit returns newest-first


def test_fetch_klines_returns_chronological_decimals() -> None:
    market = lambda url, headers: json.dumps(_klines([100, 101, 102])).encode()  # noqa: E731
    candles = bot.fetch_klines(market, bot.pf.DEMO_BASE, "BTCUSDT", "1", 3)
    assert candles["close"] == [Decimal("100"), Decimal("101"), Decimal("102")]  # oldest -> newest
    assert candles["high"][0] == Decimal("101") and candles["low"][0] == Decimal("99")


def test_bot_buys_on_breakout_and_sells_on_breakdown() -> None:
    # Flat, then a breakout above the 3-bar high, then a breakdown below the 2-bar low.
    closes = [100] * 8 + [130, 131, 90, 91]
    wallets = iter(
        [
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "BTC", "walletBalance": "0"},
                                {"coin": "USDT", "walletBalance": "50000"},
                            ]
                        }
                    ]
                },
            },  # preflight
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "BTC", "walletBalance": "0"},
                                {"coin": "USDT", "walletBalance": "50000"},
                            ]
                        }
                    ]
                },
            },  # buy: before
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "BTC", "walletBalance": "0.0004"},
                                {"coin": "USDT", "walletBalance": "49975"},
                            ]
                        }
                    ]
                },
            },  # buy: mid
        ]  # fmt: skip
    )

    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}}
            ).encode()
        if "wallet-balance" in url:
            return json.dumps(next(wallets)).encode()
        if "order/realtime" in url:
            return json.dumps(
                {"retCode": 0, "result": {"list": [{"orderStatus": "Filled",
                    "cumExecQty": "0.0004", "avgPrice": "130", "cumExecFee": "0.0001"}]}}
            ).encode()  # fmt: skip
        raise AssertionError(url)

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        side = json.loads(body)["side"]
        return json.dumps(
            {"retCode": 0, "result": {"orderId": "B1" if side == "Buy" else "S1"}}
        ).encode()

    market = lambda url, headers: json.dumps(_klines(closes)).encode()  # noqa: E731
    report = bot.run_bot(
        KEY, SECRET, symbol="BTCUSDT", entry_w=3, exit_w=2, bars=len(closes),
        get_transport=get, market_transport=market, post_transport=post, sleep=lambda _s: None,
    )  # fmt: skip
    sides = [t["side"] for t in report["trades"]]
    assert sides == ["BUY", "SELL"]  # entered the breakout, closed on the breakdown, ends flat


def test_bot_stops_when_preflight_is_not_green() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Wallet": ["Withdraw"]}}}
            ).encode()
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    def boom(url: str, headers: dict[str, str]) -> bytes:
        raise AssertionError("must not fetch market data or trade when preflight fails")

    report = bot.run_bot(KEY, SECRET, get_transport=get, market_transport=boom)
    assert report["ok"] is False and report["stage"] == "preflight"
