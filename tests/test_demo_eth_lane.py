"""Offline tests for the D-104 stage-2 ETH demo measurement lane. No network, no keys."""

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
import tios.evidence.demo_decision_evidence_v2 as stage_b  # noqa: E402
from tests.test_demo_decision_evidence_v2 import _activation_root  # noqa: E402
from tios.services.dashboard_api import demo_lane as dashboard_demo_lane  # noqa: E402

START = datetime(2026, 7, 1, tzinfo=UTC)

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        self.order_details: dict[str, dict[str, Any]] = {}

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
                                "orderId": order_id,
                                "orderStatus": status,
                                "avgPrice": "100",
                                "cumExecQty": "0.01",
                                "cumExecFee": "0.001",
                                **self.order_details.get(order_id, {}),
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
            self.order_details[order_id] = {
                "symbol": str(order.get("symbol")),
                "side": str(order.get("side")),
                "orderType": str(order.get("orderType")),
                "stopOrderType": "Stop",
                # Observed spot realtime rows use 0 (venue-default/unspecified).
                "triggerDirection": 0,
                "marketUnit": "baseCoin",
                "triggerPrice": str(order.get("triggerPrice")),
                "qty": str(order.get("qty")),
            }
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
    assert state["resting_stop"]["risk_fraction"] == str(lane.DEMO_DISASTER_STOP_PCT)
    assert state["resting_stop"]["price_tick"] == "0.01"
    # Heartbeat and durable state carry the same bound order metadata; the dashboard
    # requires both snapshots to corroborate before it says protection is current.
    assert heartbeat["resting_stop"] == state["resting_stop"]


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
    assert "risk_fraction" not in heartbeat["resting_stop"]


def test_malformed_tracked_stop_cannot_unblock_a_fresh_entry_signal(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    lane.write_state(
        {
            **armed,
            "lane_base": "0",
            "entry_price": None,
            "resting_stop": {
                "state": "ACTIVE",
                "order_id": "MALFORMED",
                "trigger_price": True,
                "base_qty": "0.01",
            },
        }
    )
    venue.closes = _flat_history() + [("200", "500")]

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    assert heartbeat["fresh_signals"] >= 1
    assert venue.orders == []
    assert heartbeat["resting_stop"]["order_id"] == "MALFORMED"


def test_ambiguous_wrong_bound_row_stays_unsafe_in_heartbeat(lane_dirs: Path) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    ambiguous = {
        "state": "AMBIGUOUS",
        "order_ids": ["OLD"],
        "order_records": {"OLD": {"order_id": "OLD", "trigger_price": "84", "base_qty": "0.01"}},
        "ambiguity_reason": "fixture retained trigger differs from venue",
    }
    lane.write_state(
        {
            **armed,
            "lane_base": "0.01",
            "entry_price": "100",
            "resting_stop": ambiguous,
        }
    )
    venue.order_statuses["OLD"] = "Untriggered"
    venue.order_details["OLD"] = {
        "symbol": "ETHUSDT",
        "side": "Sell",
        "orderType": "Market",
        "stopOrderType": "Stop",
        "triggerDirection": 0,
        "triggerPrice": "85",
        "qty": "0.01",
    }

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )

    assert heartbeat["resting_stop"] == ambiguous
    assert heartbeat["resting_stop"]["state"] == "AMBIGUOUS"
    assert venue.orders == []


def test_confirmed_legacy_stop_is_locally_enriched_without_any_venue_mutation(
    lane_dirs: Path,
) -> None:
    venue = FakeVenue(_flat_history())
    lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    armed = json.loads((lane_dirs / "lane_state.json").read_text())
    legacy = {
        "state": "ACTIVE",
        "order_id": "LEGACY-STOP",
        "trigger_price": "85.00",
        "risk_boundary_price": "85.00",
        "base_qty": "0.01",
        "position_base_qty": "0.01",
    }
    lane.write_state(
        {
            **armed,
            "lane_base": "0.01",
            "entry_price": "100",
            "resting_stop": legacy,
        }
    )
    venue.order_statuses["LEGACY-STOP"] = "Untriggered"
    venue.order_details["LEGACY-STOP"] = {"triggerPrice": "85.00", "qty": "0.01"}
    venue.order_details["LEGACY-STOP"].update(
        {
            "symbol": "ETHUSDT",
            "side": "Sell",
            "orderType": "Market",
            "stopOrderType": "Stop",
            "triggerDirection": 0,
            "marketUnit": "baseCoin",
        }
    )

    heartbeat = lane.run_cycle(
        "k", "s", get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None
    )
    persisted = json.loads((lane_dirs / "lane_state.json").read_text())

    assert venue.orders == [], "metadata migration must never create or replace an order"
    assert persisted["resting_stop"]["order_id"] == "LEGACY-STOP"
    assert persisted["resting_stop"]["risk_fraction"] == "0.15"
    assert persisted["resting_stop"]["price_tick"] == "0.01"
    assert heartbeat["resting_stop"] == persisted["resting_stop"]
    projected = dashboard_demo_lane._operational_disaster_stop(
        persisted,
        heartbeat,
        running=True,
        ledger_base=0.01,
        now=datetime.fromisoformat(heartbeat["at"]),
    )
    assert projected["currently_confirmed"] is True
    assert projected["order_id"] == "LEGACY-STOP"


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


# --- Stage B default-disabled integration -----------------------------------------------------

EPOCH = "act_" + "a" * 64
INTENT = "evt_" + "b" * 64
TARGET_ORD = "ord_" + "c" * 64


def _exit_payload() -> dict[str, Any]:
    return {
        "side": "SELL",
        "order_type": "MARKET",
        "qty": "0.01",
        "quantity_unit": "BASE",
        "trigger_price": None,
        "order_filter": "Order",
        "target_order_alias": None,
    }


def _payload_for(kind: str) -> dict[str, Any]:
    if kind == "EXIT_CREATE":
        return _exit_payload()
    payload = {
        "side": "SELL",
        "order_type": "STOP_MARKET",
        "qty": "0.01",
        "quantity_unit": "BASE",
        "trigger_price": "85",
        "order_filter": "StopOrder",
        "target_order_alias": None,
    }
    if kind == "STOP_REPLACE_CREATE":
        payload["target_order_alias"] = TARGET_ORD
    return payload


def _reserved_state(kind: str) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = lane.build_pending_risk_reduction(
        activation_epoch=EPOCH,
        subject_intent_event_id=INTENT,
        action_kind=kind,
        sequence=1,
        payload=_payload_for(kind),
    )
    state = lane.reserve_risk_reduction({"lane_base": "0.01", "cursor": None}, pending)
    return state, pending


def _active_repo(tmp_path: Path) -> tuple[Path, stage_b.ActivationContext, datetime]:
    now = datetime.now(UTC)
    repo = _activation_root(tmp_path, approved_at=now)
    activation = stage_b.load_activation(repo, now=now)
    return repo, activation, now


def _bound_event(activation: stage_b.ActivationContext, now: datetime) -> stage_b.EvidenceEvent:
    return stage_b.next_event(
        None,
        activation_epoch=activation.activation_epoch,
        event_type=stage_b.EventType.ACTIVATION_BOUND,
        recorded_at=now,
        payload={
            "activation_receipt_sha256": activation.receipt_sha256,
            "config_sha256": activation.config_sha256,
            "independent_review_sha256": activation.independent_review_sha256,
            "flat_reconciliation_sha256": activation.flat_reconciliation_sha256,
            "rollback_config_sha256": activation.rollback_config_sha256,
            "controlled_restart_id": activation.receipt["controlled_restart_id"],
            "repo_commit": activation.receipt["repo_commit"],
        },
    )


def test_repository_runtime_root_and_latch_absent_default_disabled() -> None:
    # The real repository must never carry the Stage B runtime root during implementation/tests.
    assert not (REPO_ROOT / stage_b.PRIVATE_ROOT_REL).exists()
    assert lane.stage_b_active(REPO_ROOT) is False
    state = lane.read_state()
    assert lane.stage_b_latch(state) is None and lane.entry_blocked(state) is False


def test_positive_activation_reader_sees_active_root(tmp_path: Path) -> None:
    repo, _activation, _now = _active_repo(tmp_path)
    assert lane.stage_b_active(repo) is True


def test_pending_payload_hash_and_action_id_verified() -> None:
    payload = _exit_payload()
    pending = lane.build_pending_risk_reduction(
        activation_epoch=EPOCH,
        subject_intent_event_id=INTENT,
        action_kind="EXIT_CREATE",
        sequence=1,
        payload=payload,
    )
    assert pending["payload_sha256"] == stage_b.canonical_sha256(payload)
    core = {k: pending[k] for k in (
        "schema", "subject_intent_event_id", "action_kind", "sequence",
        "payload", "payload_sha256", "client_key_sha256",
    )}  # fmt: skip
    assert pending["action_id"] == "rr_" + stage_b.canonical_sha256(core)
    # Raw key never stored in lane state; only its hash, recomputable from the verified record.
    key = lane.pending_client_key(pending, EPOCH)
    assert len(key) == 36 and key.startswith("tios2_r_")
    assert stage_b.sha256_bytes(key.encode("ascii")) == pending["client_key_sha256"]
    tampered = {**pending, "payload_sha256": "0" * 64}
    with pytest.raises(ValueError, match="does not match"):
        lane.pending_client_key(tampered, EPOCH)


