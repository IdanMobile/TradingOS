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


def test_authenticated_post_transport_is_quarantined() -> None:
    with pytest.raises(RuntimeError, match="quarantined"):
        rt._post_transport("https://api-demo.bybit.com/v5/order/create", {}, b"{}")


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


# --- Stage B (default-disabled) Bybit V5 client-key + reconciliation adapter tests -------------

DEMO = pf.DEMO_BASE


def test_validate_client_key_accepts_len_1_and_36_rejects_0_37_and_bad_chars() -> None:
    assert rt.validate_client_key("a") == "a"
    assert rt.validate_client_key("A9_-" * 9) == "A9_-" * 9  # exactly 36 chars
    for bad in ("", "x" * 37, "has space", "has/slash", "emoji\U0001f600", 123, None):
        with pytest.raises(ValueError, match="orderLinkId"):
            rt.validate_client_key(bad)


def test_order_create_validates_and_forwards_orderlinkid_persisted_key_equals_posted() -> None:
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {"orderId": "OID-1"}}).encode()

    key = "tios2_r_" + "0" * 28  # 36 chars, exactly what the lane persists before POST
    order = {"category": "spot", "symbol": "ETHUSDT", "side": "Sell", "orderLinkId": key}
    rt._order_create(post, KEY, SECRET, TS, DEMO, order)
    assert json.loads(captured["body"])["orderLinkId"] == key  # posted == persisted


def test_order_create_rejects_bad_orderlinkid_before_any_post() -> None:
    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        raise AssertionError("a malformed client key must never reach the venue")

    order = {"category": "spot", "symbol": "ETHUSDT", "orderLinkId": "x" * 37}
    with pytest.raises(ValueError, match="orderLinkId"):
        rt._order_create(post, KEY, SECRET, TS, DEMO, order)


def test_create_retcode_zero_is_acknowledged_pending_not_filled() -> None:
    assert (
        rt.classify_create_ack({"retCode": 0, "result": {"orderId": "OID"}})
        == "ACKNOWLEDGED_PENDING"
    )
    assert rt.classify_create_ack({"retCode": 10001, "retMsg": "err"}) == "VENUE_REJECTED"


def _exec_row(exec_id: str, exec_time: str, qty: str = "0.01", **extra: object) -> dict:
    row = {
        "execId": exec_id,
        "execTime": exec_time,
        "execQty": qty,
        "orderId": "O",
        "leavesQty": "0",
    }
    row.update(extra)
    return row


def test_dedupe_executions_drops_identical_and_orders_deterministically() -> None:
    rows = [
        _exec_row("b", "100"),
        _exec_row("a", "100"),
        _exec_row("a", "100"),  # identical duplicate -> dropped
    ]
    out = rt.dedupe_executions(rows)
    assert [r["execId"] for r in out] == ["a", "b"]  # same execTime -> tie-break by execId


def test_dedupe_executions_conflicting_execid_fails_closed() -> None:
    with pytest.raises(rt.ExecutionConflict, match="conflicting duplicate execId"):
        rt.dedupe_executions([_exec_row("a", "100", qty="0.01"), _exec_row("a", "100", qty="0.02")])


def _key_get(pages: dict[str, list[dict]]) -> object:
    """Signed-GET fake keyed by endpoint path; serves single-page results by default."""

    def get(url: str, headers: dict[str, str]) -> bytes:
        for path, rows in pages.items():
            if path in url:
                return json.dumps(
                    {"retCode": 0, "result": {"list": rows, "nextPageCursor": ""}}
                ).encode()
        raise AssertionError(f"unexpected GET {url}")

    return get


def test_reconcile_realtime_hit_collects_executions() -> None:
    key = "tios2_" + "a" * 20
    get = _key_get(
        {
            "/v5/order/realtime": [{"orderLinkId": key, "orderStatus": "Filled"}],
            "/v5/order/history": [],
            "/v5/execution/list": [
                _exec_row("e1", "100", execValue="20", execFee="0.01", feeCurrency="USDT")
            ],
        }
    )
    out = rt.reconcile_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")
    assert out["status"] == "Filled" and out["source"] == "REALTIME"
    assert len(out["executions"]) == 1


