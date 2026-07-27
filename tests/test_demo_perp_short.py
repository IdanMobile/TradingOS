"""Offline tests for the DEFAULT-DISABLED perp short side. No network, no keys, no venue.

Every venue interaction is a stubbed transport. What each test proves is named in its docstring;
the safety-critical ones are the refusals (unverified leverage / cross margin / hedge mode), the
"never unprotected" close, the single shared cap across both sides, and the ledger isolation that
keeps perp funding out of the spot round-trip report.
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

import scripts.demo_activity_lane as act  # noqa: E402
import scripts.demo_eth_lane as lane  # noqa: E402
import scripts.demo_perp_short as perp  # noqa: E402

START = datetime(2026, 7, 1, tzinfo=UTC)
OLD_CURSOR = "2020-01-01T00:00:00+00:00"

BULL: list[tuple[str, str]] = [(str(100 + i), "10") for i in range(59)] + [("159", "1000")]
BEAR: list[tuple[str, str]] = [(str(200 - i), "10") for i in range(60)]
FLAT: list[tuple[str, str]] = [("100", "10")] * 60


def _kline_rows(closes: list[tuple[str, str]]) -> list[list[str]]:
    rows = []
    for index, (close, volume) in enumerate(closes):
        open_ms = int((START + timedelta(hours=index)).timestamp() * 1000)
        rows.append([str(open_ms), "100", close, "90", close, volume, "0"])
    forming_ms = int((START + timedelta(hours=len(closes))).timestamp() * 1000)
    rows.append([str(forming_ms), "100", "100", "90", "100", "1", "0"])
    return rows


class Venue:
    """Spot + linear stand-in. Records every POST body so refusals can be proven by absence."""

    def __init__(
        self,
        closes: dict[str, list[tuple[str, str]]] | None = None,
        *,
        marks: dict[str, str] | None = None,
        position_overrides: dict[str, dict[str, Any]] | None = None,
        hedge_mode: bool = False,
        empty_positions: bool = False,
        stop_fails: bool = False,
        isolated_fails: bool = False,
        cover_fails: bool = False,
        fail_perp_get: str | None = None,
    ) -> None:
        self.closes = closes or {}
        self.marks = marks or {}
        self.hedge_mode = hedge_mode
        self.empty_positions = empty_positions
        self.stop_fails = stop_fails
        self.isolated_fails = isolated_fails
        # The venue rejects the reduce-only CLOSE and leaves the short open — the case the local
        # state file must not mistake for "flat".
        self.cover_fails = cover_fails
        self.fail_perp_get = fail_perp_get
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.balances: dict[str, Decimal] = {"USDT": Decimal("100000")}
        self.stop_ids: set[str] = set()
        self.positions: dict[str, dict[str, Any]] = {}
        self.position_overrides = position_overrides or {}

    # --- helpers ---------------------------------------------------------------------------
    @staticmethod
    def _q(url: str, key: str) -> str:
        return parse_qs(urlsplit(url).query).get(key, [""])[0]

    def _position(self, symbol: str) -> dict[str, Any]:
        base = {
            "symbol": symbol,
            "positionIdx": "0",
            "size": "0",
            "side": "",
            "avgPrice": "0",
            "leverage": "1",
            "tradeMode": "1",
            "stopLoss": "",
        }
        base.update(self.positions.get(symbol, {}))
        base.update(self.position_overrides.get(symbol, {}))
        return base

    # --- transports ------------------------------------------------------------------------
    def get(self, url: str, headers: dict[str, str]) -> bytes:
        symbol = self._q(url, "symbol")
        linear = self._q(url, "category") == "linear" or "/v5/position/list" in url
        if linear and self.fail_perp_get == symbol:
            raise RuntimeError(f"perp read unavailable for {symbol}")
        if "/v5/position/list" in url:
            if self.empty_positions:
                rows: list[dict[str, Any]] = []
            elif self.hedge_mode:
                rows = [
                    {**self._position(symbol), "positionIdx": "1"},
                    {**self._position(symbol), "positionIdx": "2"},
                ]
            else:
                rows = [self._position(symbol)]
            return json.dumps({"retCode": 0, "result": {"list": rows}}).encode()
        if "/v5/market/kline" in url:
            rows_k = list(reversed(_kline_rows(self.closes.get(symbol, FLAT))))
            return json.dumps({"result": {"list": rows_k}}).encode()
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
                                "lotSizeFilter": {
                                    "basePrecision": "0.00001",
                                    "qtyStep": "0.001",
                                    "minOrderQty": "0.001",
                                },
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
            order_id = self._q(url, "orderId")
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
        path = urlsplit(url).path
        payload = json.loads(body)
        self.posts.append((path, payload))
        symbol = str(payload.get("symbol", ""))
        if path == "/v5/position/switch-isolated":
            if self.isolated_fails:
                return json.dumps({"retCode": 110027, "retMsg": "not supported"}).encode()
            self.positions.setdefault(symbol, {})["tradeMode"] = "1"
            return json.dumps({"retCode": 0}).encode()
        if path == "/v5/position/set-leverage":
            self.positions.setdefault(symbol, {})["leverage"] = str(payload["buyLeverage"])
            return json.dumps({"retCode": 0}).encode()
        if path == "/v5/position/trading-stop":
            if self.stop_fails:
                return json.dumps({"retCode": 10001, "retMsg": "stop rejected"}).encode()
            self.positions.setdefault(symbol, {})["stopLoss"] = str(payload["stopLoss"])
            return json.dumps({"retCode": 0}).encode()
        assert path == "/v5/order/create"
        order_id = f"OID-{len(self.posts)}"
        if payload.get("category") == "linear":
            mark = Decimal(self.marks.get(symbol, "100"))
            if payload["side"] == "Sell":
                self.positions.setdefault(symbol, {}).update(
                    {"size": str(payload["qty"]), "side": "Sell", "avgPrice": str(mark)}
                )
            elif self.cover_fails:
                # Rejected close: the position stays OPEN on the venue.
                return json.dumps({"retCode": 110017, "retMsg": "reduce-only rejected"}).encode()
            else:
                self.positions.setdefault(symbol, {}).update(
                    {"size": "0", "side": "", "avgPrice": "0", "stopLoss": ""}
                )
            return json.dumps({"retCode": 0, "result": {"orderId": order_id}}).encode()
        base = symbol.removesuffix("USDT")
        self.balances.setdefault(base, Decimal("0"))
        if payload.get("orderFilter") == "StopOrder":
            self.stop_ids.add(order_id)
        elif payload["side"] == "Buy":
            self.balances["USDT"] -= Decimal("25")
            self.balances[base] += Decimal("0.01")
        else:
            self.balances[base] -= Decimal("0.01")
            self.balances["USDT"] += Decimal("1")
        return json.dumps({"retCode": 0, "result": {"orderId": order_id}}).encode()

    # --- assertions helpers ----------------------------------------------------------------
    def bodies(self, path: str) -> list[dict[str, Any]]:
        return [payload for post_path, payload in self.posts if post_path == path]

    def perp_orders(self) -> list[dict[str, Any]]:
        return [o for o in self.bodies("/v5/order/create") if o.get("category") == "linear"]

    def spot_orders(self) -> list[dict[str, Any]]:
        return [o for o in self.bodies("/v5/order/create") if o.get("category") == "spot"]


@pytest.fixture(autouse=True)
def _fresh_warn_set() -> Any:
    act._NO_DATA_WARNED.clear()
    yield
    act._NO_DATA_WARNED.clear()


@pytest.fixture()
def lane_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(lane, "LANE_DIR", tmp_path)
    monkeypatch.setattr(lane, "KILL_SWITCH", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(lane, "ORDERS_LEDGER", tmp_path / "orders.jsonl")
    monkeypatch.setattr(lane, "ACTIONS_LEDGER", tmp_path / "demo_lane_actions.jsonl")
    monkeypatch.setattr(lane, "LANE_STATE", tmp_path / "lane_state.json")
    monkeypatch.setattr(lane, "HEARTBEAT", tmp_path / "heartbeat.json")
    return tmp_path


def _cycle(venue: Venue, symbols: list[str], **kw: Any) -> dict[str, Any]:
    return act.run_activity_cycle(
        "k",
        "s",
        symbols=symbols,
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        **kw,
    )


def _short(venue: Venue, symbol: str, decision: str | None, **kw: Any) -> dict[str, Any]:
    kw.setdefault("long_open", False)
    kw.setdefault("entry_notional_budget", None)
    kw.setdefault("signal_ref", "TEST")
    return perp.run_short_cycle(
        symbol,
        decision,
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        **kw,
    )


def _arm(symbol: str) -> None:
    perp.write_short_state(symbol, {"armed": True, "short_size": "0"})


# --- DEFAULT OFF ---------------------------------------------------------------------------


def test_shorts_are_off_by_default() -> None:
    """The master switch ships False, and both public entry points default to it."""
    assert perp.SHORTS_ENABLED is False
    assert act.run_activity_cycle.__defaults__ is None  # keyword-only; read the annotations instead
    assert act.run_activity_cycle.__kwdefaults__["shorts"] is False
    assert act.run_activity_lane.__kwdefaults__["shorts"] is False


def test_default_cycle_never_touches_the_perp_path(lane_dirs: Path) -> None:
    """Shorts off: a maximally bearish coin produces ZERO perp calls, state, or ledger lines."""
    venue = Venue(closes={"BTCUSDT": BEAR})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT"])

    assert report["shorts_enabled"] is False
    assert venue.perp_orders() == []
    assert venue.bodies("/v5/position/set-leverage") == []
    assert venue.bodies("/v5/position/switch-isolated") == []
    assert not perp.perp_ledger_path().exists()
    assert not (lane_dirs / "lane_state_BTCUSDT_activity_short.json").exists()


# --- SYMMETRIC HYSTERESIS ------------------------------------------------------------------


def test_short_hysteresis_mirrors_the_long_side_exactly() -> None:
    """SHORT at <= -ENTRY, COVER at >= -EXIT, hold in between — derived from the same constants."""
    assert act.short_decision(-act.ENTRY_THRESHOLD) == "SHORT"
    assert act.short_decision(-act.ENTRY_THRESHOLD - Decimal("0.5")) == "SHORT"
    assert act.short_decision(-act.ENTRY_THRESHOLD + Decimal("0.01")) is None
    assert act.short_decision(-(act.ENTRY_THRESHOLD + act.EXIT_THRESHOLD) / 2) is None
    assert act.short_decision(-act.EXIT_THRESHOLD) == "COVER"
    assert act.short_decision(Decimal("0.4")) == "COVER"
    # Mirror property over the whole band: short(x) is the long decision at -x, renamed.
    for raw in ("-1", "-0.3", "-0.15", "-0.1", "0", "0.05", "0.2", "1"):
        score = Decimal(raw)
        mapped = {"BUY": "SHORT", "SELL": "COVER", None: None}[act.confluence_decision(-score)]
        assert act.short_decision(score) == mapped


def test_short_disaster_stop_fires_ABOVE_entry() -> None:
    """The -15% long stop mirrored: a short is stopped when price RISES 15% through entry."""
    entry = Decimal("100")
    assert perp.short_stop_price(entry) == Decimal("115.00")
    assert perp.short_stop_triggered(entry, Decimal("115"))
    assert perp.short_stop_triggered(entry, Decimal("120"))
    assert not perp.short_stop_triggered(entry, Decimal("114.99"))
    assert not perp.short_stop_triggered(entry, Decimal("85"))  # a WINNING short never stops out
    # Same single constant drives both sides, so they cannot drift.
    assert perp.short_stop_price(entry) - entry == entry - lane.disaster_stop_price(entry)
    # Quantization tightens (rounds DOWN) for a short — the mirror of the long's round-up.
    assert perp.quantize_short_stop_price(Decimal("115.567"), Decimal("0.01")) == Decimal("115.56")


def test_short_size_is_base_coin_and_refuses_below_the_venue_minimum() -> None:
    """Linear qty is BASE COIN (no spot `marketUnit`), quantized DOWN, never rounded up to fit."""
    size = perp.short_size_for(Decimal("25"), Decimal("100"), Decimal("0.001"), Decimal("0.001"))
    assert size == Decimal("0.250")
    with pytest.raises(lane.LocalRejection, match="below the venue minimum"):
        perp.short_size_for(Decimal("25"), Decimal("100000"), Decimal("1"), Decimal("1"))
    with pytest.raises(lane.LocalRejection, match="must be finite and positive"):
        perp.short_size_for(Decimal("25"), Decimal("0"), Decimal("0.001"), Decimal("0.001"))


# --- VERIFICATION: leverage / margin mode / position mode ------------------------------------


def test_required_leverage_is_explicitly_set_and_read_back(lane_dirs: Path) -> None:
    """The required multiple is REQUESTED then CONFIRMED from the row before any order is sent."""
    venue = Venue(marks={"BTCUSDT": "100"})
    want = str(perp.REQUIRED_LEVERAGE)
    ok, detail = perp.verify_symbol(
        "BTCUSDT", "k", "s", get_transport=venue.get, post_transport=venue.post
    )
    assert ok and detail["leverage"] == want and detail["tradeMode"] == "1"
    leverage_bodies = venue.bodies("/v5/position/set-leverage")
    assert leverage_bodies == [
        {"category": "linear", "symbol": "BTCUSDT", "buyLeverage": want, "sellLeverage": want}
    ]
    assert venue.bodies("/v5/position/switch-isolated")[0]["tradeMode"] == 1


@pytest.mark.parametrize(
    ("kwargs", "refusal"),
    [
        ({"position_overrides": {"BTCUSDT": {"leverage": "25"}}}, "leverage_not_required_multiple"),
        ({"position_overrides": {"BTCUSDT": {"tradeMode": "0"}}}, "margin_not_isolated"),
        ({"empty_positions": True}, "no_one_way_position_row"),
        ({"hedge_mode": True}, "no_one_way_position_row"),
        ({"isolated_fails": True}, "switch_isolated"),
        ({"fail_perp_get": "BTCUSDT"}, "position_read"),
    ],
)
def test_unverifiable_settings_refuse_the_symbol_without_ordering(
    lane_dirs: Path, kwargs: dict[str, Any], refusal: str
) -> None:
    """Wrong leverage, cross margin, hedge mode, missing row, unreadable venue => NO perp order."""
    venue = Venue(marks={"BTCUSDT": "100"}, **kwargs)
    record = perp.open_short(
        "BTCUSDT",
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        signal_ref="TEST",
    )
    assert record["ok"] is False and record["stage"] == "refused_unverified"
    assert record["detail"]["refused"] == refusal
    assert venue.perp_orders() == []  # nothing was ever sent to the venue


# --- NEVER UNPROTECTED ----------------------------------------------------------------------


def test_short_entry_attaches_and_confirms_a_venue_stop_above_entry(lane_dirs: Path) -> None:
    """A successful short is protected the moment it exists, at the mirrored +15% level."""
    venue = Venue(marks={"BTCUSDT": "100"})
    record = perp.open_short(
        "BTCUSDT",
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        signal_ref="TEST",
    )
    assert record["ok"] is True and record["stage"] == "done"
    assert record["side"] == "Sell" and record["reduce_only"] is False
    assert Decimal(record["stop_price"]) == Decimal("115")
    assert Decimal(record["stop_price"]) > Decimal(record["entry_price"])
    stop_bodies = venue.bodies("/v5/position/trading-stop")
    assert stop_bodies == [
        {
            "category": "linear",
            "symbol": "BTCUSDT",
            "stopLoss": "115.00",
            "tpslMode": "Full",
            "positionIdx": 0,
        }
    ]
    assert venue.positions["BTCUSDT"]["stopLoss"] == "115.00"


def test_failed_protective_stop_closes_the_position_immediately(lane_dirs: Path) -> None:
    """If the stop cannot be confirmed the short is closed at once — never left unprotected."""
    venue = Venue(marks={"BTCUSDT": "100"}, stop_fails=True)
    record = perp.open_short(
        "BTCUSDT",
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        signal_ref="TEST",
    )
    assert record["ok"] is False and record["stage"] == "closed_unprotected"
    orders = venue.perp_orders()
    assert [o["side"] for o in orders] == ["Sell", "Buy"]
    assert orders[1]["reduceOnly"] is True
    assert venue.positions["BTCUSDT"]["size"] == "0"


def test_every_cycle_closes_an_open_short_that_cannot_be_protected(lane_dirs: Path) -> None:
    """The sweep is unconditional: a pre-existing unprotected short closes even with no signal."""
    venue = Venue(marks={"BTCUSDT": "100"}, stop_fails=True)
    venue.positions["BTCUSDT"] = {"size": "0.25", "side": "Sell", "avgPrice": "100", "stopLoss": ""}
    _arm("BTCUSDT")
    report = _short(venue, "BTCUSDT", None)
    assert report["stage"] == "closed_unprotected"
    assert venue.perp_orders()[0]["reduceOnly"] is True
    assert venue.positions["BTCUSDT"]["size"] == "0"


def test_open_short_reattaches_a_missing_stop_without_closing(lane_dirs: Path) -> None:
    """A recoverable missing stop is re-attached; the position survives because it is protected."""
    venue = Venue(marks={"BTCUSDT": "100"})
    venue.positions["BTCUSDT"] = {"size": "0.25", "side": "Sell", "avgPrice": "100", "stopLoss": ""}
    _arm("BTCUSDT")
    report = _short(venue, "BTCUSDT", None)
    assert report["stage"] == "hold" and report["stop_price"] == "115.00"
    assert venue.positions["BTCUSDT"]["stopLoss"] == "115.00"
    assert venue.perp_orders() == []  # nothing was closed


def test_local_disaster_stop_closes_a_short_that_ran_15_percent_against_it(
    lane_dirs: Path,
) -> None:
    """The local mirrored guard fires on mark >= entry*1.15, backing up the venue stop."""
    venue = Venue(marks={"BTCUSDT": "116"})
    venue.positions["BTCUSDT"] = {
        "size": "0.25",
        "side": "Sell",
        "avgPrice": "100",
        "stopLoss": "115.00",
    }
    _arm("BTCUSDT")
    report = _short(venue, "BTCUSDT", None)
    assert report["stage"] == "disaster_stop"
    assert report["action"]["reason"] == "DISASTER_STOP_SHORT"
    assert venue.perp_orders()[0] == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Market",
        "qty": "0.25",
        "reduceOnly": True,
        "positionIdx": 0,
    }


# --- COVER ----------------------------------------------------------------------------------


def test_cover_is_always_reduce_only(lane_dirs: Path) -> None:
    """A cover can only ever shrink the short — it can never open a reverse long."""
    venue = Venue(marks={"BTCUSDT": "95"})
    venue.positions["BTCUSDT"] = {
        "size": "0.25",
        "side": "Sell",
        "avgPrice": "100",
        "stopLoss": "115.00",
    }
    _arm("BTCUSDT")
    report = _short(venue, "BTCUSDT", "COVER")
    assert report["stage"] == "cover"
    order = venue.perp_orders()[0]
    assert order["side"] == "Buy" and order["reduceOnly"] is True
    assert perp.short_open("BTCUSDT") is False


def test_first_sight_of_a_coin_arms_without_trading(lane_dirs: Path) -> None:
    """Prospective discipline, mirroring the long lane's cursor arming."""
    venue = Venue(marks={"BTCUSDT": "100"})
    assert _short(venue, "BTCUSDT", "SHORT")["stage"] == "armed"
    assert venue.perp_orders() == []
    assert _short(venue, "BTCUSDT", "SHORT")["stage"] == "short_entry"