def test_pending_payload_rejects_bad_target_combinations() -> None:
    bad_exit = {**_exit_payload(), "target_order_alias": TARGET_ORD}
    with pytest.raises(ValueError, match="null target"):
        lane.build_pending_risk_reduction(
            activation_epoch=EPOCH, subject_intent_event_id=INTENT,
            action_kind="EXIT_CREATE", sequence=1, payload=bad_exit,
        )  # fmt: skip
    bad_replace = _payload_for("STOP_REPLACE_CREATE")
    bad_replace["target_order_alias"] = None
    with pytest.raises(ValueError, match="tracked target"):
        lane.build_pending_risk_reduction(
            activation_epoch=EPOCH, subject_intent_event_id=INTENT,
            action_kind="STOP_REPLACE_CREATE", sequence=1, payload=bad_replace,
        )  # fmt: skip


def test_cancel_target_derives_no_client_key() -> None:
    payload = {
        "side": "SELL", "order_type": "MARKET", "qty": "0", "quantity_unit": "BASE",
        "trigger_price": None, "order_filter": "StopOrder", "target_order_alias": TARGET_ORD,
    }  # fmt: skip
    pending = lane.build_pending_risk_reduction(
        activation_epoch=EPOCH, subject_intent_event_id=INTENT,
        action_kind="CANCEL_TARGET", sequence=1, payload=payload,
    )  # fmt: skip
    assert pending["client_key_sha256"] is None
    with pytest.raises(ValueError, match="derives no client key"):
        lane.pending_client_key(pending, EPOCH)


@pytest.mark.parametrize("kind", ["EXIT_CREATE", "STOP_CREATE", "STOP_REPLACE_CREATE"])
def test_crash_before_reserved_fresh_reserve_posts_exactly_once(kind: str, lane_dirs: Path) -> None:
    # Crash point 1: no pending persisted -> a fresh reserve+execute issues exactly one POST.
    state, _pending = _reserved_state(kind)
    posts = {"n": 0}

    def do_post() -> dict[str, Any]:
        posts["n"] += 1
        return {"retCode": 0, "result": {"orderId": "X"}}

    state, _res = lane.execute_risk_reduction_create(state, do_post, lambda: {"queried": True})
    assert posts["n"] == 1
    assert state["stage_b_v2"]["pending_risk_reduction"]["phase"] == "ACK_PENDING"


@pytest.mark.parametrize("kind", ["EXIT_CREATE", "STOP_CREATE", "STOP_REPLACE_CREATE"])
def test_crash_after_reserved_permits_the_one_post(kind: str, lane_dirs: Path) -> None:
    # Crash point 2: phase RESERVED persisted, crash before POST_UNKNOWN -> the one POST is allowed.
    state, _pending = _reserved_state(kind)
    reloaded = json.loads((lane_dirs / "lane_state.json").read_text())
    assert reloaded["stage_b_v2"]["pending_risk_reduction"]["phase"] == "RESERVED"
    posts = {"n": 0}

    def do_post() -> dict[str, Any]:
        posts["n"] += 1
        return {"retCode": 0, "result": {"orderId": "X"}}

    lane.execute_risk_reduction_create(reloaded, do_post, lambda: {"queried": True})
    assert posts["n"] == 1


@pytest.mark.parametrize("kind", ["EXIT_CREATE", "STOP_CREATE", "STOP_REPLACE_CREATE"])
@pytest.mark.parametrize("phase", ["POST_UNKNOWN", "ACK_PENDING"])
def test_crash_after_post_unknown_or_ack_never_reposts(
    kind: str, phase: str, lane_dirs: Path
) -> None:
    # Crash points 3 & 4: pre-POST POST_UNKNOWN and post-POST-before-ack both present as an
    # unresolved attempt. Reload (restart) must reconcile by key and issue ZERO create POSTs.
    state, _pending = _reserved_state(kind)
    state = lane.advance_pending(state, phase)
    reloaded = json.loads((lane_dirs / "lane_state.json").read_text())
    posts = {"n": 0}

    def do_post() -> dict[str, Any]:
        posts["n"] += 1
        return {"retCode": 0, "result": {"orderId": "X"}}

    _state, res = lane.execute_risk_reduction_create(reloaded, do_post, lambda: {"queried": True})
    assert posts["n"] == 0 and res == {"queried": True}


def test_reserve_persists_before_post_and_stores_no_raw_key(lane_dirs: Path) -> None:
    state, _pending = _reserved_state("EXIT_CREATE")
    raw = (lane_dirs / "lane_state.json").read_text()
    persisted = json.loads(raw)
    pending = persisted["stage_b_v2"]["pending_risk_reduction"]
    assert pending["phase"] == "RESERVED"
    assert persisted["stage_b_v2"]["risk_reduction_sequence"] == 1
    # The raw client key (tios2_r_...) is never written to lane state — only its SHA-256.
    assert "tios2_r_" not in raw
    assert pending["client_key_sha256"] and len(pending["client_key_sha256"]) == 64


def test_economics_from_execution_rows_partial_fills_all_fee_currencies() -> None:
    rows = [
        {
            "side": "Buy",
            "execQty": "0.02",
            "execValue": "40",
            "execFee": "0.00002",
            "feeCurrency": "ETH",
        },
        {
            "side": "Sell",
            "execQty": "0.008",
            "execValue": "16",
            "execFee": "0.01",
            "feeCurrency": "USDT",
        },
        {
            "side": "Sell",
            "execQty": "0.001",
            "execValue": "2",
            "execFee": "0.5",
            "feeCurrency": "BONK",
        },
    ]
    econ = lane.economics_from_execution_rows(rows)
    # position = (buy 0.02 - buy base fee 0.00002) - (sell 0.008 + 0.001 + sell base fee 0)
    assert econ["position_base_qty"] == Decimal("0.02") - Decimal("0.00002") - Decimal("0.009")
    assert econ["entry_exec_value"] == Decimal("40") and econ["exit_exec_value"] == Decimal("18")
    assert econ["quote_fee"] == Decimal("0.01") and econ["base_fee"] == Decimal("0.00002")
    assert econ["third_fee_present"] == Decimal("1")  # a nonzero third-currency fee is flagged


def test_partially_filled_canceled_updates_lane_base_from_executions() -> None:
    # The correctness gap: a terminal PartiallyFilledCanceled order with real executions must move
    # lane_base off exact rows, not off a rounded wallet delta (which the fixture disagrees with).
    rows = [
        {"side": "Buy", "execQty": "0.004", "execValue": "8", "execFee": "0", "feeCurrency": "USDT"}
    ]
    econ = lane.economics_from_execution_rows(rows)
    assert econ["position_base_qty"] == Decimal("0.004")


def test_economics_rejects_non_decimal_and_boolean_fields() -> None:
    with pytest.raises(ValueError, match="boolean"):
        lane.economics_from_execution_rows(
            [
                {
                    "side": "Buy",
                    "execQty": True,
                    "execValue": "1",
                    "execFee": "0",
                    "feeCurrency": "USDT",
                }
            ]
        )
    with pytest.raises(ValueError, match="nonnegative"):
        lane.economics_from_execution_rows(
            [
                {
                    "side": "Buy",
                    "execQty": "-1",
                    "execValue": "1",
                    "execFee": "0",
                    "feeCurrency": "USDT",
                }
            ]
        )


def test_entry_block_latch_blocks_entries_but_bypass_still_posts(lane_dirs: Path) -> None:
    # Evidence degradation latches ENTRY_BLOCK: new entries are gated...
    blocked = {"lane_base": "0", "stage_b_v2": {"evidence_state": "ENTRY_BLOCK"}}
    assert lane.entry_blocked(blocked) is True
    # ...yet a reserved risk-reducing exit still proceeds to its single POST (the bypass invariant).
    state, _pending = _reserved_state("EXIT_CREATE")
    state["stage_b_v2"]["evidence_state"] = "ENTRY_BLOCK"
    posts = {"n": 0}

    def do_post() -> dict[str, Any]:
        posts["n"] += 1
        return {"retCode": 0, "result": {"orderId": "X"}}

    lane.execute_risk_reduction_create(state, do_post, lambda: {"queried": True})
    assert posts["n"] == 1


def test_unresolved_attempt_blocks_new_entries() -> None:
    state = {
        "stage_b_v2": {
            "evidence_state": "READY",
            "pending_risk_reduction": {"phase": "POST_UNKNOWN"},
        }
    }
    assert lane.entry_blocked(state) is True


def test_ready_latch_allows_entries() -> None:
    assert (
        lane.entry_blocked(
            {"stage_b_v2": {"evidence_state": "READY", "pending_risk_reduction": None}}
        )
        is False
    )