def test_reconcile_realtime_miss_falls_back_to_history() -> None:
    key = "tios2_" + "b" * 20
    get = _key_get(
        {
            "/v5/order/realtime": [],  # miss is NOT "no order"
            "/v5/order/history": [{"orderLinkId": key, "orderStatus": "PartiallyFilledCanceled"}],
            "/v5/execution/list": [
                _exec_row("e1", "100", execValue="10", execFee="0", feeCurrency="USDT")
            ],
        }
    )
    out = rt.reconcile_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")
    assert out["status"] == "PartiallyFilledCanceled" and out["source"] == "HISTORY"


def test_pagination_walks_cursor_pages() -> None:
    key = "tios2_" + "c" * 20
    seq = iter(
        [
            {"list": [_exec_row("e1", "1")], "nextPageCursor": "p2"},
            {"list": [_exec_row("e2", "2")], "nextPageCursor": ""},
        ]
    )

    def get(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps({"retCode": 0, "result": next(seq)}).encode()

    rows = rt.executions_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")
    assert [r["execId"] for r in rows] == ["e1", "e2"]


def test_pagination_cursor_loop_is_unresolved_not_empty() -> None:
    key = "tios2_" + "d" * 20

    def get(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps({"retCode": 0, "result": {"list": [], "nextPageCursor": "same"}}).encode()

    with pytest.raises(rt.ReconciliationUnresolved, match="cursor loop"):
        rt.orders_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")


def test_pagination_oversized_page_is_unresolved() -> None:
    key = "tios2_" + "e" * 20

    def get(url: str, headers: dict[str, str]) -> bytes:
        rows = [_exec_row(f"e{i}", "1") for i in range(51)]  # over the internal 50-row cap
        return json.dumps({"retCode": 0, "result": {"list": rows, "nextPageCursor": ""}}).encode()

    with pytest.raises(rt.ReconciliationUnresolved, match="50-row cap"):
        rt.executions_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")


def test_unknown_create_reconciles_by_key_and_never_reposts_create() -> None:
    # Reconciliation is a pure query flow — it takes only a GET transport, so it structurally
    # cannot replay a create POST for an unknown/ambiguous submission result.
    key = "tios2_" + "f" * 20
    get = _key_get(
        {
            "/v5/order/realtime": [{"orderLinkId": key, "orderStatus": "New"}],
            "/v5/order/history": [],
            "/v5/execution/list": [],
        }
    )
    out = rt.reconcile_by_client_key(get, KEY, SECRET, DEMO, key, "ETHUSDT")
    assert out["status"] == "New" and out["all_pages_complete"] is True


# --- P1-B: protective-stop / cancel client-key + async-ack + query-confirm adapters ------------


def test_place_stop_validates_and_forwards_orderlinkid() -> None:
    key = "tios2_r_" + "0" * 28  # the deterministic stop-create key the lane persists before POST
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {"orderId": "S1"}}).encode()

    rt.place_stop(
        post, KEY, SECRET, TS, DEMO,
        symbol="ETHUSDT", trigger_price="85", base_qty="0.01", client_key=key,
    )  # fmt: skip
    body = json.loads(captured["body"])
    assert body["orderLinkId"] == key and body["orderFilter"] == "StopOrder"


def test_place_stop_rejects_bad_orderlinkid_before_any_post() -> None:
    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        raise AssertionError("a malformed stop client key must never reach the venue")

    with pytest.raises(ValueError, match="orderLinkId"):
        rt.place_stop(
            post, KEY, SECRET, TS, DEMO,
            symbol="ETHUSDT", trigger_price="85", base_qty="0.01", client_key="x" * 37,
        )  # fmt: skip


def test_place_stop_without_key_stays_byte_identical() -> None:
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {"orderId": "S1"}}).encode()

    rt.place_stop(
        post, KEY, SECRET, TS, DEMO, symbol="ETHUSDT", trigger_price="85", base_qty="0.01"
    )
    assert "orderLinkId" not in json.loads(captured["body"])  # legacy compensating stop unchanged