# --- NEVER BOTH SIDES AT ONCE ----------------------------------------------------------------


def test_a_short_is_never_opened_while_that_coin_is_long(lane_dirs: Path) -> None:
    venue = Venue(marks={"BTCUSDT": "100"})
    _arm("BTCUSDT")
    report = _short(venue, "BTCUSDT", "SHORT", long_open=True)
    assert report["stage"] == "skipped_long_open"
    assert venue.perp_orders() == []


def test_a_long_is_never_opened_while_that_coin_is_short(lane_dirs: Path) -> None:
    """A bullish score covers the short this cycle and withholds the long entry until it is gone."""
    venue = Venue(closes={"BTCUSDT": BULL}, marks={"BTCUSDT": "100"})
    venue.positions["BTCUSDT"] = {
        "size": "0.25",
        "side": "Sell",
        "avgPrice": "100",
        "stopLoss": "115.00",
    }
    perp.write_short_state("BTCUSDT", {"armed": True, "short_size": "0.25"})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT"], shorts=True)

    assert report["coins"]["BTCUSDT"]["decision"] == "BUY"  # the signal said buy...
    assert venue.spot_orders() == []  # ...but no long was opened while short
    assert report["coins"]["BTCUSDT"]["short"]["stage"] == "cover"
    assert venue.perp_orders()[0]["reduceOnly"] is True