def test_sink_invoked_only_under_held_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, activation, now = _active_repo(tmp_path)
    monkeypatch.setattr(lane, "LANE_DIR", repo / "artifacts/trading_domain/demo_lane")
    monkeypatch.setattr(lane, "LANE_STATE", lane.LANE_DIR / "lane_state.json")
    event = _bound_event(activation, now)
    # A commit REQUIRES the exclusive lane-lock capability; append refuses without it.
    with pytest.raises(stage_b.StageBEvidenceError, match="lane lock capability is required"):
        stage_b.StageBEvidenceSink(repo).append([event], capability=None)  # type: ignore[arg-type]
    with stage_b.exclusive_lane_lock_capability(repo) as capability:
        assert lane.record_stage_b_events([event], capability, repo_root=repo) == "READY"


def test_evidence_failure_latches_entry_block_without_raising(tmp_path: Path) -> None:
    repo, _activation, _now = _active_repo(tmp_path)
    # A non-genesis first event fails validation inside the sink; record must degrade to
    # ENTRY_BLOCK rather than raise, so an evidence outage never obstructs the caller.
    bad = stage_b.next_event(
        None, activation_epoch=EPOCH, event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=datetime.now(UTC),
        payload={
            "strategy_alias": "strategy_" + "d" * 64, "cost_alias": "cost_" + "e" * 64,
            "risk_alias": "risk_" + "f" * 64, "symbol": "ETHUSDT", "timeframe": "1h",
            "decision": "ENTRY", "side": "BUY", "requested_qty": "25", "quantity_unit": "QUOTE",
        },
    )  # fmt: skip
    with stage_b.exclusive_lane_lock_capability(repo) as capability:
        assert lane.record_stage_b_events([bad], capability, repo_root=repo) == "ENTRY_BLOCK"


# --- ACTIVE-path integration (activated root in a temp dir; never the real runtime root) -------

_ENTRY_ROW = {
    "side": "Buy",
    "execQty": "0.25",
    "execValue": "25",
    "execFee": "0",
    "feeCurrency": "USDT",
    "execId": "e1",
    "execTime": "1",
    "orderId": "O",
    "leavesQty": "0",
}


class ActiveVenue:
    """Venue serving the ACTIVE order + reconciliation endpoints, keyed by orderLinkId."""

    def __init__(
        self,
        exec_rows: list[dict[str, Any]],
        *,
        realtime_status: str | None = "Filled",
        history_status: str | None = None,
        repo_root: Path | None = None,
        closes: list[tuple[str, str]] | None = None,
    ) -> None:
        self.exec_rows = exec_rows
        self.realtime_status = realtime_status
        self.history_status = history_status
        self.repo_root = repo_root
        self.closes = closes
        self.balances = {"USDT": Decimal("1000"), "ETH": Decimal("0.01")}  # wallet delta disagrees
        self.create_posts = 0
        self.created: list[dict[str, Any]] = []
        self.committed_keys_at_post: list[list[object]] = []

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        query = parse_qs(urlsplit(url).query)
        link = query.get("orderLinkId", [None])[0]
        if "/v5/market/kline" in url:
            rows = list(reversed(_kline_rows(self.closes or _flat_history())))
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
            coins = [{"coin": k, "walletBalance": str(v)} for k, v in self.balances.items()]
            return json.dumps({"retCode": 0, "result": {"list": [{"coin": coins}]}}).encode()
        if "/v5/order/realtime" in url:
            if link is not None:  # reconciliation lookup by client key
                rows = (
                    []
                    if self.realtime_status is None
                    else [{"orderLinkId": link, "orderStatus": self.realtime_status}]
                )
                return json.dumps({"result": {"list": rows, "nextPageCursor": ""}}).encode()
            order_id = query.get("orderId", [""])[0]  # place()'s terminal poll
            status = self.realtime_status or self.history_status or "Filled"
            return json.dumps(
                {
                    "result": {
                        "list": [
                            {
                                "orderId": order_id,
                                "orderStatus": status,
                                "avgPrice": "100",
                                "cumExecQty": "0.25",
                                "cumExecFee": "0.001",
                            }
                        ]
                    }
                }
            ).encode()
        if "/v5/order/history" in url:
            rows = (
                []
                if self.history_status is None
                else [{"orderLinkId": link, "orderStatus": self.history_status}]
            )
            return json.dumps({"result": {"list": rows, "nextPageCursor": ""}}).encode()
        if "/v5/execution/list" in url:
            rows = [{**r, "orderLinkId": link} for r in self.exec_rows]
            return json.dumps({"result": {"list": rows, "nextPageCursor": ""}}).encode()
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url: str, headers: dict[str, str], body: bytes) -> bytes:
        assert "/v5/order/create" in url
        self.create_posts += 1
        order = json.loads(body)
        self.created.append(order)
        # Prove the client key was DURABLY COMMITTED to evidence BEFORE this POST.
        if self.repo_root is not None:
            events = stage_b.StageBEvidenceSink(self.repo_root).load().events
            self.committed_keys_at_post.append(
                [
                    e.payload.get("client_key")
                    for e in events
                    if e.event_type is stage_b.EventType.IDEMPOTENCY_KEY_RESERVED
                ]
            )
        if order["side"] == "Buy":
            self.balances["ETH"] += Decimal("0.25")
            self.balances["USDT"] -= Decimal("25")
        else:
            self.balances["ETH"] -= Decimal("0.01")
        return json.dumps(
            {"retCode": 0, "result": {"orderId": f"OID-{self.create_posts}"}}
        ).encode()


def _active_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    now = datetime.now(UTC)
    repo = _activation_root(tmp_path, approved_at=now)
    lane_dir = repo / "artifacts/trading_domain/demo_lane"
    monkeypatch.setattr(lane, "STAGE_B_REPO_ROOT", repo)
    monkeypatch.setattr(lane, "LANE_DIR", lane_dir)
    monkeypatch.setattr(lane, "LANE_STATE", lane_dir / "lane_state.json")
    monkeypatch.setattr(lane, "KILL_SWITCH", lane_dir / "KILL_SWITCH")
    monkeypatch.setattr(lane, "ORDERS_LEDGER", lane_dir / "orders.jsonl")
    monkeypatch.setattr(lane, "ACTIONS_LEDGER", lane_dir / "demo_lane_actions.jsonl")
    monkeypatch.setattr(lane, "HEARTBEAT", lane_dir / "heartbeat.json")
    return repo


def _epoch(repo: Path) -> str:
    return stage_b.load_activation(repo).activation_epoch


def _seed_open_episode(repo: Path, lane_base: str) -> dict[str, Any]:
    return {
        "lane_base": lane_base,
        "cursor": None,
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 0,
            "evidence_state": "READY",
        },
    }


def test_active_entry_commits_key_before_post_and_stays_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-C + P0-E: under the HELD capability, the entry key is durably committed to the evidence
    # chain BEFORE the POST, equals the posted orderLinkId, and the path does NOT self-inflict
    # ENTRY_BLOCK (no re-acquired lock). No raw key is stored in lane state.
    repo = _active_env(tmp_path, monkeypatch)
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        action, lane_base, entry_price, state = lane.active_entry(
            "SIG-1", {"lane_base": "0", "cursor": None}, "k", "s",
            get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
            capability=cap, repo_root=repo,
        )  # fmt: skip
    assert venue.create_posts == 1
    posted_key = venue.created[0]["orderLinkId"]
    assert posted_key in venue.committed_keys_at_post[0]  # committed BEFORE the POST
    assert state["stage_b_v2"]["evidence_state"] == "READY"  # not a self-inflicted ENTRY_BLOCK
    assert state["stage_b_v2"]["open_episode_event_id"].startswith("evt_")
    assert "client_key" not in json.dumps(state["stage_b_v2"])  # no raw key in lane state
    assert lane_base == Decimal("0.25") and entry_price == Decimal("100") and action is not None


def test_active_entry_without_capability_fails_closed_no_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-E: ACTIVE but no held lock threaded -> cannot durably persist the key.
    # Fail closed: ENTRY_BLOCK, no POST.
    repo = _active_env(tmp_path, monkeypatch)
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    action, lane_base, _e, state = lane.active_entry(
        "SIG-1", {"lane_base": "0", "cursor": None}, "k", "s",
        get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
        capability=None, repo_root=repo,
    )  # fmt: skip
    assert venue.create_posts == 0 and action is None and lane_base == Decimal("0")
    assert state["stage_b_v2"]["evidence_state"] == "ENTRY_BLOCK"


def test_active_lane_base_from_executions_partially_filled_canceled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-C stop gate: a PartiallyFilledCanceled entry (realtime miss -> history terminal) drives
    # lane_base from the exact executions (0.004), NOT the 0.25 wallet delta.
    repo = _active_env(tmp_path, monkeypatch)
    rows = [
        {
            "side": "Buy",
            "execQty": "0.004",
            "execValue": "10",
            "execFee": "0",
            "feeCurrency": "USDT",
            "execId": "e1",
            "execTime": "1",
            "orderId": "O",
            "leavesQty": "0",
        }
    ]
    venue = ActiveVenue(
        rows, realtime_status=None, history_status="PartiallyFilledCanceled", repo_root=repo
    )
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        _action, lane_base, entry_price, _state = lane.active_entry(
            "SIG-1", {"lane_base": "0", "cursor": None}, "k", "s",
            get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
            capability=cap, repo_root=repo,
        )  # fmt: skip
    assert lane_base == Decimal("0.004") and entry_price == Decimal("2500")