def test_cancel_order_targets_original_orderlinkid_correlation() -> None:
    key = "tios2_" + "a" * 20
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {}}).encode()

    rt.cancel_order(post, KEY, SECRET, TS, DEMO, symbol="ETHUSDT", order_link_id=key)
    body = json.loads(captured["body"])
    assert body["orderLinkId"] == key and "orderId" not in body  # original correlation only


def test_cancel_order_by_id_stays_byte_identical() -> None:
    captured: dict[str, str] = {}

    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        captured["body"] = body.decode()
        return json.dumps({"retCode": 0, "result": {}}).encode()

    rt.cancel_order(post, KEY, SECRET, TS, DEMO, order_id="OID-7", symbol="ETHUSDT")
    # Assert on the RAW serialized bytes: json.loads dict equality is key-order-insensitive and
    # would pass even if orderId moved after orderFilter. The legacy body must be byte-for-byte
    # unchanged from pre-Wave-2 — category, symbol, orderId, then orderFilter.
    assert captured["body"] == (
        '{"category": "spot", "symbol": "ETHUSDT", "orderId": "OID-7", "orderFilter": "StopOrder"}'
    )


def test_cancel_order_requires_exactly_one_correlation() -> None:
    def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        raise AssertionError("cancel must not post with an ambiguous/absent correlation")

    with pytest.raises(ValueError, match="exactly one"):  # neither
        rt.cancel_order(post, KEY, SECRET, TS, DEMO, symbol="ETHUSDT")
    with pytest.raises(ValueError, match="exactly one"):  # both
        rt.cancel_order(
            post, KEY, SECRET, TS, DEMO,
            symbol="ETHUSDT", order_id="OID-7", order_link_id="tios2_" + "a" * 20,
        )  # fmt: skip


def test_stop_and_cancel_acks_are_async_pending_not_confirmed() -> None:
    # A create/cancel retCode=0 means ACCEPTED/PENDING; the caller must confirm by query, never
    # clear state on the ack alone.
    assert rt.classify_create_ack({"retCode": 0, "result": {}}) == "ACKNOWLEDGED_PENDING"
    assert rt.classify_create_ack({"retCode": 10001, "retMsg": "no"}) == "VENUE_REJECTED"


def test_order_status_legacy_empty_order_id_polls_silently() -> None:
    # CLEANUP: the legacy positional call (no client_key) with an empty orderId — e.g. a create ack
    # that returned no orderId — stays byte-identical to pre-Wave-2: it queries by "" and returns {}
    # rather than raising. Exactly-one enforcement applies ONLY to the new client_key usage.
    def get(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps({"retCode": 0, "result": {"list": []}}).encode()

    assert rt.order_status(get, KEY, SECRET, TS, "", base=DEMO, symbol="ETHUSDT") == {}
    # ...but passing BOTH a client_key and an orderId is still rejected (the new keyed usage).
    with pytest.raises(ValueError, match="exactly one"):
        rt.order_status(
            get, KEY, SECRET, TS, "OID-1",
            base=DEMO, symbol="ETHUSDT", client_key="tios2_" + "a" * 20,
        )  # fmt: skip


def test_order_status_reconciles_a_resting_stop_by_client_key() -> None:
    key = "tios2_r_" + "1" * 28
    captured: dict[str, str] = {}

    def get(url: str, headers: dict[str, str]) -> bytes:
        captured["url"] = url
        return json.dumps(
            {"retCode": 0, "result": {"list": [{"orderLinkId": key, "orderStatus": "Untriggered"}]}}
        ).encode()

    row = rt.order_status(get, KEY, SECRET, TS, base=DEMO, symbol="ETHUSDT", client_key=key)
    assert row["orderStatus"] == "Untriggered"  # a resting stop, confirmed by its original key
    assert f"orderLinkId={key}" in captured["url"] and "orderId=" not in captured["url"]
