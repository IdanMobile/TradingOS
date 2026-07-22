"""Tests for the dashboard's demo-lane projection and bounded controls (D-106)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tios.services.dashboard_api import demo_lane


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / demo_lane.LANE_DIR).mkdir(parents=True)
    script = tmp_path / demo_lane.LANE_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# stand-in lane script\n")
    return tmp_path


def _order(**fields: object) -> str:
    base = {
        "recorded_at": "2026-07-19T01:00:00+00:00",
        "side": "Buy",
        "qty": "25",
        "unit": "quoteCoin",
        "ok": True,
        "stage": "done",
        "avg_price": "3000",
        "cum_exec_qty": "0.008",
        "fee": "0.01",
        "environment": "VENUE_DEMO",
    }
    return json.dumps({**base, **fields})


def test_projection_defaults_to_idle_and_is_labelled(root: Path) -> None:
    lane = demo_lane.build_demo_lane(root)
    assert lane["status"] == "IDLE"
    assert lane["running"] is False
    assert lane["real_money"] is False
    assert lane["validation_state"] == "UNVALIDATED"
    assert lane["promotion_eligible"] is False
    assert lane["counts"]["orders_filled"] == 0


def test_projection_reports_stopped_and_counts_fills(root: Path) -> None:
    (root / demo_lane.KILL_SWITCH).write_text("{}")
    (root / demo_lane.ORDERS_LEDGER).write_text(
        "\n".join(
            [
                _order(),
                _order(side="Sell", unit="baseCoin"),
                _order(ok=False, stage="kill_switch"),
                "not json",
            ]
        )
    )
    (root / demo_lane.LANE_STATE).write_text(json.dumps({"lane_base": "0.008", "cursor": "x"}))
    lane = demo_lane.build_demo_lane(root)
    assert lane["status"] == "STOPPED"
    assert lane["kill_switch"] is True
    assert lane["counts"] == {
        "orders_recorded": 3,
        "orders_filled": 2,
        "buys": 1,
        "sells": 1,
        "refused": 1,
    }
    assert lane["position_base"] == "0.008"
    # newest first, and refusals stay visible as evidence alongside fills
    assert lane["orders"][0]["stage"] == "kill_switch"
    assert [o["side"] for o in lane["orders"] if o["ok"]] == ["Sell", "Buy"]


def test_running_detection_follows_the_lane_lock(root: Path) -> None:
    import fcntl

    lock = root / demo_lane.LANE_LOCK
    lock.write_text(json.dumps({"pid": 4242, "started_at": "2026-07-19T01:00:00+00:00"}))
    assert demo_lane.build_demo_lane(root)["running"] is False
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        lane = demo_lane.build_demo_lane(root)
        assert lane["running"] is True and lane["status"] == "RUNNING" and lane["pid"] == 4242
    finally:
        handle.close()
    assert demo_lane.build_demo_lane(root)["running"] is False  # lock released with the handle


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "LAUNCH_LIVE", "idempotency_key": "k1"},
        {"action": "", "idempotency_key": "k1"},
        {"action": "START"},
        {"action": "START", "idempotency_key": "bad key!"},
        {"action": "START", "idempotency_key": "k1", "symbol": "BTCUSDT"},
    ],
)
def test_actions_are_allowlisted_and_closed(root: Path, payload: dict) -> None:
    with pytest.raises(demo_lane.DemoLaneActionError):
        demo_lane.perform_demo_lane_action(root, payload)


def test_stop_sets_flag_and_audits_without_a_process(root: Path) -> None:
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "STOP", "idempotency_key": "stop-1"}
    )
    assert (root / demo_lane.KILL_SWITCH).is_file()
    assert result["state"]["kill_switch"] is True
    audit = (root / demo_lane.AUDIT_PATH).read_text().splitlines()
    record = json.loads(audit[0])
    assert record["action"] == "STOP" and record["real_money"] is False


def test_start_clears_stop_flag_and_spawns_once(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (root / demo_lane.KILL_SWITCH).write_text("{}")
    spawned: list[str] = []

    class FakeProcess:
        pid = 9999

    def fake_spawn(_root: Path, mode: str) -> FakeProcess:
        spawned.append(mode)
        return FakeProcess()

    monkeypatch.setattr(demo_lane, "_spawn", fake_spawn)
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "START", "idempotency_key": "start-1"}
    )
    assert spawned == ["--loop"]
    assert not (root / demo_lane.KILL_SWITCH).exists()
    assert "9999" in result["recorded"]["detail"]


def test_start_and_run_once_refuse_while_a_lane_holds_the_lock(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl

    lock = root / demo_lane.LANE_LOCK
    lock.write_text(json.dumps({"pid": 4242}))
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr(
        demo_lane, "_spawn", lambda *_a, **_k: pytest.fail("must not spawn a second lane")
    )
    try:
        for action in ("START", "RUN_ONCE"):
            with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
                demo_lane.perform_demo_lane_action(
                    root, {"action": action, "idempotency_key": f"{action}-1"}
                )
            assert excinfo.value.status_code == 409
    finally:
        handle.close()


def test_missing_lane_script_is_unavailable_not_a_crash(root: Path) -> None:
    (root / demo_lane.LANE_SCRIPT).unlink()
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(root, {"action": "START", "idempotency_key": "k1"})
    assert excinfo.value.status_code == 503


def test_order_money_uses_reconciled_wallet_deltas(tmp_path: Path) -> None:
    """Venue before/after balances are the source of truth, not qty * price.

    The delta already accounts for however the venue charged the fee, so a derived
    notional would disagree with what actually left the wallet.
    """
    from tios.services.dashboard_api.demo_lane import _order_money

    money = _order_money(
        {
            "side": "Buy",
            "avg_price": "1862.37",
            "fee": "0.000013423755752079",
            "reconcile": {"ETH_delta": 0.01341033, "USDT_delta": -25.0},
        }
    )

    assert money["usd_spent"] == 25.0
    assert money["usd_received"] == 0.0
    assert money["base_delta"] == 0.01341033
    assert money["fee_usd"] == pytest.approx(0.025, abs=0.001)


def test_pnl_average_cost_exceeds_fill_price_when_fee_is_taken_in_base() -> None:
    """A base-coin fee means less ETH for the same USD, so effective cost is higher."""
    from tios.services.dashboard_api.demo_lane import _pnl

    pnl = _pnl(
        [
            {
                "side": "Buy",
                "avg_price": "1862.37",
                "fee": "0.000013423755752079",
                "reconcile": {"ETH_delta": 0.01341033, "USDT_delta": -25.0},
            }
        ],
        mark_price=0.0,
    )

    assert pnl["invested_usd"] == 25.0
    assert pnl["position_base"] == 0.01341033
    assert pnl["average_cost_usd"] > 1862.37


def test_unmarked_position_reports_null_not_zero_pnl() -> None:
    """Showing an unmarked position as flat would understate open risk."""
    from tios.services.dashboard_api.demo_lane import _pnl

    pnl = _pnl(
        [
            {
                "side": "Buy",
                "avg_price": "1862.37",
                "reconcile": {"ETH_delta": 0.01, "USDT_delta": -25.0},
            }
        ],
        mark_price=0.0,
    )

    assert pnl["marked"] is False
    assert pnl["total_pnl_usd"] is None
    assert pnl["total_pnl_pct"] is None


def test_pnl_marks_open_position_and_percentage() -> None:
    from tios.services.dashboard_api.demo_lane import _pnl

    pnl = _pnl(
        [
            {
                "side": "Buy",
                "avg_price": "2000",
                "reconcile": {"ETH_delta": 0.01, "USDT_delta": -20.0},
            }
        ],
        mark_price=2200.0,
    )

    assert pnl["position_value_usd"] == pytest.approx(22.0)
    assert pnl["total_pnl_usd"] == pytest.approx(2.0)
    assert pnl["total_pnl_pct"] == pytest.approx(10.0)


def test_completed_round_trip_realises_pnl() -> None:
    from tios.services.dashboard_api.demo_lane import _pnl

    pnl = _pnl(
        [
            {
                "side": "Buy",
                "avg_price": "2000",
                "reconcile": {"ETH_delta": 0.01, "USDT_delta": -20.0},
            },
            {
                "side": "Sell",
                "avg_price": "2200",
                "reconcile": {"ETH_delta": -0.01, "USDT_delta": 22.0},
            },
        ],
        mark_price=2200.0,
    )

    assert pnl["position_base"] == pytest.approx(0.0)
    assert pnl["total_pnl_usd"] == pytest.approx(2.0)
    assert pnl["unrealised_pnl_usd"] == pytest.approx(0.0)
    assert pnl["realised_pnl_usd"] == pytest.approx(2.0)


def test_wallet_prefers_heartbeat_over_stale_fill_snapshot() -> None:
    """A lane that trades rarely would otherwise show balances frozen at the last fill."""
    from tios.services.dashboard_api.demo_lane import _wallet

    fresh = _wallet(
        {"wallet": {"USDT": "975.0", "ETH": "0.0134"}, "at": "2026-07-20T18:00:00+00:00"},
        [{"wallet_after": {"USDT": "1000.0"}, "recorded_at": "2026-07-20T14:15:58+00:00"}],
    )

    assert fresh["source"] == "heartbeat"
    assert fresh["quote_balance_usd"] == 975.0
    assert fresh["as_of"] == "2026-07-20T18:00:00+00:00"


def test_wallet_falls_back_to_last_fill_when_heartbeat_has_none() -> None:
    from tios.services.dashboard_api.demo_lane import _wallet

    fallback = _wallet(
        {"at": "2026-07-20T18:00:00+00:00"},
        [{"wallet_after": {"USDT": "1000.0"}, "recorded_at": "2026-07-20T14:15:58+00:00"}],
    )

    assert fallback["source"] == "last_fill"
    assert fallback["quote_balance_usd"] == 1000.0
    assert fallback["as_of"] == "2026-07-20T14:15:58+00:00"


def test_wallet_absent_is_reported_as_unavailable() -> None:
    from tios.services.dashboard_api.demo_lane import _wallet

    empty = _wallet({}, [])
    assert empty["available"] is False
    assert empty["quote_balance_usd"] is None


def test_position_states_absent_stop_and_take_profit_explicitly() -> None:
    """Blank fields read as 'not loaded'; absence must be stated, not implied.

    Asserted on the position rather than on market state: a stop describes the trade it
    protects, so that is where its absence has to be visible.
    """
    from tios.services.dashboard_api.demo_lane import _position, _rules

    position = _position(
        [
            {
                "side": "Buy",
                "avg_price": "1862",
                "reconcile": {"ETH_delta": 0.0134, "USDT_delta": -25.0},
            }
        ],
        mark=1900.0,
        rules={"donchian_lower": "1800.0"},
    )

    assert position["stop_loss"] is None
    assert position["take_profit"] is None
    assert "no stop loss or take profit" in position["protection"]
    assert _rules({}, holding=False, mark=0.0)["exit_rule"] == "close < donchian_lower(40)"


def test_rules_show_the_exit_band_while_long() -> None:
    """While holding, the price that matters is the one that triggers the sell."""
    from tios.services.dashboard_api.demo_lane import _rules

    heartbeat = {
        "rule_levels": {
            "warming_up": False,
            "donchian_upper": "1950.0",
            "donchian_lower": "1800.0",
            "volume_threshold": "500.0",
            "volume_base": "610.0",
        }
    }

    rules = _rules(heartbeat, holding=True, mark=1900.0)

    assert rules["active_trigger"] == "EXIT_BELOW"
    assert rules["active_trigger_price"] == 1800.0
    # 1900 is 5.26% above the 1800 exit band.
    assert rules["distance_to_trigger_pct"] == pytest.approx(5.26, abs=0.01)


def test_rules_show_the_entry_band_while_flat() -> None:
    from tios.services.dashboard_api.demo_lane import _rules

    heartbeat = {
        "rule_levels": {
            "warming_up": False,
            "donchian_upper": "1950.0",
            "donchian_lower": "1800.0",
        }
    }

    rules = _rules(heartbeat, holding=False, mark=1900.0)

    assert rules["active_trigger"] == "ENTRY_ABOVE"
    assert rules["active_trigger_price"] == 1950.0
    # Negative: price is below the entry band and must rise to reach it.
    assert rules["distance_to_trigger_pct"] < 0


def test_rules_report_warming_up_when_the_lane_has_no_levels_yet() -> None:
    from tios.services.dashboard_api.demo_lane import _rules

    assert _rules({}, holding=True, mark=1900.0)["warming_up"] is True
    assert (
        _rules({"rule_levels": {"warming_up": True}}, holding=True, mark=0.0)["warming_up"] is True
    )


def test_account_block_states_demo_and_credential_boundary(tmp_path: Path) -> None:
    from tios.services.dashboard_api.demo_lane import build_demo_lane

    account = build_demo_lane(tmp_path)["account"]

    assert account["venue"] == "Bybit"
    assert account["environment"] == "DEMO"
    assert account["real_money"] is False
    assert "dashboard holds none" in account["credential_holder"]


def test_stop_and_take_profit_live_on_the_position_not_the_account(tmp_path: Path) -> None:
    """Scope discipline: a stop protects a position, so it must not read as an account setting."""
    from tios.services.dashboard_api.demo_lane import _position, _rules

    position = _position(
        [
            {
                "side": "Buy",
                "avg_price": "1862",
                "reconcile": {"ETH_delta": 0.0134, "USDT_delta": -25.0},
            }
        ],
        mark=1900.0,
        rules={"donchian_lower": "1800.0"},
    )
    assert "stop_loss" in position
    assert "take_profit" in position
    assert position["stop_loss"] is None

    # Market state carries neither — those belong to the trade, not the tape.
    market = _rules({"rule_levels": {"warming_up": False, "donchian_lower": "1800"}}, True, 1900.0)
    assert "stop_loss" not in market
    assert "take_profit" not in market


def test_position_reports_entry_exit_and_unrealised_for_one_trade() -> None:
    from tios.services.dashboard_api.demo_lane import _position

    position = _position(
        [
            {
                "side": "Buy",
                "avg_price": "2000",
                "reconcile": {"ETH_delta": 0.01, "USDT_delta": -20.0},
            }
        ],
        mark=2200.0,
        rules={"donchian_lower": "1900.0"},
    )

    assert position["open"] is True
    assert position["entry_price_usd"] == 2000.0
    assert position["unrealised_pnl_usd"] == pytest.approx(2.0)
    assert position["unrealised_pnl_pct"] == pytest.approx(10.0)
    assert position["exit_trigger_usd"] == 1900.0
    assert position["distance_to_exit_pct"] == pytest.approx(13.64, abs=0.01)


def test_flat_position_reports_the_entry_band_instead(tmp_path: Path) -> None:
    from tios.services.dashboard_api.demo_lane import _position

    position = _position([], mark=1900.0, rules={"donchian_upper": "1950.0"})

    assert position["open"] is False
    assert position["would_enter_above"] == "1950.0"
    assert position["entry_price_usd"] is None


def _write_open_lane_with_stop(root: Path, resting_stop: object, *, in_state: bool = True) -> None:
    (root / demo_lane.ORDERS_LEDGER).write_text(
        _order(
            order_id="B1",
            reconcile={"ETH_delta": 0.01341033, "USDT_delta": -25.0},
        )
        + "\n"
    )
    state: dict[str, object] = {
        "lane_base": "0.01341033",
        "entry_price": "1862.37",
    }
    heartbeat: dict[str, object] = {
        "at": datetime.now(UTC).isoformat(),
        "lane_base": "0.01341033",
        "mark_price": "1900",
        "resting_stop": resting_stop,
    }
    if in_state:
        state["resting_stop"] = resting_stop
    else:
        heartbeat["resting_stop"] = resting_stop
    (root / demo_lane.LANE_STATE).write_text(json.dumps(state))
    (root / demo_lane.HEARTBEAT).write_text(json.dumps(heartbeat))


def _active_stop(order_id: str = "STOP-1") -> dict[str, str]:
    return {
        "state": "ACTIVE",
        "order_id": order_id,
        "risk_boundary_price": "1583.0145",
        "trigger_price": "1583.02",
        "base_qty": "0.01341",
        "position_base_qty": "0.01341033",
        "risk_fraction": "0.15",
        "price_tick": "0.01",
    }


def test_active_operational_stop_is_normalized_and_attached_only_to_open_position(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_open_lane_with_stop(root, _active_stop())
    monkeypatch.setattr(
        demo_lane,
        "_running",
        lambda _root: (True, 4242, datetime.now(UTC).isoformat()),
    )

    lane = demo_lane.build_demo_lane(root)

    expected = lane["operational_disaster_stop"]
    assert expected["state"] == "ACTIVE"
    assert expected["last_reported_active"] is True
    assert expected["active"] is True
    assert expected["currently_confirmed"] is True
    assert expected["source"] == "lane_state"
    assert expected["order_id"] == "STOP-1"
    assert expected["local_boundary_price_usd"] == 1583.0145
    assert expected["venue_trigger_price_usd"] == 1583.02
    assert expected["base_qty"] == 0.01341
    assert expected["position_base_qty"] == 0.01341033
    assert expected["risk_fraction"] == 0.15
    assert expected["price_tick_usd"] == 0.01
    assert expected["freshness"]["fresh"] is True
    assert expected["reasons"] == []
    assert expected["last_confirmed_at"] is not None
    assert lane["position"]["stop_loss"] is None
    assert lane["position"]["take_profit"] is None
    assert lane["position"]["operational_disaster_stop"] == expected
    assert "last reported operational -15% disaster stop" in lane["position"]["protection"]
    assert "currently confirmed by fresh lane reconciliation" in lane["position"]["protection"]
    assert "rule-driven exit" in lane["position"]["protection"]
    assert lane["positions"][0]["sl_steps"] == [1583.02]
    assert lane["positions"][0]["operational_disaster_stop"] == expected


def test_heartbeat_fallback_retains_report_but_cannot_claim_current_confirmation(
    root: Path,
) -> None:
    _write_open_lane_with_stop(root, _active_stop("HEARTBEAT-STOP"), in_state=False)

    stop = demo_lane.build_demo_lane(root)["operational_disaster_stop"]

    assert stop["last_reported_active"] is True
    assert stop["active"] is False
    assert stop["currently_confirmed"] is False
    assert stop["source"] == "heartbeat"
    assert stop["order_id"] == "HEARTBEAT-STOP"
    assert "LANE_STATE_STOP_MISSING" in stop["reasons"]


@pytest.mark.parametrize("stop_state", ["AMBIGUOUS", "FILLED_PENDING_RECONCILIATION"])
def test_unconfirmed_operational_stop_is_visible_but_never_claimed_as_protection(
    root: Path, stop_state: str
) -> None:
    resting_stop = {**_active_stop(), "state": stop_state}
    _write_open_lane_with_stop(root, resting_stop)

    lane = demo_lane.build_demo_lane(root)
    open_position = lane["positions"][0]

    assert lane["operational_disaster_stop"]["state"] == stop_state
    assert lane["operational_disaster_stop"]["last_reported_active"] is False
    assert lane["operational_disaster_stop"]["active"] is False
    assert open_position["operational_disaster_stop"]["state"] == stop_state
    assert open_position["sl_steps"] == []
    assert "operational" not in open_position["protection"]
    assert "operational" not in lane["position"]["protection"]


def test_malformed_active_stop_fails_closed_instead_of_using_stale_heartbeat(root: Path) -> None:
    _write_open_lane_with_stop(root, {"state": "ACTIVE"})
    heartbeat = json.loads((root / demo_lane.HEARTBEAT).read_text())
    heartbeat["resting_stop"] = _active_stop("STALE")
    (root / demo_lane.HEARTBEAT).write_text(json.dumps(heartbeat))

    lane = demo_lane.build_demo_lane(root)
    stop = lane["operational_disaster_stop"]

    assert stop["state"] == "ACTIVE"
    assert stop["last_reported_active"] is True
    assert stop["active"] is False
    assert stop["source"] == "lane_state"
    assert stop["order_id"] is None
    assert lane["positions"][0]["sl_steps"] == []


def _currently_confirmed_stop(
    *,
    state_stop: dict[str, object] | None = None,
    heartbeat_stop: dict[str, object] | None = None,
    state_base: object = "0.01341033",
    heartbeat_base: object = "0.01341033",
    ledger_base: float = 0.01341033,
    entry_price: object = "1862.37",
    mark_price: object | None = "1900",
    running: bool = True,
    heartbeat_age: timedelta = timedelta(minutes=5),
) -> dict[str, Any]:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    state_report = state_stop or _active_stop()
    heartbeat_report = heartbeat_stop or dict(state_report)
    heartbeat: dict[str, object] = {
        "at": (now - heartbeat_age).isoformat(),
        "lane_base": heartbeat_base,
        "resting_stop": heartbeat_report,
    }
    if mark_price is not None:
        heartbeat["mark_price"] = mark_price
    return demo_lane._operational_disaster_stop(
        {
            "lane_base": state_base,
            "entry_price": entry_price,
            "resting_stop": state_report,
        },
        heartbeat,
        running=running,
        ledger_base=ledger_base,
        now=now,
    )


@pytest.mark.parametrize("bad_value", [True, float("inf"), float("-inf"), float("nan")])
def test_bool_and_nonfinite_stop_numerics_fail_closed(bad_value: object) -> None:
    stop = {**_active_stop(), "base_qty": bad_value}

    projection = _currently_confirmed_stop(state_stop=stop, heartbeat_stop=dict(stop))

    assert projection["last_reported_active"] is True
    assert projection["active"] is False
    assert projection["base_qty"] is None
    assert "STOP_FIELDS_INVALID_OR_MISSING" in projection["reasons"]


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"base_qty": "0.001"}, "STOP_QTY_COVERAGE_TOO_LOW"),
        ({"position_base_qty": "0.012"}, "STOP_POSITION_EXPOSURE_MISMATCH"),
    ],
)
def test_tiny_or_stale_stop_quantity_is_not_currently_confirmed(
    updates: dict[str, str], reason: str
) -> None:
    stop = {**_active_stop(), **updates}

    projection = _currently_confirmed_stop(state_stop=stop, heartbeat_stop=dict(stop))

    assert projection["active"] is False
    assert reason in projection["reasons"]


def test_ledger_and_state_exposure_disagreement_fails_closed() -> None:
    projection = _currently_confirmed_stop(state_base="0.02")

    assert projection["active"] is False
    assert "STATE_LEDGER_EXPOSURE_MISMATCH" in projection["reasons"]


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"risk_boundary_price": "1500"}, "LOCAL_BOUNDARY_MISMATCH"),
        ({"trigger_price": "1584"}, "VENUE_TRIGGER_OUTSIDE_TICK_TOLERANCE"),
    ],
)
def test_wrong_boundary_or_trigger_fails_closed(updates: dict[str, str], reason: str) -> None:
    stop = {**_active_stop(), **updates}

    projection = _currently_confirmed_stop(state_stop=stop, heartbeat_stop=dict(stop))

    assert projection["active"] is False
    assert reason in projection["reasons"]


def test_dead_lane_retains_last_report_without_claiming_current_protection() -> None:
    projection = _currently_confirmed_stop(running=False)

    assert projection["last_reported_active"] is True
    assert projection["currently_confirmed"] is False
    assert "LANE_NOT_RUNNING" in projection["reasons"]


def test_stale_heartbeat_retains_last_confirmation_time_but_is_inactive() -> None:
    projection = _currently_confirmed_stop(heartbeat_age=timedelta(hours=2))

    assert projection["active"] is False
    assert projection["last_confirmed_at"] is not None
    assert projection["freshness"]["fresh"] is False
    assert "HEARTBEAT_STALE" in projection["reasons"]


def test_boundary_timestamp_overflow_is_invalid_not_an_api_crash() -> None:
    freshness = demo_lane._heartbeat_freshness(
        {"at": "0001-01-01T00:00:00+23:59"},
        datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )

    assert freshness["fresh"] is False
    assert freshness["age_seconds"] is None


def test_state_and_heartbeat_stop_mismatch_fails_closed() -> None:
    heartbeat_stop = {**_active_stop(), "order_id": "OTHER"}

    projection = _currently_confirmed_stop(heartbeat_stop=heartbeat_stop)

    assert projection["active"] is False
    assert projection["last_confirmed_at"] is None
    assert "STATE_HEARTBEAT_STOP_MISMATCH" in projection["reasons"]


def test_mark_at_or_below_trigger_is_visible_as_breached_not_active() -> None:
    projection = _currently_confirmed_stop(mark_price="1583.02")

    assert projection["active"] is False
    assert "MARK_AT_OR_BELOW_TRIGGER" in projection["reasons"]


def test_missing_mark_cannot_confirm_current_protection() -> None:
    projection = _currently_confirmed_stop(mark_price=None)

    assert projection["last_reported_active"] is True
    assert projection["active"] is False
    assert "MARK_INVALID_OR_MISSING" in projection["reasons"]


def test_bound_non_default_tick_controls_trigger_tolerance() -> None:
    stop = {**_active_stop(), "price_tick": "0.1", "trigger_price": "1583.1"}

    projection = _currently_confirmed_stop(state_stop=stop, heartbeat_stop=dict(stop))

    assert projection["active"] is True
    assert projection["price_tick_usd"] == 0.1
    assert projection["venue_trigger_price_usd"] == 1583.1


def test_bound_changed_risk_fraction_controls_expected_boundary() -> None:
    stop = {
        **_active_stop(),
        "risk_fraction": "0.20",
        "risk_boundary_price": "1489.896",
        "trigger_price": "1489.90",
    }

    projection = _currently_confirmed_stop(state_stop=stop, heartbeat_stop=dict(stop))

    assert projection["active"] is True
    assert projection["risk_fraction"] == 0.2


def test_older_report_without_bound_metadata_remains_visible_but_inactive() -> None:
    old_stop = _active_stop()
    old_stop.pop("risk_fraction")
    old_stop.pop("price_tick")

    projection = _currently_confirmed_stop(state_stop=old_stop, heartbeat_stop=dict(old_stop))

    assert projection["last_reported_active"] is True
    assert projection["active"] is False
    assert projection["risk_fraction"] is None
    assert projection["price_tick_usd"] is None
    assert "BOUND_STOP_METADATA_MISSING_OR_INVALID" in projection["reasons"]


def test_flat_lane_does_not_attach_stop_to_a_closed_position(root: Path) -> None:
    (root / demo_lane.ORDERS_LEDGER).write_text(
        _order(order_id="B1", reconcile={"ETH_delta": 0.01, "USDT_delta": -20.0})
        + "\n"
        + _order(
            order_id="S1",
            side="Sell",
            reconcile={"ETH_delta": -0.01, "USDT_delta": 22.0},
        )
        + "\n"
    )
    (root / demo_lane.LANE_STATE).write_text(
        json.dumps({"lane_base": "0", "resting_stop": _active_stop()})
    )

    lane = demo_lane.build_demo_lane(root)

    assert lane["operational_disaster_stop"]["active"] is False
    assert lane["position"]["open"] is False
    assert "operational_disaster_stop" not in lane["position"]
    assert lane["positions"][0]["status"] == "CLOSED"
    assert "operational_disaster_stop" not in lane["positions"][0]
    assert lane["positions"][0]["sl_steps"] == []


def test_closed_round_trip_annotates_realised_pnl_on_the_sell(tmp_path: Path) -> None:
    """Per-order result belongs on the order that closed it, not only in the total."""
    from tios.services.dashboard_api.demo_lane import _annotate_orders

    annotations = _annotate_orders(
        [
            {
                "order_id": "A",
                "side": "Buy",
                "avg_price": "2000",
                "reconcile": {"ETH_delta": 0.01, "USDT_delta": -20.0},
            },
            {
                "order_id": "B",
                "side": "Sell",
                "avg_price": "2200",
                "reconcile": {"ETH_delta": -0.01, "USDT_delta": 22.0},
            },
        ]
    )

    assert annotations["A"]["realised_pnl_usd"] is None, "an open buy has realised nothing"
    assert annotations["B"]["realised_pnl_usd"] == pytest.approx(2.0)
    assert annotations["A"]["stop_loss"] is None
    assert annotations["B"]["protection"] == "none — rule-driven exit"


def _buy(ts: str, eth: float = 0.01, usdt: float = -20.0, oid: str = "B1") -> dict:
    return {
        "order_id": oid,
        "side": "Buy",
        "avg_price": "2000",
        "recorded_at": ts,
        "reconcile": {"ETH_delta": eth, "USDT_delta": usdt},
    }


def _sell(ts: str, eth: float = -0.01, usdt: float = 22.0, oid: str = "S1") -> dict:
    return {
        "order_id": oid,
        "side": "Sell",
        "avg_price": "2200",
        "recorded_at": ts,
        "reconcile": {"ETH_delta": eth, "USDT_delta": usdt},
    }


def test_round_trips_fold_fills_into_positions() -> None:
    """Positions are derived from fills, never stored, so they cannot disagree."""
    from tios.services.dashboard_api.demo_lane import _round_trips

    positions = _round_trips(
        [
            _buy("2026-07-01T00:00:00+00:00"),
            _sell("2026-07-03T00:00:00+00:00"),
            _buy("2026-07-10T00:00:00+00:00", oid="B2"),
        ],
        mark=2100.0,
    )

    assert len(positions) == 2
    open_pos, closed = positions[0], positions[1]  # newest first
    assert open_pos["status"] == "OPEN"
    assert open_pos["pnl_usd"] == pytest.approx(1.0)  # 0.01 * 2100 - 20
    assert closed["status"] == "CLOSED"
    assert closed["pnl_usd"] == pytest.approx(2.0)
    assert closed["pnl_pct"] == pytest.approx(10.0)
    assert closed["strategy"].startswith("STRAT-ETH")
    assert closed["tp_steps"] == [] and closed["sl_steps"] == []
    assert closed["expected_hold_bars"] == 65


def test_window_stats_attribute_realised_pnl_to_the_close_window() -> None:
    """Realised P/L belongs to the window the result became real in."""
    from datetime import UTC, datetime

    from tios.services.dashboard_api.demo_lane import _round_trips, _window_stats

    now = datetime(2026, 7, 20, tzinfo=UTC)
    fills = [
        _buy("2026-06-01T00:00:00+00:00"),
        _sell("2026-06-03T00:00:00+00:00"),  # closed 47d ago
        _buy("2026-07-19T12:00:00+00:00", oid="B2"),
        _sell("2026-07-19T18:00:00+00:00", oid="S2"),
    ]
    positions = _round_trips(fills, mark=0.0)

    windows = _window_stats(positions, fills, now)

    assert windows["1d"]["positions_closed"] == 1
    assert windows["1d"]["realised_pnl_usd"] == pytest.approx(2.0)
    assert windows["all"]["positions_closed"] == 2
    assert windows["all"]["realised_pnl_usd"] == pytest.approx(4.0)
    assert windows["all"]["win_rate_pct"] == 100.0
    # The June trade's P/L must NOT leak into the 1-day window.
    assert windows["1d"]["realised_pnl_usd"] < windows["all"]["realised_pnl_usd"]


def test_window_stats_exclude_unrealised_pnl() -> None:
    """Window numbers must not drift with price when nothing was traded."""
    from datetime import UTC, datetime

    from tios.services.dashboard_api.demo_lane import _round_trips, _window_stats

    fills = [_buy("2026-07-19T12:00:00+00:00")]
    positions = _round_trips(fills, mark=99999.0)  # huge unrealised gain

    windows = _window_stats(positions, fills, datetime(2026, 7, 20, tzinfo=UTC))

    assert windows["1d"]["realised_pnl_usd"] == 0
    assert windows["1d"]["positions_opened"] == 1
    assert windows["1d"]["positions_closed"] == 0


def test_ai_costs_projection_aggregates_ledger_without_credentials(tmp_path: Path) -> None:
    import json as _json

    from tios.services.dashboard_api.ai_costs import build_ai_costs

    empty = build_ai_costs(tmp_path)
    assert empty["available"] is False

    ledger = tmp_path / "artifacts" / "ai_benchmarks" / "cost_telemetry.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        _json.dumps(
            {
                "at": "2026-07-21T00:00:00+00:00",
                "provider": "anthropic",
                "model": "claude-opus-4-8",
                "calls": 54,
                "cost_usd": 0.27,
            }
        )
        + "\n"
        + _json.dumps(
            {
                "at": "2026-07-21T00:00:00+00:00",
                "provider": "openai",
                "model": None,
                "calls": 0,
                "cost_usd": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    view = build_ai_costs(tmp_path)
    assert view["available"] is True
    assert view["total_cost_usd"] == pytest.approx(0.27)
    # A blocked config with zero calls contributes no spend row.
    assert list(view["by_model"]) == ["claude-opus-4-8"]
    forbidden = _json.dumps(view).lower()
    assert "api_key" not in forbidden and "sk-" not in forbidden


def test_divergence_projection_reports_staleness_honestly(tmp_path: Path) -> None:
    import json as _json

    from tios.services.dashboard_api.demo_lane import _divergence

    assert _divergence(tmp_path, fills_now=0)["available"] is False

    report = tmp_path / "artifacts" / "trading_domain" / "demo_lane" / "DIVERGENCE_REPORT.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        _json.dumps(
            {
                "fills_measured": 1,
                "mean_divergence_bps": -1.45,
                "worst_divergence_bps": -1.45,
                "generated_at": "2026-07-20T21:11:17+00:00",
            }
        ),
        encoding="utf-8",
    )

    fresh = _divergence(tmp_path, fills_now=1)
    assert fresh["available"] and fresh["stale"] is False
    # New fills since the report ran: the numbers must be flagged, not passed off as current.
    assert _divergence(tmp_path, fills_now=3)["stale"] is True
