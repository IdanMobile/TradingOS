"""Offline checks for the Bybit demo execution round-trip (no network, no real key)."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402

KEY, SECRET, TS = "demo-key", "demo-secret", "1700000000000"


def test_sign_post_matches_independent_hmac() -> None:
    body = '{"category":"spot"}'
    expected = hmac.new(
        SECRET.encode(), f"{TS}{KEY}{pf.RECV_WINDOW}{body}".encode(), hashlib.sha256
    ).hexdigest()
    assert rt.sign_post(SECRET, TS, KEY, body) == expected


def test_place_market_buy_refuses_non_demo_host() -> None:
    with pytest.raises(ValueError, match="non-demo host"):
        rt.place_market_buy(
            lambda u, h, b: b"{}", KEY, SECRET, TS, base="https://api.bybit.com", quote_qty=10
        )


def test_place_market_buy_enforces_notional_cap() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        rt.place_market_buy(lambda u, h, b: b"{}", KEY, SECRET, TS, quote_qty=rt.MAX_NOTIONAL + 1)


def test_place_market_buy_signs_and_sends_capped_spot_order() -> None:
    captured: dict[str, object] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["url"], captured["headers"], captured["body"] = url, headers, body.decode()
        return json.dumps({"retCode": 0, "result": {"orderId": "OID-1"}}).encode()

    resp = rt.place_market_buy(post, KEY, SECRET, TS, quote_qty=25)
    body = json.loads(str(captured["body"]))
    assert body == {
        "category": "spot",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Market",
        "qty": "25",
        "marketUnit": "quoteCoin",
    }
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["X-BAPI-SIGN"] == rt.sign_post(SECRET, TS, KEY, str(captured["body"]))
    assert resp["result"]["orderId"] == "OID-1"


def test_run_roundtrip_reconciles_a_filled_order() -> None:
    # GET transport answers preflight (query-api + wallet before/after) and order status.
    wallet_calls = iter(
        [  # before (from preflight), then after the fill
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "USDT", "walletBalance": "50000"},
                                {"coin": "BTC", "walletBalance": "1"},
                            ]
                        }
                    ]
                },
            },
            {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "coin": [
                                {"coin": "USDT", "walletBalance": "49974.99"},
                                {"coin": "BTC", "walletBalance": "1.0004"},
                            ]
                        }
                    ]
                },
            },
        ]  # fmt: skip
    )

    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}}
            ).encode()
        if "wallet-balance" in url:
            return json.dumps(next(wallet_calls)).encode()
        if "order/realtime" in url:
            return json.dumps(
                {"retCode": 0, "result": {"list": [{
                    "orderStatus": "Filled", "cumExecQty": "0.0004",
                    "avgPrice": "62500", "cumExecFee": "0.01",
                }]}}
            ).encode()  # fmt: skip
        raise AssertionError(url)

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        return json.dumps({"retCode": 0, "result": {"orderId": "OID-9"}}).encode()

    report = rt.run_roundtrip(
        KEY, SECRET, get_transport=get, post_transport=post, sleep=lambda _s: None
    )
    assert report["ok"] is True
    assert report["order_status"] == "Filled"
    assert report["filled_qty"] == "0.0004"
    assert report["reconcile"]["BTC_delta"] == pytest.approx(0.0004)
    assert report["reconcile"]["USDT_delta"] == pytest.approx(-25.01)


def test_run_roundtrip_stops_when_preflight_is_not_green() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:  # a key that can move funds -> preflight unsafe
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Wallet": ["Withdraw"]}}}
            ).encode()
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        raise AssertionError("must not place an order when preflight is not green")

    report = rt.run_roundtrip(KEY, SECRET, get_transport=get, post_transport=post)
    assert report["ok"] is False and report["stage"] == "preflight"


def test_round_down_truncates_to_base_step() -> None:
    assert rt._round_down(0.000391775, 6) == 0.000391  # never rounds up past what we hold
    assert rt._round_down(0.5, 6) == 0.5


def test_place_market_sell_signs_a_base_order() -> None:
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {"orderId": "S1"}}).encode()

    rt.place_market_sell(post, KEY, SECRET, TS, base_qty=0.0004)
    assert json.loads(captured["body"]) == {
        "category": "spot",
        "symbol": "BTCUSDT",
        "side": "Sell",
        "orderType": "Market",
        "qty": "0.0004",
        "marketUnit": "baseCoin",
    }


def _wallet(btc: float, usdt: float) -> dict:
    return {
        "retCode": 0,
        "result": {
            "list": [
                {
                    "coin": [
                        {"coin": "BTC", "walletBalance": str(btc)},
                        {"coin": "USDT", "walletBalance": str(usdt)},
                    ]
                }
            ]
        },
    }


def _cycle_transports(wallet_seq: list[dict]) -> tuple:
    wallets = iter(wallet_seq)
    fills = {
        "B1": {"orderStatus": "Filled", "cumExecQty": "0.0004", "avgPrice": "62500",
               "cumExecFee": "0.0000004"},
        "S1": {"orderStatus": "Filled", "cumExecQty": "0.0004", "avgPrice": "62490",
               "cumExecFee": "0.025"},
    }  # fmt: skip

    def get(url: str, headers: dict[str, str]) -> bytes:
        if "query-api" in url:
            return json.dumps(
                {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}}
            ).encode()
        if "wallet-balance" in url:
            return json.dumps(next(wallets)).encode()
        if "order/realtime" in url:
            oid = url.split("orderId=", 1)[1].split("&", 1)[0]
            return json.dumps({"retCode": 0, "result": {"list": [fills[oid]]}}).encode()
        raise AssertionError(url)

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        side = json.loads(body)["side"]
        return json.dumps(
            {"retCode": 0, "result": {"orderId": "B1" if side == "Buy" else "S1"}}
        ).encode()

    return get, post


def test_open_and_close_cycle_ends_flat() -> None:
    # before -> after buy (+0.0004 BTC, -25 USDT) -> after sell (~flat, small fee loss)
    get, post = _cycle_transports([_wallet(0, 50000), _wallet(0.0004, 49975), _wallet(0, 49999.9)])
    cycle = rt.open_and_close_cycle(
        KEY, SECRET, get_transport=get, post_transport=post, sleep=lambda _s: None
    )
    assert cycle["ok"] is True
    assert cycle["qty"] == 0.0004
    assert cycle["entry_price"] == "62500" and cycle["exit_price"] == "62490"
    assert cycle["usdt_net"] == pytest.approx(-0.1)  # only fees lost; ends flat


def test_session_runs_multiple_cycles_and_logs() -> None:
    wallet_seq = [_wallet(0, 50000)]  # preflight snapshot
    for _ in range(2):  # each cycle reads before, mid, after
        wallet_seq += [_wallet(0, 50000), _wallet(0.0004, 49975), _wallet(0, 49999.9)]
    get, post = _cycle_transports(wallet_seq)
    lines: list[str] = []
    report = rt.session(
        KEY, SECRET, cycles=2, log=lines.append,
        get_transport=get, post_transport=post, sleep=lambda _s: None,
    )  # fmt: skip
    assert report["ok"] is True
    assert report["cycles_filled"] == 2
    assert sum(line.startswith("cycle ") for line in lines) == 2  # one log line per cycle