def test_active_evidence_failure_blocks_entry_but_risk_reducing_sell_posts_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-E/C invariant: pre-submission commit failure -> ENTRY_BLOCK + NO POST; yet a risk-reducing
    # sell on the already-open episode still posts EXACTLY once (evidence never blocks reduction).
    repo = _active_env(tmp_path, monkeypatch)

    def boom(*_a: object, **_k: object) -> None:
        raise stage_b.StageBEvidenceError("simulated evidence-store outage")

    monkeypatch.setattr(stage_b.StageBEvidenceSink, "append", boom)
    seeded = _seed_open_episode(repo, "0.25")
    venue = ActiveVenue([_ENTRY_ROW], realtime_status="Filled", repo_root=repo)
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        action, _lb, _e, state = lane.active_entry(
            "SIG-1", seeded, "k", "s",
            get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
            capability=cap, repo_root=repo,
        )  # fmt: skip
    assert action is None and venue.create_posts == 0  # entry blocked, NO POST
    assert state["stage_b_v2"]["evidence_state"] == "ENTRY_BLOCK"
    assert lane.entry_blocked(state) is True
    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    rr_action, _s2 = lane.active_risk_reduction(
        sell, "EXIT_CREATE", state, "k", "s",
        get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None, repo_root=repo,
    )  # fmt: skip
    assert venue.create_posts == 1 and rr_action is not None and rr_action.get("order_id")


def _commit_presubmission(repo: Path, key: str) -> str:
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        activation = stage_b.load_activation(repo)
        material = lane._alias_material(activation)
        events, intent_id, _order_alias = lane._entry_presubmission_events(
            activation, None, material, key
        )
        stage_b.StageBEvidenceSink(repo).append(events, capability=cap)
    return intent_id


def test_active_restart_reconciles_by_committed_key_and_reposts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-C restart: a mid-flight entry (committed intent, NO attempt) is recovered by the key read
    # from committed evidence and reconciled WITHOUT any repost.
    repo = _active_env(tmp_path, monkeypatch)
    key = lane.entry_client_key()
    _commit_presubmission(repo, key)  # pre-submission committed; the process then "crashed"
    rows = [
        {
            "side": "Buy",
            "execQty": "0.006",
            "execValue": "15",
            "execFee": "0",
            "feeCurrency": "USDT",
            "execId": "e1",
            "execTime": "1",
            "orderId": "O",
            "leavesQty": "0",
        }
    ]
    venue = ActiveVenue(rows, realtime_status="PartiallyFilledCanceled", repo_root=repo)
    lane_base, entry_price, _state = lane.recover_unresolved_entry(
        {"lane_base": "0"}, "k", "s", venue.get, repo_root=repo
    )
    assert venue.create_posts == 0  # reconcile-by-committed-key reposts NOTHING
    assert lane_base == Decimal("0.006") and entry_price == Decimal("2500")


def test_active_risk_reduction_ambiguous_result_leaves_pending_no_second_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-A: a non-terminal ("New") reconciliation must NOT fabricate FILLED. The pending stays, and
    # a subsequent call issues NO second create POST.
    repo = _active_env(tmp_path, monkeypatch)
    state = _seed_open_episode(repo, "0.25")
    venue = ActiveVenue([_ENTRY_ROW], realtime_status="New", repo_root=repo)
    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    action, state = lane.active_risk_reduction(
        sell, "EXIT_CREATE", state, "k", "s",
        get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None, repo_root=repo,
    )  # fmt: skip
    assert venue.create_posts == 1 and action is not None
    pending = state["stage_b_v2"]["pending_risk_reduction"]
    assert pending is not None and pending["phase"] in {"POST_UNKNOWN", "ACK_PENDING"}
    assert pending["terminal_status"] is None  # NOT fabricated FILLED
    action2, state2 = lane.active_risk_reduction(
        sell, "EXIT_CREATE", state, "k", "s",
        get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None, repo_root=repo,
    )  # fmt: skip
    assert action2 is None and venue.create_posts == 1  # no duplicate create


def test_risk_reduction_malformed_create_response_after_send_stays_post_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING K1: a create whose POST was SENT but returns non-JSON bytes raises JSONDecodeError (a
    # ValueError subclass) AFTER the send. The narrow LocalRejection catch must NOT swallow it as a
    # no_send: the exception propagates, POST_UNKNOWN (persisted BEFORE the send) is NOT cleared,
    # recovery/next cycle reconciles query-only without a second create POST.
    repo = _active_env(tmp_path, monkeypatch)
    state = _seed_open_episode(repo, "0.25")
    venue = ActiveVenue([_ENTRY_ROW], realtime_status="New")
    posts: list[str] = []

    def malformed_post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        posts.append(url)  # the create reached the venue
        return b"<html>502 Bad Gateway</html>"

    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    with pytest.raises(ValueError):  # JSONDecodeError propagates; NOT swallowed as no_send
        lane.active_risk_reduction(
            sell, "EXIT_CREATE", state, "k", "s",
            get_transport=venue.get, post_transport=malformed_post, sleep=lambda _s: None,
            repo_root=repo,
        )  # fmt: skip
    assert len(posts) == 1  # the create WAS sent
    persisted = json.loads(lane.LANE_STATE.read_text())
    pending = persisted["stage_b_v2"]["pending_risk_reduction"]
    assert pending is not None and pending["phase"] == "POST_UNKNOWN"  # NOT cleared/rolled back
    # Recovery is query-only (realtime "New" is non-terminal) -> no second create POST.
    stayed = lane.recover_unresolved_risk_reduction(persisted, "k", "s", venue.get, repo_root=repo)
    assert stayed["stage_b_v2"]["pending_risk_reduction"]["phase"] == "POST_UNKNOWN"
    assert venue.create_posts == 0
    # A fresh cycle refuses to start a second create while the prior attempt is unresolved.
    action2, _s2 = lane.active_risk_reduction(
        sell, "EXIT_CREATE", stayed, "k", "s",
        get_transport=venue.get, post_transport=malformed_post, sleep=lambda _s: None,
        repo_root=repo,
    )  # fmt: skip
    assert action2 is None and len(posts) == 1  # no second create POST


def test_risk_reduction_malformed_wallet_after_ack_stays_post_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING K2: a create ACCEPTED by the venue (retCode==0) whose post-order wallet response has a
    # malformed balance drives a _delta ValueError AFTER the send. Same invariant as K1: not a
    # as no_send, POST_UNKNOWN not cleared, no duplicate create.
    repo = _active_env(tmp_path, monkeypatch)
    state = _seed_open_episode(repo, "0.25")

    class _MalformedWalletVenue(ActiveVenue):
        def get(self, url: str, headers: dict[str, str]) -> bytes:
            if "/v5/account/wallet-balance" in url:
                coins = [
                    {"coin": "ETH", "walletBalance": "not-a-number"},
                    {"coin": "USDT", "walletBalance": "1000"},
                ]
                return json.dumps({"retCode": 0, "result": {"list": [{"coin": coins}]}}).encode()
            return super().get(url, headers)

    venue = _MalformedWalletVenue([_ENTRY_ROW], realtime_status="New")
    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    with pytest.raises(ValueError):  # _delta parse fails AFTER retCode==0; NOT a no_send
        lane.active_risk_reduction(
            sell, "EXIT_CREATE", state, "k", "s",
            get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
            repo_root=repo,
        )  # fmt: skip
    assert venue.create_posts == 1  # the create WAS accepted by the venue
    persisted = json.loads(lane.LANE_STATE.read_text())
    pending = persisted["stage_b_v2"]["pending_risk_reduction"]
    assert pending is not None and pending["phase"] == "POST_UNKNOWN"  # NOT cleared/rolled back
    stayed = lane.recover_unresolved_risk_reduction(persisted, "k", "s", venue.get, repo_root=repo)
    assert stayed["stage_b_v2"]["pending_risk_reduction"]["phase"] == "POST_UNKNOWN"
    assert venue.create_posts == 1  # recovery query-only -> no second create POST


def test_risk_reduction_presend_rejections_roll_back_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING K3 (regression guard): deterministic pre-send rejections still roll the reservation
    # back to a clean, non-frozen state so a routine reject never freezes future risk reduction —
    # the SELL_MAX_NOTIONAL cap (now a LocalRejection) and a stage-based no-send (kill switch).
    repo = _active_env(tmp_path, monkeypatch)

    # (a) SELL_MAX_NOTIONAL cap -> LocalRejection -> no_send -> pending cleared, no POST.
    over_cap_sell = lane.LaneIntent(
        "Sell", Decimal("2"), "baseCoin", "EXIT", "EXIT_LONG"
    )  # 2*100>120
    over_cap = ActiveVenue([_ENTRY_ROW], realtime_status="New")
    action_a, state_a = lane.active_risk_reduction(
        over_cap_sell, "EXIT_CREATE", _seed_open_episode(repo, "2"), "k", "s",
        get_transport=over_cap.get, post_transport=over_cap.post, sleep=lambda _s: None,
        repo_root=repo,
    )  # fmt: skip
    assert over_cap.create_posts == 0 and action_a is None  # raised cap -> no POST, no record
    assert state_a["stage_b_v2"]["pending_risk_reduction"] is None  # rolled back, not frozen
    assert json.loads(lane.LANE_STATE.read_text())["stage_b_v2"]["pending_risk_reduction"] is None

    # (b) kill switch -> stage-based no-send -> pending cleared, no POST, ledger record returned.
    lane.KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
    lane.KILL_SWITCH.write_text("stop")
    ok_sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    ks_venue = ActiveVenue([_ENTRY_ROW], realtime_status="New")
    action_b, state_b = lane.active_risk_reduction(
        ok_sell, "EXIT_CREATE", _seed_open_episode(repo, "0.25"), "k", "s",
        get_transport=ks_venue.get, post_transport=ks_venue.post, sleep=lambda _s: None,
        repo_root=repo,
    )  # fmt: skip
    assert ks_venue.create_posts == 0
    assert action_b is not None and action_b["stage"] == "kill_switch"
    assert state_b["stage_b_v2"]["pending_risk_reduction"] is None  # cleared, next create allowed


def test_recover_unresolved_risk_reduction_queries_terminal_without_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P0-D: an unresolved POST_UNKNOWN risk reduction is reconciled query-only next cycle; a genuine
    # terminal status clears it, a non-terminal one leaves it — never a duplicate create.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch,
        subject_intent_event_id="evt_" + "a" * 64,
        action_kind="EXIT_CREATE",
        sequence=1,
        payload={
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "0.25",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "order_filter": "Order",
            "target_order_alias": None,
        },
    )
    pending["phase"] = "POST_UNKNOWN"
    frozen = {
        "lane_base": "0.25",
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 1,
            "pending_risk_reduction": pending,
            "evidence_state": "READY",
        },
    }
    non_terminal = ActiveVenue([_ENTRY_ROW], realtime_status="New")
    stayed = lane.recover_unresolved_risk_reduction(
        frozen, "k", "s", non_terminal.get, repo_root=repo
    )
    assert stayed["stage_b_v2"]["pending_risk_reduction"]["phase"] == "POST_UNKNOWN"
    assert non_terminal.create_posts == 0  # query-only, never reposts
    terminal = ActiveVenue([_ENTRY_ROW], realtime_status="Filled")
    cleared = lane.recover_unresolved_risk_reduction(frozen, "k", "s", terminal.get, repo_root=repo)
    assert cleared["stage_b_v2"]["pending_risk_reduction"] is None
    assert terminal.create_posts == 0


