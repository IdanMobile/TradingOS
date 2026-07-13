"""Offline checks for the funding-carry demo bot (no network, no real key)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_carry_bot as cb  # noqa: E402

KEY, SECRET = "demo-key", "demo-secret"


def test_fetch_carry_signal_parses_funding_and_prices() -> None:
    ticker = {
        "result": {"list": [{"fundingRate": "0.0001", "markPrice": "63800", "lastPrice": "63810"}]}
    }
    market = lambda url, h: json.dumps(ticker).encode()  # noqa: E731
    signal = cb.fetch_carry_signal(market, cb.pf.DEMO_BASE, "BTCUSDT")
    assert signal["funding_rate"] == 0.0001 and signal["last_price"] == 63810.0


def test_order_enforces_carry_cap() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        cb._order(
            lambda u, h, b: b"{}", KEY, SECRET, {"category": "spot"}, cb.CARRY_MAX_NOTIONAL + 1
        )


def test_run_carry_opens_and_closes_four_legs() -> None:
    bodies: list[dict] = []
    positions = iter(
        [
            {"retCode": 0, "result": {"list": [{"side": "Sell", "size": "0.001"}]}},
            {"retCode": 0, "result": {"list": [{"side": "None", "size": "0"}]}},
        ]
    )

    responses = {
        "query-api": {
            "retCode": 0,
            "result": {
                "readOnly": 0,
                "permissions": {"Spot": ["SpotTrade"], "Derivatives": ["DerivativesTrade"]},
            },
        },
        "wallet-balance": {
            "retCode": 0,
            "result": {"list": [{"coin": [{"coin": "USDT", "walletBalance": "50000"}]}]},
        },
        "order/realtime": {
            "retCode": 0,
            "result": {
                "list": [{"orderStatus": "Filled", "avgPrice": "63800", "cumExecQty": "0.001"}]
            },
        },
    }

    def get(url: str, headers: dict[str, str]) -> bytes:
        if "position/list" in url:
            return json.dumps(next(positions)).encode()
        for key, payload in responses.items():
            if key in url:
                return json.dumps(payload).encode()
        raise AssertionError(url)

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        bodies.append(json.loads(body))
        return json.dumps({"retCode": 0, "result": {"orderId": "OID"}}).encode()

    market = lambda url, h: json.dumps(  # noqa: E731
        {
            "result": {
                "list": [{"fundingRate": "0.0001", "markPrice": "63800", "lastPrice": "63800"}]
            }
        }
    ).encode()
    report = cb.run_carry(
        KEY, SECRET, get_transport=get, market_transport=market, post_transport=post,
        sleep=lambda _s: None,
    )  # fmt: skip
    assert report["ok"] is True and report["carry_favorable"] is True
    assert [leg["leg"] for leg in report["legs"]] == [
        "SPOT_BUY",
        "PERP_SHORT",
        "PERP_CLOSE",
        "SPOT_SELL",
    ]
    # The short leg is a linear-perp SELL; the close is a reduce-only linear BUY.
    short = next(b for b in bodies if b["category"] == "linear" and b["side"] == "Sell")
    close = next(b for b in bodies if b["category"] == "linear" and b["side"] == "Buy")
    assert short["orderType"] == "Market" and close["reduceOnly"] is True


def test_run_carry_stops_when_preflight_is_not_green() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Wallet": ["Withdraw"]}}}
            ).encode()
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    def boom(url: str, headers: dict[str, str]) -> bytes:
        raise AssertionError("must not read market or trade when preflight fails")

    report = cb.run_carry(KEY, SECRET, get_transport=get, market_transport=boom)
    assert report["ok"] is False and report["stage"] == "preflight"


def test_run_carry_does_not_trade_when_funding_is_unfavorable() -> None:
    responses = {
        "query-api": {
            "retCode": 0,
            "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}},
        },
        "wallet-balance": {"retCode": 0, "result": {"list": []}},
    }

    def get(url: str, headers: dict[str, str]) -> bytes:
        payload = next(payload for key, payload in responses.items() if key in url)
        return json.dumps(payload).encode()

    def market(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps(
            {
                "result": {
                    "list": [{"fundingRate": "-0.0001", "markPrice": "63800", "lastPrice": "63800"}]
                }
            }
        ).encode()

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        raise AssertionError("unfavorable funding must not place orders")

    report = cb.run_carry(
        KEY, SECRET, get_transport=get, market_transport=market, post_transport=post
    )
    assert report["ok"] is False and report["stage"] == "signal" and report["legs"] == []


def test_poll_leg_does_not_treat_missing_status_as_filled() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    assert cb._poll_leg(get, KEY, SECRET, "spot", "BTCUSDT", "OID", lambda _s: None) == {}
