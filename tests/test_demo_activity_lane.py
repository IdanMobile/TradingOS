"""Offline tests for the multi-timeframe confluence activity lane. No network, no keys.

Proves the FOUNDATION (interval-parameterized bar fetch, the roster's deterministic latest-bar
signals) and the CONFLUENCE decision layer (weighted score, hysteresis) and that the scored engine
composes exactly the demo lane's safety machinery: SHARED kill switch (halts all), SHARED total
cap (gates only new entries, never risk reduction), per-coin disaster stop priced off that coin's
own entry, one coin's failure never aborting the others, and every order attributed to the engine.
Demo/fake money, execution-measurement only.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from socket import gaierror
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_activity_lane as act  # noqa: E402
import scripts.demo_eth_lane as lane  # noqa: E402
import scripts.demo_preflight as pf  # noqa: E402
from tios.trading_domain import Timeframe  # noqa: E402

START = datetime(2026, 7, 1, tzinfo=UTC)
OLD_CURSOR = "2020-01-01T00:00:00+00:00"  # older than any bar -> a fresh signal fires
FUTURE_CURSOR = "2999-01-01T00:00:00+00:00"  # newer than any bar -> no fresh signal fires

# A rising trend that ends on a new high with a volume surge: donchian/MA-cross/volume-breakout all
# fire BUY, so the confluence score clears the ENTRY threshold on every timeframe.
BULL: list[tuple[str, str]] = [(str(100 + i), "10") for i in range(59)] + [("159", "1000")]
FLAT: list[tuple[str, str]] = [("100", "10")] * 60


def _kline_rows(closes: list[tuple[str, str]]) -> list[list[str]]:
    """(close, volume) pairs -> Bybit kline rows oldest-first, plus a forming dummy bar."""
    rows = []
    for index, (close, volume) in enumerate(closes):
        open_ms = int((START + timedelta(hours=index)).timestamp() * 1000)
        rows.append([str(open_ms), "100", close, "90", close, volume, "0"])
    forming_ms = int((START + timedelta(hours=len(closes))).timestamp() * 1000)
    rows.append([str(forming_ms), "100", "100", "90", "100", "1", "0"])
    return rows


class ActivityVenue:
    """URL-dispatching GET/POST stand-in serving per-symbol klines (same series each interval)."""

    def __init__(
        self,
        closes: dict[str, list[tuple[str, str]]] | None = None,
        marks: dict[str, str] | None = None,
        fail_kline: str | None = None,
        transport_down: bool = False,
    ) -> None:
        self.closes = closes if closes is not None else {}
        self.marks = marks or {}
        self.fail_kline = fail_kline
        # `transport_down` reproduces the observed laptop-sleep DNS loss: EVERY request raises the
        # real urllib error (a socket.gaierror wrapped in URLError -> an OSError subclass).
        self.transport_down = transport_down
        self.orders: list[dict[str, Any]] = []
        self.kline_urls: list[str] = []
        self.balances: dict[str, Decimal] = {"USDT": Decimal("100000")}
        self.stop_ids: set[str] = set()

    @staticmethod
    def _symbol(url: str) -> str:
        return parse_qs(urlsplit(url).query).get("symbol", [""])[0]

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        symbol = self._symbol(url)
        if self.transport_down:
            raise URLError(gaierror(8, "nodename nor servname provided, or not known"))
        if "/v5/market/kline" in url:
            self.kline_urls.append(url)
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


@pytest.fixture(autouse=True)
def _fresh_warn_set() -> Any:
    """`warn once per RUN` is module state — every test starts from a clean run."""
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


def _cycle(venue: ActivityVenue, symbols: list[str], **kw: Any) -> dict[str, Any]:
    return act.run_activity_cycle(
        "k",
        "s",
        symbols=symbols,
        get_transport=venue.get,
        post_transport=venue.post,
        sleep=lambda _s: None,
        **kw,
    )


# --- FOUNDATION: interval-parameterized bar fetch ------------------------------------------------
def test_interval_defaults_to_1h_byte_identical() -> None:
    venue = ActivityVenue(closes={"ETHUSDT": FLAT})
    bars = lane.fetch_closed_bars(venue.get, symbol="ETHUSDT")  # no interval -> today's behavior
    assert "interval=60" in venue.kline_urls[-1]
    assert bars[-1].close_time - bars[-1].open_time == timedelta(hours=1)
    assert bars[-1].market.timeframe is Timeframe.H1
    assert "-1H-LIVE" in str(bars[-1].market.dataset_ref)


@pytest.mark.parametrize(
    ("interval", "minutes", "timeframe", "label"),
    [
        ("5", 5, Timeframe.M5, "-5M-LIVE"),
        ("15", 15, Timeframe.M15, "-15M-LIVE"),
        ("240", 240, Timeframe.H4, "-4H-LIVE"),
    ],
)
def test_nondefault_interval_routes_the_right_kline_request(
    interval: str, minutes: int, timeframe: Timeframe, label: str
) -> None:
    venue = ActivityVenue(closes={"BTCUSDT": FLAT})
    bars = lane.fetch_closed_bars(venue.get, symbol="BTCUSDT", interval=interval)
    assert f"interval={interval}" in venue.kline_urls[-1]
    assert bars[-1].close_time - bars[-1].open_time == timedelta(minutes=minutes)
    assert bars[-1].market.timeframe is timeframe
    assert label in str(bars[-1].market.dataset_ref)


def test_unsupported_interval_fails_closed() -> None:
    venue = ActivityVenue()
    with pytest.raises(ValueError, match="unsupported kline interval"):
        lane.fetch_closed_bars(venue.get, symbol="BTCUSDT", interval="7")


# --- FOUNDATION: each roster strategy's latest-bar signal is deterministic ------------------------
def test_signal_on_latest_known_answers() -> None:
    roster = dict(act.ROSTER)
    bull = act.candles_from_bars(lane.fetch_closed_bars(ActivityVenue({"X": BULL}).get, symbol="X"))
    # breakout, MA cross, and volume-breakout all fire BUY on the rising/surging series.
    assert act.signal_on_latest(roster["EXT-DONCHIAN-40"], bull) == "BUY"
    assert act.signal_on_latest(roster["EXT-SMA-10-30"], bull) == "BUY"
    assert act.signal_on_latest(roster["EXT-EMA-12-26"], bull) == "BUY"
    assert act.signal_on_latest(roster["SIG-VOLUME-BREAKOUT"], bull) == "BUY"

    falling = [(str(200 - i), "10") for i in range(60)]
    bear = act.candles_from_bars(
        lane.fetch_closed_bars(ActivityVenue({"X": falling}).get, symbol="X")
    )
    assert act.signal_on_latest(roster["EXT-SMA-10-30"], bear) == "SELL"
    assert act.signal_on_latest(roster["EXT-EMA-12-26"], bear) == "SELL"


# --- CONFLUENCE: weighted score and hysteresis ---------------------------------------------------
def test_confluence_score_normalizes_and_weights_higher_timeframes() -> None:
    weights = {"15m": Decimal("1"), "1h": Decimal("2"), "4h": Decimal("3")}
    unanimous = {"15m": [("S", "BUY")], "1h": [("S", "BUY")], "4h": [("S", "BUY")]}
    score, ctx = act.confluence_score(unanimous, weights)
    assert score == Decimal("1")  # all bullish -> +1
    assert len(ctx["bullish"]) == 3 and ctx["bearish"] == []

    # A single 4h BUY outweighs a single 15m SELL -> net positive (higher timeframe dominates).
    hi_bull = {"15m": [("S", "SELL")], "4h": [("S", "BUY")]}
    assert act.confluence_score(hi_bull, weights)[0] == Decimal("0.5")
    hi_bear = {"15m": [("S", "BUY")], "4h": [("S", "SELL")]}
    assert act.confluence_score(hi_bear, weights)[0] == Decimal("-0.5")


def test_confluence_decision_uses_entry_exit_hysteresis() -> None:
    assert act.confluence_decision(act.ENTRY_THRESHOLD) == "BUY"  # at/above ENTRY enters
    assert act.confluence_decision(act.ENTRY_THRESHOLD - Decimal("0.01")) is None  # band -> hold
    assert act.confluence_decision((act.ENTRY_THRESHOLD + act.EXIT_THRESHOLD) / 2) is None
    assert act.confluence_decision(act.EXIT_THRESHOLD) == "SELL"  # at/below EXIT exits
    assert act.confluence_decision(Decimal("-0.4")) == "SELL"


# --- INTEGRATION: run_activity_cycle drives the demo machinery ------------------------------------
def test_bullish_confluence_enters_one_long_attributed_to_the_engine(lane_dirs: Path) -> None:
    venue = ActivityVenue(closes={"BTCUSDT": BULL})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT"])

    buys = [o for o in venue.orders if o["side"] == "Buy"]
    assert len(buys) == 1 and buys[0]["symbol"] == "BTCUSDT"
    assert Decimal(report["coins"]["BTCUSDT"]["confidence"]) >= act.ENTRY_THRESHOLD
    assert report["coins"]["BTCUSDT"]["decision"] == "BUY"
    # ONE position per coin: its own state + heartbeat file, keyed by the activity discriminator.
    assert (lane_dirs / "lane_state_BTCUSDT_activity.json").is_file()
    assert (lane_dirs / "heartbeat_BTCUSDT_activity.json").is_file()
    assert not (lane_dirs / "lane_state.json").is_file()  # ETH single-lane state untouched
    # Every order carries symbol + strategy + the confidence score (via signal_ref).
    records = [json.loads(x) for x in (lane_dirs / "orders.jsonl").read_text().splitlines()]
    entry = next(r for r in records if r.get("reason") == "ENTRY_LONG")
    assert entry["symbol"] == "BTCUSDT"
    assert entry["strategy"] == act.ACTIVITY_STRATEGY
    assert entry["signal_ref"].startswith("ACT-CONF:")
    assert entry["real_money"] is False and entry["promotion_eligible"] is False


def test_shared_kill_switch_halts_all_coins(lane_dirs: Path) -> None:
    (lane_dirs / "KILL_SWITCH").write_text("stop")
    venue = ActivityVenue(closes={"BTCUSDT": BULL, "SOLUSDT": BULL})
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT", "XRPUSDT"])
    assert report["kill_switch"] is True
    assert venue.orders == [] and venue.kline_urls == []  # nothing fetched or traded
    assert all(c["stage"] == "kill_switch" for c in report["coins"].values())


def test_shared_cap_blocks_new_entry_while_open_coin_exit_still_runs(lane_dirs: Path) -> None:
    # BTC already open (consuming the whole 25 USDT cap) and underwater -> its disaster-stop exit
    # runs; SOL has bullish confluence but must be skipped because no budget remains.
    venue = ActivityVenue(closes={"SOLUSDT": BULL}, marks={"BTCUSDT": "80"})
    lane.write_state(
        {"lane_base": "0.01", "cursor": FUTURE_CURSOR, "entry_price": "100", "resting_stop": None},
        "BTCUSDT_activity",
    )
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "SOLUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT"], total_cap=Decimal("25"))

    assert [o for o in venue.orders if o["side"] == "Buy" and o["symbol"] == "SOLUSDT"] == []
    btc_sells = [
        o
        for o in venue.orders
        if o["side"] == "Sell" and o["symbol"] == "BTCUSDT" and o.get("orderFilter") != "StopOrder"
    ]
    assert len(btc_sells) == 1  # risk-reducing exit on the already-open coin is never cap-gated
    assert report["coins"]["SOLUSDT"]["lane_base"] == "0"  # SOL never entered


def test_per_coin_disaster_stop_uses_that_coins_own_entry(lane_dirs: Path) -> None:
    venue = ActivityVenue(marks={"SOLUSDT": "80"})  # entry 100, mark 80 < the -15% (85) level
    lane.write_state(
        {"lane_base": "0.01", "cursor": FUTURE_CURSOR, "entry_price": "100", "resting_stop": None},
        "SOLUSDT_activity",
    )
    report = _cycle(venue, ["SOLUSDT"])
    sells = [o for o in venue.orders if o["side"] == "Sell" and o.get("orderFilter") != "StopOrder"]
    assert len(sells) == 1 and sells[0]["symbol"] == "SOLUSDT"
    assert report["coins"]["SOLUSDT"]["lane_base"] == "0"


def test_one_coin_failure_does_not_abort_the_cycle(lane_dirs: Path) -> None:
    venue = ActivityVenue(closes={"BTCUSDT": BULL}, fail_kline="XRPUSDT")
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT", "XRPUSDT", "SOLUSDT"])
    assert "error" in report["coins"]["XRPUSDT"]
    assert "error" not in report["coins"]["BTCUSDT"]
    assert "error" not in report["coins"]["SOLUSDT"]
    assert [o for o in venue.orders if o["side"] == "Buy" and o["symbol"] == "BTCUSDT"]  # healthy


def test_universe_and_roster_constants() -> None:
    assert len(act.ACTIVITY_UNIVERSE) >= 39 and "ETHUSDT" in act.ACTIVITY_UNIVERSE
    assert 6 <= len(act.ROSTER) <= 10
    assert act.ENTRY_THRESHOLD > act.EXIT_THRESHOLD  # hysteresis band
    assert act.TIMEFRAME_WEIGHTS["1h"] > act.TIMEFRAME_WEIGHTS["15m"]  # higher tf weighted more


def test_activity_tuned_for_traffic_drops_4h_anchor() -> None:
    # Activity/visibility tuning (NOT edge): the 4h filter is dropped and --interval swaps the
    # fastest member, so `--interval 5m` scores on {5m,15m,1h}. Pins the trade-frequency tuning.
    assert act.CONFLUENCE_TIMEFRAMES == ("5m", "15m", "1h")
    assert "4h" not in act.CONFLUENCE_HIGHER_TIMEFRAMES
    assert act._timeframes_for("5m") == ("5m", "15m", "1h")
    assert act.ENTRY_THRESHOLD == Decimal("0.15")


def test_ledger_recovery_isolates_lanes_by_strategy_tag() -> None:
    # Cross-lane isolation on the shared ledger: a legacy (strategy=None) restart recovery must NOT
    # read the confluence lane's entry for the same coin (it would misprice the protective stop),
    # and vice versa. `strategy` is always compared; untagged legacy records read as None.
    records = [
        {"symbol": "BTCUSDT", "reason": "ENTRY_LONG", "ok": True, "avg_price": "100"},
        {
            "symbol": "BTCUSDT",
            "reason": "ENTRY_LONG",
            "ok": True,
            "avg_price": "200",
            "strategy": "ACTIVITY-CONFLUENCE",
        },
    ]
    # legacy/multi restart (strategy=None) recovers its OWN untagged 100, not the newer activity 200
    assert lane.entry_price_from_ledger(records, "BTCUSDT", None) == Decimal("100")
    # activity restart recovers its OWN tagged 200, not the legacy 100
    assert lane.entry_price_from_ledger(records, "BTCUSDT", "ACTIVITY-CONFLUENCE") == Decimal("200")


# --- price history: the chart series comes from the bars the confluence cycle already fetched -----
def test_price_history_reuses_the_reference_bars_without_extra_fetches(lane_dirs: Path) -> None:
    venue = ActivityVenue(closes={"BTCUSDT": BULL})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    _cycle(venue, ["BTCUSDT"], timeframes=("5m", "15m", "1h"))

    # Exactly one kline request per (coin, timeframe) — the price history adds no venue call.
    assert len(venue.kline_urls) == 3
    # Named by the COIN (what a chart is of), not by the activity state key.
    payload = json.loads((lane_dirs / "price_history_BTCUSDT.json").read_text())
    assert not (lane_dirs / "price_history_BTCUSDT_activity.json").exists()
    assert payload["symbol"] == "BTCUSDT"
    assert payload["interval"] == "5m"  # the fastest (reference) timeframe run_cycle evaluated
    assert payload["schema_version"] == 1 and payload["max_points"] == lane.PRICE_HISTORY_MAX_POINTS
    assert len(payload["points"]) == len(BULL)  # whole fetched window seeded on the first write
    assert payload["points"][-1]["close"] == BULL[-1][0]
    assert all(isinstance(p["close"], str) for p in payload["points"])


def test_price_history_failure_never_blocks_a_confluence_entry(
    lane_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(lane, "write_price_history", _boom)
    venue = ActivityVenue(closes={"BTCUSDT": BULL})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["BTCUSDT"])
    assert "error" not in report["coins"]["BTCUSDT"]  # the failure never reaches the per-coin guard
    assert len([o for o in venue.orders if o["side"] == "Buy"]) == 1
    assert not (lane_dirs / "price_history_BTCUSDT.json").exists()


def test_price_history_only_written_for_coins_the_lane_evaluates(lane_dirs: Path) -> None:
    venue = ActivityVenue(closes={"BTCUSDT": BULL}, fail_kline="XRPUSDT")
    _cycle(venue, ["BTCUSDT", "XRPUSDT"])
    assert (lane_dirs / "price_history_BTCUSDT.json").is_file()
    assert not (lane_dirs / "price_history_XRPUSDT.json").exists()  # never evaluated -> no file


# --- DEFECT 1: a delisted / empty-bar coin is a quiet SKIP, never a recurring exception -----------
def test_empty_bar_coin_is_skipped_cleanly_and_never_reaches_the_roster(lane_dirs: Path) -> None:
    # EOSUSDT is delisted on the demo venue and returns an empty kline list. Before the fix the
    # roster's ATR indexed `high[0]` and raised `list index out of range` EVERY cycle.
    venue = ActivityVenue(closes={"BTCUSDT": BULL, "EOSUSDT": []})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["EOSUSDT", "BTCUSDT"])

    eos = report["coins"]["EOSUSDT"]
    assert eos == {"skipped": "insufficient_bars", "bars": dict.fromkeys(("5m", "15m", "1h"), 0)}
    assert "error" not in eos  # a skip, not an exception
    # The other coin in the SAME cycle is scored and traded exactly as before.
    assert "error" not in report["coins"]["BTCUSDT"]
    assert Decimal(report["coins"]["BTCUSDT"]["confidence"]) >= act.ENTRY_THRESHOLD
    assert [o for o in venue.orders if o["side"] == "Buy" and o["symbol"] == "BTCUSDT"]
    assert not any(o["symbol"] == "EOSUSDT" for o in venue.orders)


def test_insufficient_but_nonempty_bars_are_skipped_the_same_way(lane_dirs: Path) -> None:
    short = [("100", "10")] * (act.MIN_ROSTER_BARS - 1)  # one bar short of the roster's lookback
    venue = ActivityVenue(closes={"THINUSDT": short})
    report = _cycle(venue, ["THINUSDT"])
    assert report["coins"]["THINUSDT"]["skipped"] == "insufficient_bars"
    assert venue.orders == []


def test_exactly_enough_bars_is_still_scored_normally(lane_dirs: Path) -> None:
    # Boundary: the guard must not steal a coin that has just enough data for the whole roster.
    # `_kline_rows` appends a forming bar that fetch_closed_bars drops: N closes -> N closed bars.
    enough = [("100", "10")] * act.MIN_ROSTER_BARS
    venue = ActivityVenue(closes={"OKUSDT": enough})
    report = _cycle(venue, ["OKUSDT"])
    assert "skipped" not in report["coins"]["OKUSDT"]
    assert "error" not in report["coins"]["OKUSDT"]
    assert "confidence" in report["coins"]["OKUSDT"]


def test_no_data_warning_is_emitted_once_per_run_not_once_per_cycle(
    lane_dirs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    venue = ActivityVenue(closes={"EOSUSDT": [], "FTMUSDT": []})
    for _ in range(3):
        _cycle(venue, ["EOSUSDT", "FTMUSDT"])
    lines = [ln for ln in capsys.readouterr().err.splitlines() if "no usable bars" in ln]
    assert len(lines) == 2  # one per SYMBOL for the whole run, not 2 per cycle
    assert sorted(ln.split(":")[0] for ln in lines) == ["EOSUSDT", "FTMUSDT"]


def test_scoring_for_healthy_coins_is_identical_with_and_without_a_dead_coin(
    lane_dirs: Path,
) -> None:
    """A skipped coin must not perturb any other coin's score or decision."""
    alone = _cycle(ActivityVenue(closes={"BTCUSDT": BULL}), ["BTCUSDT"])
    with_dead = _cycle(
        ActivityVenue(closes={"BTCUSDT": BULL, "EOSUSDT": []}), ["EOSUSDT", "BTCUSDT", "FTMUSDT"]
    )
    assert with_dead["coins"]["BTCUSDT"]["confidence"] == alone["coins"]["BTCUSDT"]["confidence"]
    assert with_dead["coins"]["BTCUSDT"]["decision"] == alone["coins"]["BTCUSDT"]["decision"]


