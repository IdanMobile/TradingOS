"""Offline tests for the D-104 stage-2 ETH demo measurement lane. No network, no keys."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import scripts.demo_eth_lane as lane

START = datetime(2026, 7, 1, tzinfo=UTC)


def _kline_rows(closes: list[tuple[str, str]]) -> list[list[str]]:
    """(close, volume) pairs -> Bybit kline rows oldest-first, plus a forming dummy bar."""
    rows = []
    for index, (close, volume) in enumerate(closes):
        open_ms = int((START + timedelta(hours=index)).timestamp() * 1000)
        rows.append([str(open_ms), "100", close, "90", close, volume, "0"])
    forming_ms = int((START + timedelta(hours=len(closes))).timestamp() * 1000)
    rows.append([str(forming_ms), "100", "100", "90", "100", "1", "0"])
    return rows


class FakeVenue:
    """URL-dispatching stand-in for both GET and POST transports."""

    def __init__(self, closes: list[tuple[str, str]]) -> None:
        self.closes = closes
        self.orders: list[dict] = []
        # Balances are STATE mutated by fills, not a canned sequence indexed by call
        # count. A call-indexed fake silently breaks whenever the lane changes how many
        # times it queries the wallet, and the resulting before/after delta reads as zero
        # — a failure that looks like a position bug but is entirely fixture artefact.
        self.balances = {"USDT": Decimal("1000"), "ETH": Decimal("0")}
        self.wallet_calls = 0
        self.stop_order_ids: set[str] = set()
        self.order_statuses: dict[str, str] = {}

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        if "/v5/market/kline" in url:
            rows = list(reversed(_kline_rows(self.closes)))
            return json.dumps({"result": {"list": rows}}).encode()
        if "/v5/market/tickers" in url:
            return json.dumps({"result": {"list": [{"lastPrice": "100"}]}}).encode()
        if "/v5/market/instruments-info" in url:
            return json.dumps(
                {
                    "result": {
                        "list": [
                            {
                                "lotSizeFilter": {"basePrecision": "0.00001"},
                                "priceFilter": {"tickSize": "0.01"},
                            }
                        ]
                    }
                }
            ).encode()
        if "/v5/account/wallet-balance" in url:
            self.wallet_calls += 1
            coins = [{"coin": k, "walletBalance": str(v)} for k, v in self.balances.items()]
            return json.dumps({"retCode": 0, "result": {"list": [{"coin": coins}]}}).encode()
        if "/v5/order/realtime" in url:
            order_id = parse_qs(urlsplit(url).query).get("orderId", [""])[0]
            status = self.order_statuses.get(
                order_id, "Untriggered" if order_id in self.stop_order_ids else "Filled"
            )
            return json.dumps(
                {
                    "result": {
                        "list": [
                            {
                                "orderStatus": status,
                                "avgPrice": "100",
                                "cumExecQty": "0.01",
                                "cumExecFee": "0.001",
                            }
                        ]
                    }
                }
            ).encode()
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url: str, headers: dict[str, str], body: bytes) -> bytes:
        assert "/v5/order/create" in url
        order = json.loads(body)
        self.orders.append(order)
        order_id = f"OID-{len(self.orders)}"
        if order.get("orderFilter") == "StopOrder":
            self.stop_order_ids.add(order_id)
        # Settle the fill into balances so the lane's own before/after reconciliation sees
        # a real movement, matching the /v5/order/realtime response below (0.01 @ 100).
        if order.get("orderFilter") != "StopOrder" and order["side"] == "Buy":
            self.balances["USDT"] -= Decimal("25")
            self.balances["ETH"] += Decimal("0.01")
        elif order.get("orderFilter") != "StopOrder":
            self.balances["ETH"] -= Decimal("0.01")
            self.balances["USDT"] += Decimal("1")
        return json.dumps({"retCode": 0, "result": {"orderId": order_id}}).encode()


@pytest.fixture()
def lane_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(lane, "LANE_DIR", tmp_path)
    monkeypatch.setattr(lane, "KILL_SWITCH", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(lane, "ORDERS_LEDGER", tmp_path / "orders.jsonl")
    monkeypatch.setattr(lane, "ACTIONS_LEDGER", tmp_path / "demo_lane_actions.jsonl")
    monkeypatch.setattr(lane, "LANE_STATE", tmp_path / "lane_state.json")
    monkeypatch.setattr(lane, "HEARTBEAT", tmp_path / "heartbeat.json")
    return tmp_path


def test_live_post_transport_refuses_non_demo_urls() -> None:
    for url in (
        "http://api-demo.bybit.com/v5/order/create",
        "https://api.bybit.com/v5/order/create",
        "https://api-demo.bybit.com.evil.example/v5/order/create",
    ):
        with pytest.raises(ValueError, match="non-demo"):
            lane._live_post_transport(url, {}, b"{}")


def test_lane_intent_validation() -> None:
    with pytest.raises(ValueError):
        lane.LaneIntent("Hold", Decimal("1"), "quoteCoin", "SIG-X", "r")
    with pytest.raises(ValueError):
        lane.LaneIntent("Buy", Decimal("1"), "baseCoin", "SIG-X", "r")
    with pytest.raises(ValueError):
        lane.LaneIntent("Sell", Decimal("0"), "baseCoin", "SIG-X", "r")
    lane.LaneIntent("Buy", Decimal("25"), "quoteCoin", "SIG-X", "ENTRY_LONG")


def test_quantize_down() -> None:
    assert lane.quantize_down(Decimal("0.123456789"), Decimal("0.00001")) == Decimal("0.12345")
    assert lane.quantize_down(Decimal("0.000004"), Decimal("0.00001")) == Decimal("0")


def test_kill_switch_blocks_and_records(lane_dirs: Path) -> None:
    (lane_dirs / "KILL_SWITCH").write_text("stop")
    venue = FakeVenue([("100", "10")])
    record = lane.place(
        lane.LaneIntent("Buy", Decimal("25"), "quoteCoin", "SIG-X", "ENTRY_LONG"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )
    assert record["ok"] is False and record["stage"] == "kill_switch"
    assert venue.orders == []
    lines = (lane_dirs / "orders.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["environment"] == "VENUE_DEMO"


def test_buy_and_sell_caps(lane_dirs: Path) -> None:
    venue = FakeVenue([("100", "10")])
    with pytest.raises(ValueError, match="cap"):
        lane.place(
            lane.LaneIntent("Buy", Decimal("51"), "quoteCoin", "SIG-X", "r"),
            "k",
            "s",
            get_transport=venue.get,
            post_transport=venue.post,
            sleep=lambda _s: None,
        )
    with pytest.raises(ValueError, match="cap"):
        lane.place(
            lane.LaneIntent("Sell", Decimal("2"), "baseCoin", "SIG-X", "r"),  # 200 USDT @ 100
            "k",
            "s",
            get_transport=venue.get,
            post_transport=venue.post,
            sleep=lambda _s: None,
        )
    assert venue.orders == []


def test_place_buy_records_and_reconciles(lane_dirs: Path) -> None:
    venue = FakeVenue([("100", "10")])
    record = lane.place(
        lane.LaneIntent("Buy", Decimal("25"), "quoteCoin", "SIG-1", "ENTRY_LONG"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )
    assert record["ok"] is True and record["order_id"] == "OID-1"
    assert record["reconcile"]["ETH_delta"] == pytest.approx(0.01)
    assert record["real_money"] is False and record["validation_state"] == "UNVALIDATED"
    assert venue.orders[0]["marketUnit"] == "quoteCoin"


def _flat_history() -> list[tuple[str, str]]:
    return [("100", "10")] * 50


def test_first_cycle_arms_cursor_without_trading(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    assert venue.orders == []
    assert heartbeat["fresh_signals"] == 0
    assert json.loads((lane_dirs / "lane_state.json").read_text())["cursor"] is not None


def test_fresh_breakout_after_cursor_places_one_buy(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    venue.closes = _flat_history() + [("200", "500")]  # fresh 40-bar breakout + volume surge
    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    assert heartbeat["fresh_signals"] >= 1
    buys = [o for o in venue.orders if o["side"] == "Buy"]
    stops = [o for o in venue.orders if o.get("orderFilter") == "StopOrder"]
    assert len(buys) == 1 and buys[0]["side"] == "Buy"
    # Entry also places the venue-resting -15% stop (survives local process death).
    assert len(stops) == 1 and stops[0]["side"] == "Sell"
    state = json.loads((lane_dirs / "lane_state.json").read_text())
    assert Decimal(state["lane_base"]) > 0
    assert state["resting_stop"]["order_id"] and Decimal(state["entry_price"]) > 0


def test_restart_with_filled_stop_latch_suppresses_all_posts(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    lane.write_state(
        {
            **armed,
            "lane_base": "0.01",
            "entry_price": "200",
            "resting_stop": {
                "state": "ACTIVE",
                "order_id": "STOP-FILLED",
                "trigger_price": "170",
                "base_qty": "0.01",
            },
        }
    )
    venue.closes = _flat_history() + [("200", "500")]

    first_heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    assert first_heartbeat["resting_stop"]["state"] == "FILLED_PENDING_RECONCILIATION"

    # A process restart reads the persisted latch and must not re-enter any POST path.
    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    assert venue.orders == []
    assert venue.wallet_calls > 0
    assert heartbeat["resting_stop"]["state"] == "FILLED_PENDING_RECONCILIATION"
    persisted = json.loads((lane_dirs / "lane_state.json").read_text())
    assert persisted["resting_stop"]["filled_order_id"] == "STOP-FILLED"


def test_unknown_active_stop_preflight_suppresses_all_posts(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    venue.order_statuses["STOP-UNKNOWN"] = ""
    lane.write_state(
        {
            **armed,
            "lane_base": "0.01",
            "entry_price": "200",
            "resting_stop": {
                "state": "ACTIVE",
                "order_id": "STOP-UNKNOWN",
                "trigger_price": "170",
                "base_qty": "0.01",
            },
        }
    )

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    assert venue.orders == []
    assert heartbeat["resting_stop"]["order_id"] == "STOP-UNKNOWN"


def test_cleared_active_stop_preflight_allows_replacement(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    venue.order_statuses["STOP-CLEARED"] = "Cancelled"
    lane.write_state(
        {
            **armed,
            "lane_base": "0.01",
            "entry_price": "100",
            "resting_stop": {
                "state": "ACTIVE",
                "order_id": "STOP-CLEARED",
                "trigger_price": "85",
                "base_qty": "0.01",
            },
        }
    )

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    stops = [order for order in venue.orders if order.get("orderFilter") == "StopOrder"]
    assert len(stops) == 1
    assert heartbeat["resting_stop"]["state"] == "ACTIVE"
    assert heartbeat["resting_stop"]["order_id"] == "OID-1"


def test_sub_step_position_keeps_cycle_alive_without_stop_post(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    lane.write_state(
        {
            **armed,
            "lane_base": "0.000009",
            "entry_price": "100",
            "resting_stop": None,
        }
    )

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    assert venue.orders == []
    assert heartbeat["lane_base"] == "0.000009"
    assert heartbeat["resting_stop"] is None