def test_active_run_cycle_recovers_and_surfaces_stage_b_in_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P1-G (focused): a full run_cycle on the ACTIVE branch (stage_b_active True via the activated
    # repo) selects the recovery path, reconciles an unresolved risk reduction query-only, and
    # surfaces the Stage B latch in the heartbeat. No duplicate create.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch,
        subject_intent_event_id="evt_" + "a" * 64,
        action_kind="EXIT_CREATE",
        sequence=1,
        payload={
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "0.25",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "order_filter": "Order",
            "target_order_alias": None,
        },
    )
    pending["phase"] = "POST_UNKNOWN"
    lane.write_state(
        {
            "lane_base": "0",
            "cursor": None,
            "stage_b_v2": {
                "open_episode_event_id": "evt_" + "a" * 64,
                "risk_reduction_sequence": 1,
                "pending_risk_reduction": pending,
                "evidence_state": "READY",
            },
        }
    )
    venue = ActiveVenue(
        [_ENTRY_ROW], realtime_status="Filled", repo_root=repo, closes=_flat_history()
    )
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        heartbeat = lane.run_cycle(
            "k",
            "s",
            get_transport=venue.get,
            post_transport=venue.post,
            sleep=lambda _s: None,
            capability=cap,
        )
    assert "stage_b" in heartbeat and heartbeat["stage_b"]["evidence_state"] == "READY"
    assert venue.create_posts == 0  # recovery is query-only; the flat cycle places no order
    persisted = json.loads(lane.LANE_STATE.read_text())
    assert persisted["stage_b_v2"]["pending_risk_reduction"] is None  # terminal -> cleared


# --- P1-B: protective-stop / cancel durability wiring -----------------------------------------


def test_cancel_target_payload_placeholder_fails_closed() -> None:
    # The typed CANCEL_TARGET placeholder is MARKET / qty 0 / null trigger; anything else is a
    # create smuggled in as a cancel and must fail closed.
    for bad in (
        {"order_type": "STOP_MARKET"},
        {"qty": "0.01"},
        {"trigger_price": "85"},
    ):
        payload = {
            "side": "SELL", "order_type": "MARKET", "qty": "0", "quantity_unit": "BASE",
            "trigger_price": None, "order_filter": "StopOrder", "target_order_alias": TARGET_ORD,
        }  # fmt: skip
        payload.update(bad)
        with pytest.raises(ValueError, match="placeholder"):
            lane.build_pending_risk_reduction(
                activation_epoch=EPOCH, subject_intent_event_id=INTENT,
                action_kind="CANCEL_TARGET", sequence=1, payload=payload,
            )  # fmt: skip


class StopVenue:
    """Serves ACTIVE reconciliation endpoints AND venue-stop identity rows (create + cancel)."""

    def __init__(self, *, closes: list[tuple[str, str]] | None = None) -> None:
        self.closes = closes or _flat_history()
        self.balances = {"USDT": Decimal("1000"), "ETH": Decimal("0.25")}
        self.create_posts = 0
        self.created: list[dict[str, Any]] = []
        self.stops: dict[str, dict[str, Any]] = {}  # orderId -> echoed identity row
        self.links: dict[str, str] = {}  # orderLinkId -> orderId
        self.cancelled: set[str] = set()

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        query = parse_qs(urlsplit(url).query)
        link = query.get("orderLinkId", [None])[0]
        oid = query.get("orderId", [""])[0]
        if "/v5/market/kline" in url:
            return json.dumps(
                {"result": {"list": list(reversed(_kline_rows(self.closes)))}}
            ).encode()
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
            coins = [{"coin": k, "walletBalance": str(v)} for k, v in self.balances.items()]
            return json.dumps({"retCode": 0, "result": {"list": [{"coin": coins}]}}).encode()
        if "/v5/order/realtime" in url:
            if link is not None:  # reconciliation by original client key
                target = self.links.get(link)
                rows = (
                    []
                    if target is None
                    else [
                        {
                            "orderId": target,  # Bybit rows carry the venue orderId
                            "orderLinkId": link,
                            "orderStatus": "Cancelled"
                            if target in self.cancelled
                            else "Untriggered",
                        }
                    ]
                )
                return json.dumps({"result": {"list": rows, "nextPageCursor": ""}}).encode()
            if oid in self.cancelled:
                return json.dumps(
                    {"result": {"list": [{"orderId": oid, "orderStatus": "Cancelled"}]}}
                ).encode()
            if oid in self.stops:
                return json.dumps(
                    {
                        "result": {
                            "list": [
                                {"orderId": oid, "orderStatus": "Untriggered", **self.stops[oid]}
                            ]
                        }
                    }
                ).encode()
            return json.dumps(
                {
                    "result": {
                        "list": [
                            {
                                "orderId": oid,
                                "orderStatus": "Filled",
                                "avgPrice": "100",
                                "cumExecQty": "0.25",
                                "cumExecFee": "0.001",
                            }
                        ]
                    }
                }
            ).encode()
        if "/v5/order/history" in url or "/v5/execution/list" in url:
            return json.dumps({"result": {"list": [], "nextPageCursor": ""}}).encode()
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url: str, headers: dict[str, str], body: bytes) -> bytes:
        order = json.loads(body)
        if "/v5/order/cancel" in url:
            if order.get("orderId"):
                self.cancelled.add(str(order["orderId"]))
            return json.dumps({"retCode": 0, "result": {}}).encode()
        assert "/v5/order/create" in url
        self.create_posts += 1
        self.created.append(order)
        oid = f"S{self.create_posts}"
        if order.get("orderFilter") == "StopOrder":
            self.stops[oid] = {
                "symbol": order["symbol"],
                "side": order["side"],
                "orderType": order["orderType"],
                "stopOrderType": "Stop",
                "triggerDirection": 0,
                "marketUnit": "baseCoin",
                "triggerPrice": order["triggerPrice"],
                "qty": order["qty"],
            }
            if order.get("orderLinkId"):
                self.links[str(order["orderLinkId"])] = oid
        return json.dumps({"retCode": 0, "result": {"orderId": oid}}).encode()


