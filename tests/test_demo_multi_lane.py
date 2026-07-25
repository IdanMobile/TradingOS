"""Offline tests for the multi-coin demo measurement lane. No network, no keys.

Proves the ETH lane stays byte-identical on defaults, that a non-ETH symbol routes its own
instrument/state/orders, that the per-coin -15% disaster stop is priced from that coin's own
entry, and that run_multi_cycle composes the SHARED kill switch and SHARED total-capital cap while
never letting one coin's failure abort the others. Demo/fake money, execution-measurement only.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_eth_lane as lane  # noqa: E402

START = datetime(2026, 7, 1, tzinfo=UTC)
OLD_CURSOR = "2020-01-01T00:00:00+00:00"  # older than any bar -> a breakout is fresh
FUTURE_CURSOR = "2999-01-01T00:00:00+00:00"  # newer than any bar -> no fresh signal fires


def _kline_rows(closes: list[tuple[str, str]]) -> list[list[str]]:
    rows = []
    for index, (close, volume) in enumerate(closes):
        open_ms = int((START + timedelta(hours=index)).timestamp() * 1000)
        rows.append([str(open_ms), "100", close, "90", close, volume, "0"])
    forming_ms = int((START + timedelta(hours=len(closes))).timestamp() * 1000)
    rows.append([str(forming_ms), "100", "100", "90", "100", "1", "0"])
    return rows


FLAT = [("100", "10")] * 50
BREAKOUT = FLAT + [("200", "500")]  # fresh 40-bar Donchian breakout + volume surge


class MultiVenue:
    """URL-dispatching GET/POST stand-in that serves per-symbol klines, marks, and fills."""

    def __init__(
        self,
        closes: dict[str, list[tuple[str, str]]] | None = None,
        marks: dict[str, str] | None = None,
        fail_kline: str | None = None,
    ) -> None:
        self.closes = closes or {}
        self.marks = marks or {}
        self.fail_kline = fail_kline
        self.orders: list[dict[str, Any]] = []
        self.balances: dict[str, Decimal] = {"USDT": Decimal("100000")}
        self.stop_ids: set[str] = set()

    @staticmethod
    def _symbol(url: str) -> str:
        return parse_qs(urlsplit(url).query).get("symbol", [""])[0]

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        symbol = self._symbol(url)
        if "/v5/market/kline" in url:
            if symbol == self.fail_kline:
                raise RuntimeError(f"kline unavailable for {symbol}")
            rows = list(reversed(_kline_rows(self.closes.get(symbol, FLAT))))
            return json.dumps({"result": {"list": rows}}).encode()
        if "/v5/market/tickers" in url:
            return json.dumps(
                {"result": {"list": [{"lastPrice": self.marks.get(symbol, "100")}]}}
            ).encode()
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
            coins = [{"coin": k, "walletBalance": str(v)} for k, v in self.balances.items()]
            return json.dumps({"retCode": 0, "result": {"list": [{"coin": coins}]}}).encode()
        if "/v5/order/realtime" in url:
            order_id = parse_qs(urlsplit(url).query).get("orderId", [""])[0]
            status = "Untriggered" if order_id in self.stop_ids else "Filled"
            return json.dumps(
                {
                    "result": {
                        "list": [
                            {
                                "orderId": order_id,
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
        base = str(order["symbol"]).removesuffix("USDT")
        self.balances.setdefault(base, Decimal("0"))
        if order.get("orderFilter") == "StopOrder":
            self.stop_ids.add(order_id)
        elif order["side"] == "Buy":
            self.balances["USDT"] -= Decimal("25")
            self.balances[base] += Decimal("0.01")
        else:
            self.balances[base] -= Decimal("0.01")
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


def _run(venue: MultiVenue, symbol: str, **kw: Any) -> dict[str, Any]:
    return lane.run_cycle(
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        symbol=symbol,
        **kw,
    )


def test_coin_universe_and_cap_constants() -> None:
    assert len(lane.DEMO_COINS) == 10
    assert lane.DEMO_COINS[1] == "ETHUSDT"  # ETH is the default single-symbol lane
    assert {"BTCUSDT", "SOLUSDT", "LTCUSDT"} <= set(lane.DEMO_COINS)
    assert lane.TOTAL_DEMO_CAPITAL_USDT == Decimal("300")


def test_default_symbol_still_routes_eth(lane_dirs: Path) -> None:
    # Byte-identical default: place() with no symbol still trades ETHUSDT and reconciles ETH_delta.
    venue = MultiVenue()
    record = lane.place(
        lane.LaneIntent("Buy", Decimal("25"), "quoteCoin", "SIG", "ENTRY_LONG"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )
    assert record["symbol"] == "ETHUSDT"
    assert venue.orders[0]["symbol"] == "ETHUSDT"
    assert "ETH_delta" in record["reconcile"]


def test_non_eth_symbol_routes_own_instrument_state_and_orders(lane_dirs: Path) -> None:
    venue = MultiVenue()
    venue.closes["SOLUSDT"] = FLAT
    _run(venue, "SOLUSDT")  # first cycle arms the cursor, trades nothing
    assert (lane_dirs / "lane_state_SOLUSDT.json").is_file()
    assert not (lane_dirs / "lane_state.json").is_file()  # ETH default file untouched
    assert venue.orders == []

    venue.closes["SOLUSDT"] = BREAKOUT  # a NEW breakout bar, now fresh
    hb = _run(venue, "SOLUSDT")

    assert hb["symbol"] == "SOLUSDT"
    buys = [o for o in venue.orders if o["side"] == "Buy"]
    assert len(buys) == 1 and buys[0]["symbol"] == "SOLUSDT"
    stops = [o for o in venue.orders if o.get("orderFilter") == "StopOrder"]
    assert len(stops) == 1 and stops[0]["symbol"] == "SOLUSDT"  # per-coin resting stop
    records = [json.loads(line) for line in (lane_dirs / "orders.jsonl").read_text().splitlines()]
    entry = next(r for r in records if r.get("reason") == "ENTRY_LONG")
    assert entry["symbol"] == "SOLUSDT" and entry["real_money"] is False
    state = json.loads((lane_dirs / "lane_state_SOLUSDT.json").read_text())
    assert Decimal(state["lane_base"]) > 0 and Decimal(state["entry_price"]) > 0
    assert (lane_dirs / "heartbeat_SOLUSDT.json").is_file()


def test_per_coin_disaster_stop_uses_that_coins_entry(lane_dirs: Path) -> None:
    # SOL is long from 100; its own mark falls to 80 (below the -15% => 85 level) -> it exits.
    venue = MultiVenue(marks={"SOLUSDT": "80"})
    lane.write_state(
        {"lane_base": "0.01", "cursor": FUTURE_CURSOR, "entry_price": "100", "resting_stop": None},
        "SOLUSDT",
    )
    hb = _run(venue, "SOLUSDT")

    sells = [o for o in venue.orders if o["side"] == "Sell" and o.get("orderFilter") != "StopOrder"]
    assert len(sells) == 1 and sells[0]["symbol"] == "SOLUSDT"
    assert hb["disaster_stop_event"] is not None
    assert "entry 100" in hb["disaster_stop_event"]["detail"]  # priced from SOL's own entry
    assert hb["lane_base"] == "0"


def test_shared_kill_switch_halts_all_coins(lane_dirs: Path) -> None:
    (lane_dirs / "KILL_SWITCH").write_text("stop")
    venue = MultiVenue()
    symbols = ["BTCUSDT", "SOLUSDT", "XRPUSDT"]
    report = lane.run_multi_cycle(
        "k",
        "s",
        symbols=symbols,
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )
    assert report["kill_switch"] is True
    assert venue.orders == []
    assert set(report["coins"]) == set(symbols)
    assert all(c["stage"] == "kill_switch" for c in report["coins"].values())


def test_shared_cap_blocks_new_entry_but_allows_risk_reduction(lane_dirs: Path) -> None:
    # BTC is already open (consuming the whole 25 USDT cap); SOL has a fresh breakout but must be
    # skipped, while BTC's own disaster-stop exit still runs (risk reduction is never cap-gated).
    venue = MultiVenue(marks={"BTCUSDT": "80"})
    venue.closes["SOLUSDT"] = BREAKOUT
    lane.write_state(
        {"lane_base": "0.01", "cursor": FUTURE_CURSOR, "entry_price": "100", "resting_stop": None},
        "BTCUSDT",
    )
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "SOLUSDT",
    )

    report = lane.run_multi_cycle(
        "k",
        "s",
        symbols=["BTCUSDT", "SOLUSDT"],
        total_cap=Decimal("25"),
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )

    assert [o for o in venue.orders if o["side"] == "Buy" and o["symbol"] == "SOLUSDT"] == []
    btc_sells = [
        o
        for o in venue.orders
        if o["side"] == "Sell" and o["symbol"] == "BTCUSDT" and o.get("orderFilter") != "StopOrder"
    ]
    assert len(btc_sells) == 1  # risk-reducing exit on the already-open coin proceeded
    assert report["coins"]["SOLUSDT"]["lane_base"] == "0"  # SOL never entered


def test_one_coin_failure_does_not_abort_multi_cycle(lane_dirs: Path) -> None:
    venue = MultiVenue(fail_kline="XRPUSDT")
    report = lane.run_multi_cycle(
        "k",
        "s",
        symbols=["BTCUSDT", "XRPUSDT", "SOLUSDT"],
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
    )
    assert "error" in report["coins"]["XRPUSDT"]
    assert "error" not in report["coins"]["BTCUSDT"]
    assert "error" not in report["coins"]["SOLUSDT"]
    assert report["coins"]["BTCUSDT"]["lane_base"] == "0"  # the healthy coins still ran