# --- SHARED CAP ------------------------------------------------------------------------------


def test_one_cap_covers_long_and_short_combined(lane_dirs: Path) -> None:
    """An open LONG consumes the shared budget, so a bearish coin's SHORT is skipped, not funded."""
    venue = Venue(closes={"BTCUSDT": FLAT, "SOLUSDT": BEAR}, marks={"SOLUSDT": "100"})
    lane.write_state(
        {"lane_base": "0.01", "cursor": OLD_CURSOR, "entry_price": "100", "resting_stop": None},
        "BTCUSDT_activity",
    )
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "SOLUSDT_activity",
    )
    _arm("SOLUSDT")
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT"], shorts=True, total_cap=Decimal("25"))

    assert report["coins"]["SOLUSDT"]["short"]["stage"] == "skipped_cap"
    assert venue.perp_orders() == []
    # The same cap arithmetic counts an open SHORT against a would-be LONG too: one open long plus
    # one open short is 50 of the shared budget, not 25 against each of two separate budgets.
    lane.write_state(
        {"lane_base": "0.01", "cursor": OLD_CURSOR, "entry_price": "100", "resting_stop": None},
        "BTCUSDT_activity",
    )
    perp.write_short_state("SOLUSDT", {"armed": True, "short_size": "0.25"})
    assert act.activity_open_exposure(["BTCUSDT", "SOLUSDT"], shorts=True) == Decimal("50")
    assert act.activity_open_exposure(["BTCUSDT", "SOLUSDT"]) == Decimal("25")  # long-only default