def _open_stage_b_state(order_id: str | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "lane_base": "0.25",
        "cursor": None,
        "resting_stop": None,
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 0,
            "evidence_state": "READY",
        },
    }
    if order_id is not None:
        state["resting_stop"] = {
            "state": "ACTIVE",
            "order_id": order_id,
            "trigger_price": "85.00",
            "base_qty": "0.25",
        }
    return state


def test_active_stop_decision_place_persists_key_before_post_and_clears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # STOP_CREATE: the deterministic key is reserved+persisted before the one keyed stop POST, the
    # confirmed resting stop resolves the pending, and no raw key lands in lane state.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    resting, state = lane.active_stop_decision(
        "place", None, Decimal("0.25"), Decimal("100"), _open_stage_b_state(), "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert venue.create_posts == 1
    stop = venue.created[0]
    assert stop["orderFilter"] == "StopOrder" and stop["orderLinkId"].startswith("tios2_r_")
    assert isinstance(resting, dict) and resting["state"] == "ACTIVE"
    assert state["stage_b_v2"]["pending_risk_reduction"] is None  # confirmed resting -> cleared
    assert state["stage_b_v2"]["risk_reduction_sequence"] == 1
    assert "tios2_r_" not in lane.LANE_STATE.read_text()  # only the key hash is ever persisted


def test_active_stop_decision_replace_posts_one_keyed_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    venue.stops["OLD"] = {"symbol": "ETHUSDT", "side": "Sell", "qty": "0.25", "triggerPrice": "80"}
    state = _open_stage_b_state("OLD")
    resting, state = lane.active_stop_decision(
        "replace", state["resting_stop"], Decimal("0.25"), Decimal("100"), state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    creates = [o for o in venue.created if o.get("orderFilter") == "StopOrder"]
    assert len(creates) == 1 and creates[0]["orderLinkId"].startswith("tios2_r_")
    assert "OLD" in venue.cancelled  # old stop cancelled by its ORIGINAL orderId
    assert isinstance(resting, dict) and resting["state"] == "ACTIVE"
    assert state["stage_b_v2"]["pending_risk_reduction"] is None


def test_active_stop_decision_cancel_uses_original_correlation_no_new_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CANCEL_TARGET derives NO client key; it cancels by the tracked venue orderId (original
    # correlation) after a fresh status query, and never issues a new keyed create.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    venue.stops["OLD"] = {"symbol": "ETHUSDT", "side": "Sell", "qty": "0.25", "triggerPrice": "85"}
    state = _open_stage_b_state("OLD")
    state["lane_base"] = "0"  # flat -> the resting stop should be cancelled
    resting, state = lane.active_stop_decision(
        "cancel", state["resting_stop"], Decimal("0"), None, state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=None, qty_step=None,
    )  # fmt: skip
    assert venue.create_posts == 0  # never a duplicate/guessed create
    assert "OLD" in venue.cancelled and resting is None
    assert state["stage_b_v2"]["pending_risk_reduction"] is None


def test_active_stop_decision_prior_unresolved_suppresses_new_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unresolved prior attempt blocks a new stop create (query/recovery-only) — no blind dup.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    state = _open_stage_b_state()
    state["stage_b_v2"]["pending_risk_reduction"] = {
        "phase": "POST_UNKNOWN",
        "action_kind": "EXIT_CREATE",
    }
    resting, _state = lane.active_stop_decision(
        "place", None, Decimal("0.25"), Decimal("100"), state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert venue.create_posts == 0 and resting is None


def test_active_stop_decision_substep_quantize_falls_back_no_frozen_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING J1: quantize_stop_qty_down raising LocalRejection (lane_base below the qty step) is a
    # deterministic pre-send rejection. active_stop_decision must NOT let it escape (that would
    # crash the lane loop) and must NOT leave a frozen POST_UNKNOWN reservation: it falls back to
    # the legacy compensating control BEFORE reserving anything.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    state = _open_stage_b_state()
    state["lane_base"] = "0.000001"  # below the 0.00001 qty step -> quantize LocalRejection
    resting, new_state = lane.active_stop_decision(
        "place", None, Decimal("0.000001"), Decimal("100"), state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert venue.create_posts == 0  # no stop POST issued
    assert resting is None  # compensating control placed nothing for a sub-step position
    latch = new_state["stage_b_v2"]
    assert latch.get("pending_risk_reduction") is None  # NO frozen POST_UNKNOWN reservation
    assert latch.get("risk_reduction_sequence") == 0  # nothing was reserved


def test_active_stop_decision_replace_postsend_failure_stays_post_unknown_no_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING L: a replace whose keyed stop-create POST reaches the venue but returns malformed JSON
    # is a POST-SEND ambiguous outcome. apply_stop_decision swallows the JSONDecodeError and returns
    # the STALE prior ACTIVE resting record UNCHANGED. The durability pending must NOT be cleared by
    # trusting that stale record (the new create's outcome is genuinely unknown): it stays
    # POST_UNKNOWN for the query-only recover sweep, and a subsequent cycle issues NO second create.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    venue.stops["OLD"] = {"symbol": "ETHUSDT", "side": "Sell", "qty": "0.25", "triggerPrice": "80"}
    creates: list[bytes] = []

    def malformed_post(url: str, headers: dict[str, str], body: bytes) -> bytes:
        if "/v5/order/create" in url:
            creates.append(body)  # the create reached the venue
            return b"<html>502 Bad Gateway</html>"  # non-JSON -> json.loads raises after the send
        return venue.post(url, headers, body)  # cancels still work

    state = _open_stage_b_state("OLD")
    resting, state = lane.active_stop_decision(
        "replace", state["resting_stop"], Decimal("0.25"), Decimal("100"), state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=malformed_post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert len(creates) == 1  # the create WAS sent
    pending = state["stage_b_v2"]["pending_risk_reduction"]
    assert pending is not None and pending["phase"] == "POST_UNKNOWN"  # NOT cleared by stale record
    assert isinstance(resting, dict) and resting["order_id"] == "OLD"  # old stop still tracked
    # A subsequent cycle refuses a second create while the prior attempt is unresolved.
    resting2, _s2 = lane.active_stop_decision(
        "replace", resting, Decimal("0.25"), Decimal("100"), state, "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=malformed_post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert len(creates) == 1  # NO second create POST (prior_unresolved guard)


class _NoStepVenue(ActiveVenue):
    """ACTIVE venue with malformed instruments-info, so instrument_qty_step raises ValueError."""

    def get(self, url: str, headers: dict[str, str]) -> bytes:
        if "/v5/market/instruments-info" in url:
            return json.dumps({"result": {"list": [{}]}}).encode()  # missing lotSizeFilter
        return super().get(url, headers)


def test_active_exit_presend_metadata_error_freezes_post_unknown_no_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PRE-ACTIVATION DEBT (characterization): place()'s exit/Sell branch calls instrument_qty_step,
    # which raises PLAIN ValueError (not LocalRejection). do_post catches only LocalRejection, so it
    # propagates AFTER POST_UNKNOWN was durably persisted -> the reservation FREEZES query-only
    # (accepted debt). run_cycle must degrade to that frozen state WITHOUT an uncaught traceback and
    # WITHOUT a duplicate create. Pins the current fail-safe behavior so it is characterized.
    repo = _active_env(tmp_path, monkeypatch)
    lane.write_state(
        {
            "lane_base": "0.25",
            "cursor": "2099-01-01T00:00:00+00:00",  # far future -> no fresh signal fires
            "entry_price": "200",  # mark 100 <= -15% stop (170) -> disaster exit fires
            "resting_stop": None,
            "stage_b_v2": {
                "open_episode_event_id": "evt_" + "a" * 64,
                "risk_reduction_sequence": 0,
                "evidence_state": "READY",
            },
        }
    )
    venue = _NoStepVenue([_ENTRY_ROW], realtime_status="New", closes=_flat_history())
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        heartbeat = lane.run_cycle(  # must NOT raise
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip
    assert venue.create_posts == 0  # pre-send failure: no create POST reached the venue
    persisted = json.loads(lane.LANE_STATE.read_text())
    pending = persisted["stage_b_v2"]["pending_risk_reduction"]
    assert pending is not None and pending["phase"] == "POST_UNKNOWN"  # frozen, not rolled back
    assert lane.entry_blocked(persisted) is True  # the frozen attempt blocks new entries
    assert heartbeat["stage_b"]["risk_reduction_phase"] == "POST_UNKNOWN"


def test_recover_unresolved_stop_create_resolves_on_confirmed_resting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A dangling STOP_CREATE (crash after POST_UNKNOWN) is reconciled by key next cycle: a confirmed
    # resting stop resolves it (no terminal status), never a duplicate create.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch, subject_intent_event_id="evt_" + "a" * 64,
        action_kind="STOP_CREATE", sequence=1, payload=_payload_for("STOP_CREATE"),
    )  # fmt: skip
    pending["phase"] = "POST_UNKNOWN"
    key = lane.pending_client_key(pending, epoch)
    venue = StopVenue()
    venue.links[key] = "S1"
    venue.stops["S1"] = {}  # resting (Untriggered) -> resolves the create
    frozen = {
        "lane_base": "0.25",
        "resting_stop": None,
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 1,
            "pending_risk_reduction": pending,
            "evidence_state": "READY",
        },
    }
    cleared = lane.recover_unresolved_risk_reduction(frozen, "k", "s", venue.get, repo_root=repo)
    assert cleared["stage_b_v2"]["pending_risk_reduction"] is None
    assert venue.create_posts == 0


def test_recover_unresolved_stop_create_restores_resting_stop_no_second_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FINDING M: recovery-confirming a resting STOP_CREATE must RESTORE resting_stop (tracked), not
    # just clear the pending. Otherwise the next cycle sees resting_stop=None, stop_reconcile_action
    # returns "place", and a SECOND stop-create POST duplicates the protective stop.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    payload = {
        "side": "SELL", "order_type": "STOP_MARKET", "qty": "0.25", "quantity_unit": "BASE",
        "trigger_price": "85", "order_filter": "StopOrder", "target_order_alias": None,
    }  # fmt: skip  # trigger/qty match lane_base 0.25 @ entry 100 (-15% = 85) -> next cycle noop
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch, subject_intent_event_id="evt_" + "a" * 64,
        action_kind="STOP_CREATE", sequence=1, payload=payload,
    )  # fmt: skip
    pending["phase"] = "POST_UNKNOWN"
    key = lane.pending_client_key(pending, epoch)
    venue = StopVenue()
    venue.links[key] = "S1"  # the recovery reconciles the new stop to venue orderId S1
    venue.stops["S1"] = {  # full identity so the next cycle confirms it active and stays a noop
        "symbol": "ETHUSDT", "side": "Sell", "orderType": "Market", "stopOrderType": "Stop",
        "triggerDirection": 0, "marketUnit": "baseCoin", "triggerPrice": "85", "qty": "0.25",
    }  # fmt: skip
    frozen = {
        "lane_base": "0.25",
        "cursor": "2099-01-01T00:00:00+00:00",
        "entry_price": "100",
        "resting_stop": None,
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 1,
            "pending_risk_reduction": pending,
            "evidence_state": "READY",
        },
    }
    cleared = lane.recover_unresolved_risk_reduction(frozen, "k", "s", venue.get, repo_root=repo)
    assert cleared["stage_b_v2"]["pending_risk_reduction"] is None
    assert venue.create_posts == 0
    restored = cleared["resting_stop"]  # Finding M: the recovered stop is now tracked, not None
    assert restored is not None and restored["order_id"] == "S1" and restored["state"] == "ACTIVE"
    assert restored["trigger_price"] == "85" and restored["base_qty"] == "0.25"
    # The next full cycle sees the tracked stop and issues NO second stop-create POST (idempotent).
    lane.write_state(cleared)
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        lane.run_cycle(
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip
    creates = [o for o in venue.created if o.get("orderFilter") == "StopOrder"]
    assert creates == []  # no duplicate stop-create POST


def test_run_cycle_recovers_stop_create_in_cycle_no_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BLOCKER 1: recovery runs INSIDE run_cycle. It restores state["resting_stop"], and the LOCAL
    # resting_stop must re-sync too -- else stop_reconcile_action sees a stale None and re-places a
    # stop already resting on the venue (a second create POST for one logical submission). Unlike
    # the M unit test above, this seeds the UNRESOLVED (POST_UNKNOWN) state and lets run_cycle do
    # the recovery-then-reconcile in one invocation.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    payload = {
        "side": "SELL", "order_type": "STOP_MARKET", "qty": "0.25", "quantity_unit": "BASE",
        "trigger_price": "85", "order_filter": "StopOrder", "target_order_alias": None,
    }  # fmt: skip  # trigger/qty match lane_base 0.25 @ entry 100 (-15% = 85) -> noop
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch, subject_intent_event_id="evt_" + "a" * 64,
        action_kind="STOP_CREATE", sequence=1, payload=payload,
    )  # fmt: skip
    pending["phase"] = "POST_UNKNOWN"
    key = lane.pending_client_key(pending, epoch)
    venue = StopVenue()
    venue.links[key] = "S1"  # recovery reconciles the in-flight stop to venue orderId S1
    venue.stops["S1"] = {
        "symbol": "ETHUSDT", "side": "Sell", "orderType": "Market", "stopOrderType": "Stop",
        "triggerDirection": 0, "marketUnit": "baseCoin", "triggerPrice": "85", "qty": "0.25",
    }  # fmt: skip
    frozen = {
        "lane_base": "0.25",
        "cursor": "2099-01-01T00:00:00+00:00",
        "entry_price": "100",
        "resting_stop": None,
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 1,
            "pending_risk_reduction": pending,
            "evidence_state": "READY",
        },
    }
    lane.write_state(frozen)  # seed the UNRESOLVED state; run_cycle performs recovery itself
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        lane.run_cycle(
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip
    creates = [o for o in venue.created if o.get("orderFilter") == "StopOrder"]
    assert creates == []  # no duplicate stop-create POST despite in-cycle recovery
    final = lane.read_state()
    assert final["stage_b_v2"]["pending_risk_reduction"] is None  # recovery cleared it
    assert final["resting_stop"] is not None and final["resting_stop"]["order_id"] == "S1"


def test_restore_recovered_resting_stop_declines_on_malformed_row_no_clear() -> None:
    # BLOCKER 2: when the reconciled venue row lacks a canonical orderId (or the payload a positive
    # trigger/qty), _restore_recovered_resting_stop returns None so the caller keeps the pending
    # unresolved (prior_unresolved guard blocks a blind second create) instead of clearing an
    # untracked stop.
    payload = {
        "side": "SELL", "order_type": "STOP_MARKET", "qty": "0.25", "quantity_unit": "BASE",
        "trigger_price": "85", "order_filter": "StopOrder", "target_order_alias": None,
    }  # fmt: skip
    pending = {"payload": payload, "phase": "POST_UNKNOWN"}
    st = {"resting_stop": None}
    assert lane._restore_recovered_resting_stop(st, pending, {"orderId": ""}) is None
    bad = {"payload": {**payload, "trigger_price": None}, "phase": "POST_UNKNOWN"}
    assert lane._restore_recovered_resting_stop(st, bad, {"orderId": "S1"}) is None
    good = lane._restore_recovered_resting_stop(st, pending, {"orderId": "S1"})
    assert good is not None and good["resting_stop"]["order_id"] == "S1"


def test_recover_unresolved_cancel_target_resolves_by_original_orderid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CANCEL_TARGET has no key: recovery re-confirms the tracked stop by its ORIGINAL orderId; a
    # cleared target resolves the pending.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    payload = {
        "side": "SELL", "order_type": "MARKET", "qty": "0", "quantity_unit": "BASE",
        "trigger_price": None, "order_filter": "StopOrder", "target_order_alias": TARGET_ORD,
    }  # fmt: skip
    pending = lane.build_pending_risk_reduction(
        activation_epoch=epoch, subject_intent_event_id="evt_" + "a" * 64,
        action_kind="CANCEL_TARGET", sequence=1, payload=payload,
    )  # fmt: skip
    pending["phase"] = "POST_UNKNOWN"
    venue = StopVenue()
    venue.cancelled.add("OLD")  # the tracked stop is confirmed cleared
    frozen = {
        "lane_base": "0",
        "resting_stop": {
            "state": "ACTIVE",
            "order_id": "OLD",
            "trigger_price": "85",
            "base_qty": "0.25",
        },
        "stage_b_v2": {
            "open_episode_event_id": "evt_" + "a" * 64,
            "risk_reduction_sequence": 1,
            "pending_risk_reduction": pending,
            "evidence_state": "READY",
        },
    }
    cleared = lane.recover_unresolved_risk_reduction(frozen, "k", "s", venue.get, repo_root=repo)
    assert cleared["stage_b_v2"]["pending_risk_reduction"] is None
    assert venue.create_posts == 0