def test_a_universe_of_only_dead_coins_is_not_a_connectivity_outage(lane_dirs: Path) -> None:
    # DATA absence must never be reinterpreted as a network outage (it would back the lane off for
    # nothing). No coin was evaluated, so there is nothing to call an outage.
    report = _cycle(ActivityVenue(closes={"EOSUSDT": [], "FTMUSDT": []}), ["EOSUSDT", "FTMUSDT"])
    assert report["connectivity_outage"] is False


# --- DEFECT 2: a total connectivity loss is ONE outage, logged once, and backs off ----------------
def test_all_coins_failing_on_transport_is_one_outage_logged_once(
    lane_dirs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    venue = ActivityVenue(transport_down=True)
    report = _cycle(venue, ["BTCUSDT", "SOLUSDT", "XRPUSDT"])

    assert report["connectivity_outage"] is True
    err = capsys.readouterr().err
    assert err.count("connectivity outage") == 1  # ONE line, not one per coin
    assert "activity cycle failed" not in err  # the 3-per-cycle flood is suppressed
    assert all("error" in report["coins"][s] for s in ("BTCUSDT", "SOLUSDT", "XRPUSDT"))


def test_a_mixed_cycle_is_not_an_outage_and_still_logs_each_coin(
    lane_dirs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    class HalfDown(ActivityVenue):
        def get(self, url: str, headers: dict[str, str]) -> bytes:
            if self._symbol(url) == "SOLUSDT":
                raise URLError(gaierror(8, "nodename nor servname provided, or not known"))
            return super().get(url, headers)

    venue = HalfDown(closes={"BTCUSDT": BULL})
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    report = _cycle(venue, ["SOLUSDT", "BTCUSDT"])

    assert report["connectivity_outage"] is False  # one coin succeeded -> not a run-level outage
    err = capsys.readouterr().err
    assert "connectivity outage" not in err
    assert err.count("SOLUSDT: activity cycle failed") == 1  # per-coin line still emitted verbatim
    assert [o for o in venue.orders if o["side"] == "Buy" and o["symbol"] == "BTCUSDT"]


def test_a_pure_data_failure_is_never_classified_as_a_connectivity_outage(lane_dirs: Path) -> None:
    # fail_kline raises RuntimeError — a DATA problem. Even as the only evaluated coin it must not
    # be reinterpreted as transport loss, and the error is neither swallowed nor rewritten.
    venue = ActivityVenue(fail_kline="XRPUSDT")
    report = _cycle(venue, ["XRPUSDT"])
    assert report["connectivity_outage"] is False
    assert "kline unavailable" in report["coins"]["XRPUSDT"]["error"]


def test_orders_exits_and_stops_still_go_out_as_soon_as_a_coin_succeeds(lane_dirs: Path) -> None:
    """The safety invariant: an outage delays nothing once connectivity is back."""
    lane.write_state(
        {"lane_base": "0", "cursor": OLD_CURSOR, "entry_price": None, "resting_stop": None},
        "BTCUSDT_activity",
    )
    lane.write_state(  # open and 20% underwater -> its disaster-stop exit is due
        {"lane_base": "0.01", "cursor": FUTURE_CURSOR, "entry_price": "100", "resting_stop": None},
        "SOLUSDT_activity",
    )
    down = ActivityVenue(transport_down=True)
    assert _cycle(down, ["BTCUSDT", "SOLUSDT"])["connectivity_outage"] is True
    assert down.orders == []  # nothing could be sent while the network was gone

    back = ActivityVenue(closes={"BTCUSDT": BULL}, marks={"SOLUSDT": "80"})
    report = _cycle(back, ["BTCUSDT", "SOLUSDT"])

    assert report["connectivity_outage"] is False
    # The entry the bullish score asks for goes out on the very first healthy cycle...
    assert [o for o in back.orders if o["side"] == "Buy" and o["symbol"] == "BTCUSDT"]
    # ...and so does the risk-reducing exit that was due on the underwater coin.
    sells = [
        o
        for o in back.orders
        if o["side"] == "Sell" and o["symbol"] == "SOLUSDT" and o.get("orderFilter") != "StopOrder"
    ]
    assert len(sells) == 1
    assert report["coins"]["SOLUSDT"]["lane_base"] == "0"


def test_outage_backoff_is_bounded_capped_and_never_faster_than_cadence() -> None:
    assert act.outage_backoff_seconds(0, 300.0) == 300.0  # healthy -> normal cadence
    assert act.outage_backoff_seconds(1, 300.0) == 600.0  # first outage doubles
    assert act.outage_backoff_seconds(2, 300.0) == act.OUTAGE_BACKOFF_MAX_SECONDS  # capped
    assert act.outage_backoff_seconds(99, 60.0) == act.OUTAGE_BACKOFF_MAX_SECONDS  # stays capped
    # A cadence slower than the cap must never be sped UP by "backing off".
    slow = act.OUTAGE_BACKOFF_MAX_SECONDS * 4
    assert act.outage_backoff_seconds(3, slow) == slow


def test_loop_backs_off_while_down_then_logs_recovery_and_resumes_cadence(
    lane_dirs: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reports: list[dict[str, Any]] = [
        {"connectivity_outage": True},
        {"connectivity_outage": True},
        {"connectivity_outage": False},
    ]
    monkeypatch.setattr(pf, "preflight", lambda *_a, **_k: {"ok": True, "host": "demo"})
    monkeypatch.setattr(act, "run_activity_cycle", lambda *_a, **_k: reports.pop(0))

    waits: list[float] = []

    def _wait(seconds: float, _sleep: Any) -> bool:
        waits.append(seconds)
        return bool(reports)  # False == kill switch seen mid-wait; ends the loop after cycle 3

    monkeypatch.setattr(act, "_wait_honouring_kill_switch", _wait)
    assert act.run_activity_lane("k", "s", interval="5m", loop=True, sleep=lambda _s: None) == 0

    cadence = max(act.LOOP_MIN_SLEEP_SECONDS, 5 * 60)
    assert waits == [
        act.outage_backoff_seconds(1, cadence),  # backed off after the first outage cycle
        act.outage_backoff_seconds(2, cadence),  # and further after the second
        cadence,  # recovered -> normal cadence restored immediately
    ]
    assert waits[0] > cadence and waits[1] > waits[0]
    out = capsys.readouterr()
    assert "connectivity restored — resuming normal cadence." in out.out
    assert out.err.count("connectivity outage — backing off") == 2  # once per outage cycle, not 37


def test_kill_switch_is_honoured_while_backing_off(lane_dirs: Path) -> None:
    # A 900s backoff must not make the lane deaf to the kill switch for 900s.
    calls: list[float] = []

    def _sleep(seconds: float) -> None:
        calls.append(seconds)
        if len(calls) == 2:
            (lane_dirs / "KILL_SWITCH").write_text("stop")

    assert act._wait_honouring_kill_switch(act.OUTAGE_BACKOFF_MAX_SECONDS, _sleep) is False
    assert len(calls) == 2  # aborted on the second slice, not after the full wait
    assert sum(calls) < act.OUTAGE_BACKOFF_MAX_SECONDS
    assert all(step <= act.OUTAGE_BACKOFF_POLL_SECONDS for step in calls)


def test_wait_returns_true_when_no_kill_switch_and_sleeps_the_whole_wait(lane_dirs: Path) -> None:
    calls: list[float] = []
    assert act._wait_honouring_kill_switch(70.0, calls.append) is True
    assert sum(calls) == 70.0  # cadence is preserved exactly; only the granularity changed