def test_short_entry_consumes_the_budget_so_two_coins_cannot_both_short(lane_dirs: Path) -> None:
    venue = Venue(
        closes={"BTCUSDT": BEAR, "SOLUSDT": BEAR}, marks={"BTCUSDT": "100", "SOLUSDT": "100"}
    )
    for symbol in ("BTCUSDT", "SOLUSDT"):
        lane.write_state(
            {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
            f"{symbol}_activity",
        )
        _arm(symbol)
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT"], shorts=True, total_cap=Decimal("25"))

    assert report["coins"]["BTCUSDT"]["short"]["stage"] == "short_entry"
    assert report["coins"]["SOLUSDT"]["short"]["stage"] == "skipped_cap"
    assert len([o for o in venue.perp_orders() if o["side"] == "Sell"]) == 1


# --- KILL SWITCH AND FAILURE ISOLATION --------------------------------------------------------


def test_kill_switch_halts_both_sides(lane_dirs: Path) -> None:
    (lane_dirs / "KILL_SWITCH").write_text("stop")
    venue = Venue(closes={"BTCUSDT": BEAR}, marks={"BTCUSDT": "100"})
    _arm("BTCUSDT")
    report = _cycle(venue, ["BTCUSDT"], shorts=True)
    assert report["kill_switch"] is True
    assert venue.posts == []

    # And directly: the order path itself refuses while the switch is set.
    record = perp.open_short(
        "BTCUSDT",
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        signal_ref="TEST",
    )
    assert record["ok"] is False and record["stage"] == "kill_switch"
    assert venue.posts == []


def test_one_coins_short_failure_never_affects_another_coin(lane_dirs: Path) -> None:
    venue = Venue(
        closes={"BTCUSDT": BEAR, "SOLUSDT": BEAR},
        marks={"BTCUSDT": "100", "SOLUSDT": "100"},
        fail_perp_get="BTCUSDT",
    )
    for symbol in ("BTCUSDT", "SOLUSDT"):
        lane.write_state(
            {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
            f"{symbol}_activity",
        )
        _arm(symbol)
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT"], shorts=True)

    assert "error" in report["coins"]["BTCUSDT"]["short"]
    assert report["coins"]["BTCUSDT"]["confidence"]  # its LONG result survived intact
    assert report["coins"]["SOLUSDT"]["short"]["stage"] == "short_entry"


# --- FUNDING / LEDGER ISOLATION ---------------------------------------------------------------


def test_perp_records_never_enter_the_spot_round_trip_ledger(lane_dirs: Path) -> None:
    """Funding containment: `report_demo_trades` folds orders.jsonl, which perps never touch.

    A perp fill does not move the wallet by its notional and funding moves it with no order at all,
    so a perp record in the spot ledger would corrupt every round trip's P&L. They live in a
    separate append-only file and are explicitly labelled as not wallet-delta attributable.
    """
    venue = Venue(closes={"BTCUSDT": BEAR}, marks={"BTCUSDT": "100"})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    _arm("BTCUSDT")
    _cycle(venue, ["BTCUSDT"], shorts=True)

    perp_records = [
        json.loads(line) for line in perp.perp_ledger_path().read_text().splitlines() if line
    ]
    assert perp_records and all(r["category"] == "linear" for r in perp_records)
    assert all(r["wallet_delta_attributable"] is False for r in perp_records)
    assert all("reconcile" not in r for r in perp_records)
    assert all(r["strategy"] == perp.SHORT_STRATEGY for r in perp_records)
    assert all(r["real_money"] is False for r in perp_records)

    spot_ledger = lane_dirs / "orders.jsonl"
    spot_records = (
        [json.loads(line) for line in spot_ledger.read_text().splitlines() if line]
        if spot_ledger.exists()
        else []
    )
    assert all(r.get("category") != "linear" for r in spot_records)
    assert all(r.get("strategy") != perp.SHORT_STRATEGY for r in spot_records)
    assert perp.perp_ledger_path() != lane.ORDERS_LEDGER


def test_a_failed_cover_leaves_the_state_short_so_the_long_stays_blocked(lane_dirs: Path) -> None:
    """A REJECTED close must not zero the local short state.

    Zeroing unconditionally was a real defect. Two things read that state file, and both would
    have been wrong in the dangerous direction: `activity_open_exposure` would under-count the
    shared $300 cap, and the long/short mutual-exclusion gate (`short_open`) would stop withholding
    the spot BUY — so a real long could open against a short that is still live on the venue.
    """
    venue = Venue(marks={"BTCUSDT": "95"}, cover_fails=True)
    venue.positions["BTCUSDT"] = {
        "size": "0.25",
        "side": "Sell",
        "avgPrice": "100",
        "stopLoss": "115.00",
    }
    _arm("BTCUSDT")
    perp.write_short_state("BTCUSDT", {"armed": True, "short_size": "0.25", "entry_price": "100"})
    report = _short(venue, "BTCUSDT", "COVER")

    assert report["stage"] == "cover"
    assert report["action"].get("ok") is not True, "the venue rejected this close"
    # The venue still holds the short...
    assert venue.positions["BTCUSDT"]["size"] == "0.25"
    # ...so the state file must still say short, which keeps BOTH consumers correct.
    assert perp.short_open("BTCUSDT") is True, "a failed close must not read as flat"
    assert perp.short_exposure(["BTCUSDT"]) > 0, "the cap must still count this slot"


def test_a_confirmed_cover_does_zero_the_state(lane_dirs: Path) -> None:
    """The mirror of the test above: a close the venue CONFIRMS does release the slot."""
    venue = Venue(marks={"BTCUSDT": "95"})
    venue.positions["BTCUSDT"] = {
        "size": "0.25",
        "side": "Sell",
        "avgPrice": "100",
        "stopLoss": "115.00",
    }
    _arm("BTCUSDT")
    perp.write_short_state("BTCUSDT", {"armed": True, "short_size": "0.25", "entry_price": "100"})
    report = _short(venue, "BTCUSDT", "COVER")
    assert report["action"].get("ok") is True
    assert perp.short_open("BTCUSDT") is False
    assert perp.short_exposure(["BTCUSDT"]) == 0


def test_leverage_can_never_put_liquidation_inside_the_disaster_stop() -> None:
    """The import-time invariant that makes an unsafe leverage unshippable.

    At 25x liquidation sits ~3.5% away while the disaster stop is at 15% — the stop could never
    fire and the exchange would decide every exit instead. This is arithmetic, not preference, so
    it is enforced at import rather than left as a comment for someone to override later.
    """
    liquidation = (Decimal("1") / perp.REQUIRED_LEVERAGE) - perp.MAINTENANCE_MARGIN_RATE
    stop = lane.DEMO_DISASTER_STOP_PCT
    assert liquidation > stop * perp.STOP_LIQUIDATION_BUFFER, "stop must fire before liquidation"
    assert perp.REQUIRED_LEVERAGE <= Decimal("5"), "5x is the ceiling this invariant permits"
    # And the notional/margin split is real: $25 of margin controls 5x that in coin.
    assert perp.SHORT_NOTIONAL_USDT == perp.SHORT_MARGIN_USDT * perp.REQUIRED_LEVERAGE
    # The shared cap still counts MARGIN, so 12 slots still means 12 positions.
    assert perp.SHORT_QUOTE_USDT == perp.SHORT_MARGIN_USDT