def test_active_run_cycle_places_durable_venue_stop_and_surfaces_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P1-G: a full run_cycle on the ACTIVE branch routes the protective-stop create through the
    # durability protocol (one keyed POST), confirms it resting (pending cleared), surfaces the
    # Stage B latch in the heartbeat, and is idempotent (no duplicate stop next cycle).
    repo = _active_env(tmp_path, monkeypatch)
    venue = StopVenue()
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        lane.run_cycle(
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip  # arm the cursor
    armed = json.loads(lane.LANE_STATE.read_text())
    lane.write_state(
        {
            **armed,
            "lane_base": "0.25",
            "entry_price": "100",
            "resting_stop": None,
            "stage_b_v2": {
                "open_episode_event_id": "evt_" + "a" * 64,
                "risk_reduction_sequence": 0,
                "evidence_state": "READY",
            },
        }
    )
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        heartbeat = lane.run_cycle(
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip
    stops = [o for o in venue.created if o.get("orderFilter") == "StopOrder"]
    assert len(stops) == 1 and stops[0]["orderLinkId"].startswith("tios2_r_")
    assert heartbeat["resting_stop"]["state"] == "ACTIVE"
    assert heartbeat["stage_b"]["evidence_state"] == "READY"
    persisted = json.loads(lane.LANE_STATE.read_text())
    assert persisted["stage_b_v2"]["pending_risk_reduction"] is None  # confirmed resting -> cleared
    # Second cycle: the stop already matches -> noop, no duplicate create.
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        lane.run_cycle(
            "k", "s", get_transport=venue.get, post_transport=venue.post,
            sleep=lambda _s: None, capability=cap,
        )  # fmt: skip
    stops2 = [o for o in venue.created if o.get("orderFilter") == "StopOrder"]
    assert len(stops2) == 1  # idempotent: the durability wrapper did not re-create the stop


# --- Finding I: a place() local no-send must roll back the reservation, never freeze it ---------


def test_execute_risk_reduction_local_no_send_rolls_back_not_frozen(lane_dirs: Path) -> None:
    # A do_post that proves a deterministic no-send must leave the pending CLEARED (non-frozen),
    # unlike an ambiguous send which stays POST_UNKNOWN — and it must not block the next reduction.
    state, _pending = _reserved_state("EXIT_CREATE")
    posts = {"n": 0}

    def no_send() -> dict[str, Any]:
        posts["n"] += 1
        return {"retCode": 1, "no_send": True}

    state, res = lane.execute_risk_reduction_create(state, no_send, lambda: {"queried": True})
    assert posts["n"] == 1 and res.get("no_send")
    assert state["stage_b_v2"]["pending_risk_reduction"] is None  # rolled back, NOT frozen
    # A fresh reserve+execute is not blocked and issues exactly one POST.
    state2, _p2 = _reserved_state("EXIT_CREATE")
    ok = {"n": 0}

    def good() -> dict[str, Any]:
        ok["n"] += 1
        return {"retCode": 0, "result": {"orderId": "X"}}

    lane.execute_risk_reduction_create(state2, good, lambda: {"queried": True})
    assert ok["n"] == 1


def _rr_exit(
    state: dict[str, Any], intent: lane.LaneIntent, venue: ActiveVenue, repo: Path
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return lane.active_risk_reduction(
        intent, "EXIT_CREATE", state, "k", "s",
        get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None, repo_root=repo,
    )  # fmt: skip


def test_active_risk_reduction_kill_switch_no_send_not_frozen_and_next_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _active_env(tmp_path, monkeypatch)
    lane.KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
    lane.KILL_SWITCH.write_text("stop")
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    state = _seed_open_episode(repo, "0.25")
    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    action, state = _rr_exit(state, sell, venue, repo)  # must NOT raise
    assert venue.create_posts == 0 and action is not None and action["stage"] == "kill_switch"
    assert state["stage_b_v2"]["pending_risk_reduction"] is None  # rolled back, not frozen
    # A subsequent legitimate risk-reducing create is NOT blocked and posts exactly once.
    lane.KILL_SWITCH.unlink()
    action2, state2 = _rr_exit(state, sell, venue, repo)
    assert venue.create_posts == 1 and action2 is not None and action2.get("order_id")
    assert state2["stage_b_v2"]["pending_risk_reduction"] is None  # terminal Filled -> cleared


def test_active_risk_reduction_sell_notional_cap_valueerror_caught_not_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _active_env(tmp_path, monkeypatch)
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    state = _seed_open_episode(repo, "2")
    big = lane.LaneIntent("Sell", Decimal("2"), "baseCoin", "EXIT", "EXIT_LONG")  # 200 USDT > 120
    action, state = _rr_exit(state, big, venue, repo)  # ValueError must be caught, not propagate
    assert venue.create_posts == 0 and action is None
    assert state["stage_b_v2"]["pending_risk_reduction"] is None
    ok_sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    action2, _s = _rr_exit(state, ok_sell, venue, repo)
    assert venue.create_posts == 1 and action2 is not None


def test_active_risk_reduction_dust_and_price_unavailable_not_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _active_env(tmp_path, monkeypatch)
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    # Dust below the instrument step -> place() stage 'qty_below_step' (pre-send local reject).
    dust = lane.LaneIntent("Sell", Decimal("0.000009"), "baseCoin", "EXIT", "EXIT_LONG")
    action, state = _rr_exit(_seed_open_episode(repo, "0.000009"), dust, venue, repo)
    assert venue.create_posts == 0 and action is not None and action["stage"] == "qty_below_step"
    assert state["stage_b_v2"]["pending_risk_reduction"] is None
    # An unavailable mark -> place() stage 'price_unavailable' (pre-send local reject).
    monkeypatch.setattr(lane, "last_price", lambda _t, _s=lane.SYMBOL: Decimal("0"))
    sell = lane.LaneIntent("Sell", Decimal("0.25"), "baseCoin", "EXIT", "EXIT_LONG")
    action2, state2 = _rr_exit(_seed_open_episode(repo, "0.25"), sell, venue, repo)
    assert venue.create_posts == 0 and action2 is not None
    assert action2["stage"] == "price_unavailable"
    assert state2["stage_b_v2"]["pending_risk_reduction"] is None


# --- Finding H: no intermediate durable write may drop a real position or orphan a stop ---------


def _commit_attempted_entry(repo: Path, key: str) -> str:
    """Commit a full entry pre-submission + SUBMISSION_ATTEMPTED chain; return the intent id."""
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        activation = stage_b.load_activation(repo)
        material = lane._alias_material(activation)
        sink = stage_b.StageBEvidenceSink(repo)
        events, intent_id, order_alias = lane._entry_presubmission_events(
            activation, None, material, key
        )
        snap = sink.append(events, capability=cap)
        attempt = lane._entry_attempt_events(
            activation, snap.events[-1], material, key, intent_id, order_alias, True
        )
        sink.append(attempt, capability=cap)
    return intent_id


def test_active_recovers_attempted_entry_position_from_executions_no_second_buy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Finding H(a): crash after the attempt commit (and the venue create) but BEFORE the reconciled
    # durable write -> on-disk lane_base is still 0 while the episode is anchored. Recovery must
    # reconcile the REAL position from the committed-key executions, query-only, and never re-buy.
    repo = _active_env(tmp_path, monkeypatch)
    key = lane.entry_client_key()
    intent_id = _commit_attempted_entry(repo, key)
    venue = ActiveVenue([_ENTRY_ROW], realtime_status="Filled", repo_root=repo)
    crashed = {
        "lane_base": "0",
        "cursor": None,
        "stage_b_v2": {
            "open_episode_event_id": intent_id,
            "evidence_state": "READY",
            "risk_reduction_sequence": 0,
        },
    }
    lane_base, entry_price, _s = lane.recover_unresolved_entry(
        crashed, "k", "s", venue.get, repo_root=repo
    )
    assert venue.create_posts == 0  # query-only reconciliation; never a second position
    assert lane_base == Decimal("0.25") and entry_price == Decimal("100")
    # Resurrection guard: once an exit has nulled the anchor, recovery must NOT resurrect the closed
    # position from the (immutable) entry executions.
    closed = {**crashed, "stage_b_v2": {**crashed["stage_b_v2"], "open_episode_event_id": None}}
    assert lane.recover_unresolved_entry(closed, "k", "s", venue.get, repo_root=repo)[0] is None


def test_active_entry_durable_write_carries_reconciled_lane_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Finding H(a): active_entry's durable write must persist the RECONCILED lane_base, not the
    # stale pre-entry "0" snapshot, so a crash before the end-of-cycle write cannot show flat.
    repo = _active_env(tmp_path, monkeypatch)
    venue = ActiveVenue([_ENTRY_ROW], repo_root=repo)
    with stage_b.exclusive_lane_lock_capability(repo) as cap:
        lane.active_entry(
            "SIG-1", {"lane_base": "0", "cursor": None}, "k", "s",
            get_transport=venue.get, post_transport=venue.post, sleep=lambda _s: None,
            capability=cap, repo_root=repo,
        )  # fmt: skip
    persisted = json.loads(lane.LANE_STATE.read_text())
    assert Decimal(persisted["lane_base"]) == Decimal("0.25")  # not the stale 0
    assert Decimal(persisted["entry_price"]) == Decimal("100")


def test_active_stop_decision_persists_new_stop_before_clear_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Finding H(b): the durable file a crash-immediately-after-clear_pending would leave must
    # already carry the just-created stop, so it is not orphaned/untracked next cycle.
    repo = _active_env(tmp_path, monkeypatch)
    epoch = _epoch(repo)
    venue = StopVenue()
    resting, _state = lane.active_stop_decision(
        "place", None, Decimal("0.25"), Decimal("100"), _open_stage_b_state(), "k", "s",
        epoch=epoch, get_transport=venue.get, post_transport=venue.post,
        price_tick=Decimal("0.01"), qty_step=Decimal("0.00001"),
    )  # fmt: skip
    assert isinstance(resting, dict) and resting["state"] == "ACTIVE"
    persisted = json.loads(lane.LANE_STATE.read_text())
    assert persisted["stage_b_v2"]["pending_risk_reduction"] is None
    assert persisted["resting_stop"]["order_id"] == resting["order_id"]  # not orphaned
