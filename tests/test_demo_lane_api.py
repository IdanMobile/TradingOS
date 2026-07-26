"""Tests for the rich multi-coin demo-lane operator projection and bounded controls.

GET /api/v1/demo-lane returns the top-level safety envelope, a rich per-coin operator view
(`coins`) with a `portfolio` roll-up, and the fixed, fail-closed Stage B readiness object.
The `stage_b` EVIDENCE field stays aggregate-only and redacted even though the operator view is
rich. The action handler returns exactly four fixed fields.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tios.services.dashboard_api import demo_lane

_BODY_KEYS = {
    "schema_version",
    "operational_status",
    "kill_switch",
    "environment",
    "real_money",
    "execution_authority",
    "validation_state",
    "promotion_eligible",
    "auto_tune",
    "coins",
    "portfolio",
    "activity",
    "activity_summary",
    "stage_b",
}
_ACTIVITY_KEYS = {
    "symbol",
    "base_coin",
    "data_available",
    "kill_switch",
    "confidence_score",
    "decision",
    "bullish",
    "bearish",
    "position",
    "protection",
    "heartbeat_age_seconds",
    "heartbeat_fresh",
}
_COIN_KEYS = {
    "symbol",
    "base_coin",
    "data_available",
    "kill_switch",
    "heartbeat_age_seconds",
    "heartbeat_fresh",
    "signals",
    "position",
    "protection",
    "watching",
    "trade_history",
}
_STAGE_B_KEYS = {"status", "cohort_size", "series"}
_COHORT_KEYS = {
    "cohort_number",
    "assigned_count",
    "eligible_closed_count",
    "ineligible_count",
    "open_count",
    "readiness",
    "aggregate",
}
_AGGREGATE_KEYS = {
    "closed_count",
    "positive_count",
    "negative_count",
    "flat_count",
    "entry_exec_value_total",
    "exit_exec_value_total",
    "gross_quote_total",
    "quote_fee_total",
    "base_fee_total",
    "net_quote_total",
}
# Anything from the legacy projection that the global allowlist forbids in every state.
_FORBIDDEN_TOKENS = (
    "heartbeat",
    "pid",
    "cursor",
    "wallet",
    "position",
    "positions",
    "position_base",
    "orders",
    "order_id",
    "client_key",
    "clientkey",
    "orderlinkid",
    "exec_id",
    "execid",
    "signal",
    "pnl",
    "realised",
    "unrealised",
    "windows",
    "best",
    "worst",
    "streak",
    "curve",
    "recorded_at",
    "avg_price",
    "divergence",
    "private_demo",
    "install_alias",
    "strategy_alias",
    "series_sha256",
    "account",
    "credential",
    "note",
)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / demo_lane.LANE_DIR).mkdir(parents=True)
    script = tmp_path / demo_lane.LANE_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# stand-in lane script\n")
    return tmp_path


def _complete_aggregate() -> dict[str, Any]:
    return {
        "closed_count": 30,
        "positive_count": 12,
        "negative_count": 11,
        "flat_count": 7,
        "entry_exec_value_total": "600.5",
        "exit_exec_value_total": "612.25",
        "gross_quote_total": "11.75",
        "quote_fee_total": "1.2",
        "base_fee_total": "0",
        "net_quote_total": "10.55",
    }


def _cohort(number: int, readiness: str, aggregate: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "cohort_number": number,
        "assigned_count": 30 if aggregate else 12,
        "eligible_closed_count": 30 if aggregate else 12,
        "ineligible_count": 0,
        "open_count": 0 if aggregate else 18,
        "readiness": readiness,
        "aggregate": aggregate,
    }


def _projection(status: str, series: list[dict[str, Any]]) -> dict[str, Any]:
    return {"status": status, "cohort_size": 30, "series": series}


# --- absent / default-disabled -------------------------------------------------------


def test_absent_stage_b_is_not_activated_with_authority_none(root: Path) -> None:
    lane = demo_lane.build_demo_lane(root)
    assert set(lane) == _BODY_KEYS
    assert (
        lane["schema_version"] == 1
    )  # matches every other GET endpoint + the client fetchJson gate
    assert lane["operational_status"] == "IDLE"
    assert lane["execution_authority"] == "NONE"
    assert lane["real_money"] is False
    assert lane["promotion_eligible"] is False
    assert lane["auto_tune"] is False
    assert lane["validation_state"] == "UNVALIDATED"
    assert set(lane["stage_b"]) == _STAGE_B_KEYS
    assert lane["stage_b"] == {"status": "NOT_ACTIVATED", "cohort_size": 30, "series": []}


# --- rich, live, multi-coin operator view -------------------------------------------


def _long_coin_files(root: Path, symbol: str) -> None:
    """Write a per-coin heartbeat/state/order set for an open LONG position on `symbol`."""
    base = symbol.removesuffix("USDT")
    hb = demo_lane.LANE_DIR / (
        "heartbeat.json" if symbol == "ETHUSDT" else f"heartbeat_{symbol}.json"
    )
    st = demo_lane.LANE_DIR / (
        "lane_state.json" if symbol == "ETHUSDT" else f"lane_state_{symbol}.json"
    )
    (root / hb).write_text(
        json.dumps(
            {
                "at": "2099-01-01T00:00:00+00:00",
                "symbol": symbol,
                "lane_base": "2",
                "mark_price": "110",
                "entry_price": "100",
                "disaster_stop_price": "85",
                "signals_in_window": 3,
                "fresh_signals": 1,
                "latest_closed_bar": "2099-01-01T00:00:00+00:00",
                "resting_stop": {"state": "ACTIVE", "trigger_price": "95", "base_qty": "2"},
                "rule_levels": {
                    "warming_up": False,
                    "close": "108",
                    "donchian_upper": "120",
                    "donchian_lower": "90",
                    "volume_base": "1.2",
                    "volume_threshold": "1.5",
                },
            }
        )
    )
    (root / st).write_text(
        json.dumps(
            {
                "lane_base": "2",
                "entry_price": "100",
                "resting_stop": {"state": "ACTIVE", "trigger_price": "95", "base_qty": "2"},
            }
        )
    )
    orders = [
        {
            "symbol": symbol,
            "side": "Buy",
            "avg_price": "100",
            "fee": "0.001",
            "recorded_at": "2099-01-01T00:00:00+00:00",
            "reconcile": {"USDT_delta": -200.0, f"{base}_delta": 2.0},
        }
    ]
    (root / demo_lane.ORDERS_LEDGER).write_text("\n".join(json.dumps(o) for o in orders) + "\n")


def test_coins_are_every_demo_coin_in_order_with_no_selector(root: Path) -> None:
    lane = demo_lane.build_demo_lane(root)
    assert [c["symbol"] for c in lane["coins"]] == list(demo_lane.DEMO_COINS)
    assert all(set(c) == _COIN_KEYS for c in lane["coins"])
    # No request/query parameter selects a coin — build_demo_lane accepts only an optional root.
    import inspect

    assert list(inspect.signature(demo_lane.build_demo_lane).parameters) == ["root"]


def test_missing_coin_degrades_to_idle_not_a_crash(root: Path) -> None:
    lane = demo_lane.build_demo_lane(root)
    btc = next(c for c in lane["coins"] if c["symbol"] == "BTCUSDT")
    assert btc["data_available"] is False
    assert btc["position"]["side"] == "FLAT"
    assert btc["position"]["unrealised_pnl_usd"] is None
    assert btc["trade_history"]["closed_count"] == 0


def test_malformed_coin_data_degrades_gracefully_not_a_crash(root: Path) -> None:
    # A heartbeat present but with wrong-typed nested fields (rule_levels/resting_stop not dicts,
    # non-numeric prices) must NOT 500 the whole response: that coin degrades to safe defaults
    # while every other coin still projects in order.
    hb = demo_lane.LANE_DIR / "heartbeat_SOLUSDT.json"
    (root / hb).parent.mkdir(parents=True, exist_ok=True)
    (root / hb).write_text(
        json.dumps(
            {
                "at": "2099-01-01T00:00:00+00:00",
                "symbol": "SOLUSDT",
                "lane_base": "not-a-number",
                "mark_price": "oops",
                "rule_levels": ["not", "a", "dict"],
                "resting_stop": "also-not-a-dict",
            }
        )
    )
    lane = demo_lane.build_demo_lane(root)
    assert [c["symbol"] for c in lane["coins"]] == list(demo_lane.DEMO_COINS)
    sol = next(c for c in lane["coins"] if c["symbol"] == "SOLUSDT")
    assert set(sol) == _COIN_KEYS
    assert sol["position"]["side"] == "FLAT"  # bad lane_base -> 0 -> flat
    assert sol["watching"]["donchian_upper_usd"] is None  # malformed rule_levels -> degraded


def test_open_position_live_unrealised_and_distance_to_entry(root: Path) -> None:
    _long_coin_files(root, "ETHUSDT")
    eth = next(c for c in demo_lane.build_demo_lane(root)["coins"] if c["symbol"] == "ETHUSDT")
    pos = eth["position"]
    assert pos["side"] == "LONG"
    assert pos["base_qty"] == 2.0
    assert pos["entry_price_usd"] == 100.0
    assert pos["mark_price_usd"] == 110.0
    # 2 @ (110-100) = 20 live unrealised, +10%.
    assert pos["unrealised_pnl_usd"] == 20.0
    assert pos["unrealised_pnl_pct"] == 10.0
    # close 108 vs breakout upper 120 -> 10% below.
    assert eth["watching"]["distance_to_entry_pct"] == 10.0
    # volume 1.2 of 1.5 gate -> 80%.
    assert eth["watching"]["volume_pct_of_gate"] == 80.0
    # -15% disaster floor + venue-resting stop surfaced.
    assert eth["protection"]["disaster_stop_price_usd"] == 85.0
    assert eth["protection"]["venue_resting_stop_trigger_usd"] == 95.0
    assert eth["protection"]["venue_resting_stop_state"] == "ACTIVE"


def test_portfolio_rollup_sums_across_coins(root: Path) -> None:
    _long_coin_files(root, "ETHUSDT")
    portfolio = demo_lane.build_demo_lane(root)["portfolio"]
    assert portfolio["coins_total"] == len(demo_lane.DEMO_COINS)
    assert portfolio["coins_in_position"] == 1
    assert portfolio["coins_flat"] == len(demo_lane.DEMO_COINS) - 1
    assert portfolio["unrealised_pnl_usd"] == 20.0
    assert portfolio["open_exposure_usd"] == 200.0  # cost basis = ledger USDT spent on the entry


def test_stage_b_field_stays_aggregate_only_and_lists_no_coins(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator view is rich, but the stage_b FIELD remains the redacted aggregate-only one."""
    _long_coin_files(root, "ETHUSDT")
    projection = _projection(
        "READY", [{"series_number": 1, "cohorts": [_cohort(1, "COMPLETE", _complete_aggregate())]}]
    )
    monkeypatch.setattr(demo_lane, "public_stage_b_projection", lambda _root: projection)
    stage_b = demo_lane.build_demo_lane(root)["stage_b"]
    assert set(stage_b) == _STAGE_B_KEYS
    stage_b_body = json.dumps(stage_b).lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in stage_b_body, f"forbidden token leaked into stage_b: {token}"
    # The per-coin operator data lives only under coins/portfolio, never inside stage_b.
    assert "ethusdt" not in stage_b_body


def test_kill_switch_and_operational_status_derive_from_lane_signals(root: Path) -> None:
    (root / demo_lane.KILL_SWITCH).write_text("{}")
    lane = demo_lane.build_demo_lane(root)
    assert lane["operational_status"] == "STOPPED"
    assert lane["kill_switch"] is True


def test_running_lock_reports_running(root: Path) -> None:
    import fcntl

    lock = root / demo_lane.LANE_LOCK
    lock.write_text(json.dumps({"pid": 4242}))
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        lane = demo_lane.build_demo_lane(root)
        assert lane["operational_status"] == "RUNNING"
        # No PID is ever surfaced, even while running.
        assert "pid" not in json.dumps(lane).lower()
    finally:
        handle.close()


# --- fail-closed on malformed / unsafe projections ----------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "READY"},  # missing series/cohort_size
        {"status": "SOMETHING_ELSE", "cohort_size": 30, "series": []},
        {"status": "READY", "cohort_size": 30, "series": "not-a-list"},
        _projection("READY", [{"series_number": 1}]),  # cohorts missing
        _projection("READY", [{"series_number": 1, "cohorts": [{"cohort_number": 1}]}]),
        "not-a-dict",
        None,
    ],
)
def test_malformed_projection_fails_closed_to_unavailable(
    root: Path, monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    monkeypatch.setattr(demo_lane, "public_stage_b_projection", lambda _root: bad)
    lane = demo_lane.build_demo_lane(root)
    assert lane["stage_b"] == {"status": "UNAVAILABLE", "cohort_size": 30, "series": []}
    assert lane["execution_authority"] == "NONE"


def test_projection_that_raises_fails_closed(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_root: Path) -> dict[str, Any]:
        raise RuntimeError("private store exploded")

    monkeypatch.setattr(demo_lane, "public_stage_b_projection", boom)
    lane = demo_lane.build_demo_lane(root)
    assert lane["stage_b"]["status"] == "UNAVAILABLE"
    assert "exploded" not in json.dumps(lane)


# --- incomplete vs complete cohorts --------------------------------------------------


def test_incomplete_cohort_renders_no_pnl(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(
        "READY", [{"series_number": 1, "cohorts": [_cohort(1, "COLLECTING", None)]}]
    )
    monkeypatch.setattr(demo_lane, "public_stage_b_projection", lambda _root: projection)
    cohort = demo_lane.build_demo_lane(root)["stage_b"]["series"][0]["cohorts"][0]
    assert set(cohort) == _COHORT_KEYS
    assert cohort["readiness"] == "COLLECTING"
    assert cohort["aggregate"] is None


def test_complete_cohort_renders_only_approved_totals(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projection = _projection(
        "READY", [{"series_number": 1, "cohorts": [_cohort(1, "COMPLETE", _complete_aggregate())]}]
    )
    monkeypatch.setattr(demo_lane, "public_stage_b_projection", lambda _root: projection)
    cohort = demo_lane.build_demo_lane(root)["stage_b"]["series"][0]["cohorts"][0]
    assert set(cohort) == _COHORT_KEYS
    assert cohort["readiness"] == "COMPLETE"
    assert set(cohort["aggregate"]) == _AGGREGATE_KEYS
    assert cohort["aggregate"]["net_quote_total"] == "10.55"
    assert cohort["aggregate"]["closed_count"] == 30


# --- redaction: forbidden fields never surface ---------------------------------------


def test_forbidden_fields_are_stripped_from_stage_b(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if upstream leaks private data, the stage_b field reprojects to the allowlist.

    Scoped to `stage_b`: the rich operator view (coins/portfolio) legitimately carries position,
    pnl, and signal fields, but the Stage B EVIDENCE field stays aggregate-only and redacted.
    """
    dirty_aggregate = {**_complete_aggregate(), "private_path": "artifacts/evidence/private_demo"}
    dirty_cohort = {
        **_cohort(1, "COMPLETE", dirty_aggregate),
        "order_id": "1899000000000000001",
        "client_key": "tios2_r_deadbeef",
        "exec_id": "EX-123",
        "recorded_at": "2026-07-24T00:00:00.000000Z",
        "best": "9.9",
        "worst": "-3.1",
        "streak": 4,
        "curve": [1, 2, 3],
        "episodes": [{"pnl": "1.0"}],
    }
    dirty_series = {
        "series_number": 1,
        "cohorts": [dirty_cohort],
        "series_sha256": "a" * 64,
        "strategy_alias": "strategy_" + "b" * 64,
    }
    monkeypatch.setattr(
        demo_lane, "public_stage_b_projection", lambda _root: _projection("READY", [dirty_series])
    )
    lane = demo_lane.build_demo_lane(root)

    series = lane["stage_b"]["series"][0]
    assert set(series) == {"series_number", "cohorts"}
    assert set(series["cohorts"][0]) == _COHORT_KEYS
    assert set(series["cohorts"][0]["aggregate"]) == _AGGREGATE_KEYS

    body = json.dumps(lane["stage_b"]).lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in body, f"forbidden token leaked: {token}"
    assert "deadbeef" not in body
    assert "1899000000000000001" not in body
    assert "2026-07-24" not in body


# --- no subgroup selection; every immutable series in order --------------------------


def test_no_request_parameter_selects_a_subgroup_all_series_in_order(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    series = [
        {"series_number": 1, "cohorts": [_cohort(1, "COMPLETE", _complete_aggregate())]},
        {"series_number": 2, "cohorts": [_cohort(1, "COLLECTING", None)]},
        {"series_number": 3, "cohorts": [_cohort(1, "PERMANENTLY_INELIGIBLE", None)]},
    ]
    monkeypatch.setattr(
        demo_lane, "public_stage_b_projection", lambda _root: _projection("READY", series)
    )
    # build_demo_lane takes only a root — there is no selector parameter at all.
    projected = demo_lane.build_demo_lane(root)["stage_b"]["series"]
    assert [s["series_number"] for s in projected] == [1, 2, 3]
    assert len(projected) == 3


# --- action success body is exactly four fields --------------------------------------


def test_stop_action_returns_exact_four_field_body(root: Path) -> None:
    result = demo_lane.perform_demo_lane_action(root, {"action": "STOP", "idempotency_key": "s1"})
    assert result == {"schema_version": 2, "ok": True, "action": "STOP", "state": "STOPPED"}
    assert (root / demo_lane.KILL_SWITCH).is_file()
    # Detailed audit is retained on disk only, never in the response.
    audit = json.loads((root / demo_lane.AUDIT_PATH).read_text().splitlines()[0])
    assert audit["action"] == "STOP"
    assert "recorded" not in result and "detail" not in result and "idempotency_key" not in result


def test_start_action_returns_exact_body_and_spawns_once(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spawned: list[str] = []

    class FakeProcess:
        pid = 9999

    monkeypatch.setattr(
        demo_lane, "_spawn", lambda _r, mode: (spawned.append(mode), FakeProcess())[1]
    )
    result = demo_lane.perform_demo_lane_action(root, {"action": "START", "idempotency_key": "k1"})
    assert spawned == ["--loop"]
    assert set(result) == {"schema_version", "ok", "action", "state"}
    assert result["ok"] is True and result["action"] == "START"
    assert "9999" not in json.dumps(result)


def test_run_once_returns_exact_body(root: Path) -> None:
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "RUN_ONCE", "idempotency_key": "r1"}
    )
    assert set(result) == {"schema_version", "ok", "action", "state"}
    assert result["action"] == "RUN_ONCE" and result["ok"] is True


# --- START_ACTIVITY: fixed-argv confluence lane (extends the D-106 audited spawn surface) --------


def test_start_activity_spawns_exact_fixed_argv_and_is_audited(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """START_ACTIVITY spawns `demo_eth_lane.py --activity --loop --interval 5m` with a fixed argv
    (no request value reaches it), returns the four-field body, and is audited like the rest."""
    captured: dict[str, Any] = {}

    class FakePopen:
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 7777

    monkeypatch.setattr(demo_lane.subprocess, "Popen", FakePopen)
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "START_ACTIVITY", "idempotency_key": "a1"}
    )
    assert captured["argv"] == [
        sys.executable,
        str(root / demo_lane.LANE_SCRIPT),
        "--activity",
        "--loop",
        "--interval",
        "5m",
    ]
    assert captured["kwargs"].get("shell") in (None, False)  # never a shell
    assert set(result) == {"schema_version", "ok", "action", "state"}
    assert result["action"] == "START_ACTIVITY" and result["ok"] is True
    assert "7777" not in json.dumps(result)  # pid never leaks into the body
    audit = json.loads((root / demo_lane.AUDIT_PATH).read_text().splitlines()[-1])
    assert audit["action"] == "START_ACTIVITY" and audit["idempotency_key"] == "a1"


def test_start_activity_refused_while_a_lane_holds_the_lock(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It shares lane.lock with the ETH/multi lanes, so it refuses to start a second lane."""
    import fcntl

    lock = root / demo_lane.LANE_LOCK
    lock.write_text(json.dumps({"pid": 4242}))
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr(
        demo_lane, "_spawn", lambda *_a, **_k: pytest.fail("must not spawn a second lane")
    )
    try:
        with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
            demo_lane.perform_demo_lane_action(
                root, {"action": "START_ACTIVITY", "idempotency_key": "a1"}
            )
        assert excinfo.value.status_code == 409
    finally:
        handle.close()


@pytest.mark.parametrize(
    "action",
    ["START_ACTIVITY_LIVE", "ACTIVITY", "START ACTIVITY", "STARTACTIVITY", "STOP_ACTIVITY"],
)
def test_mutated_activity_action_is_rejected_without_reflecting_it(root: Path, action: str) -> None:
    """A string that does not normalize to an allowlisted action is rejected generically."""
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(root, {"action": action, "idempotency_key": "k1"})
    assert action not in str(excinfo.value)
    assert str(excinfo.value) == "demo lane action is invalid"


def test_stop_writes_the_kill_switch_the_activity_lane_checks(root: Path) -> None:
    """STOP halts the confluence activity lane too: it writes the SAME KILL_SWITCH the activity
    lane honors via lane.kill_switch_active() (scripts/demo_eth_lane.py
    KILL_SWITCH = artifacts/trading_domain/demo_lane/KILL_SWITCH)."""
    assert demo_lane.KILL_SWITCH == Path("artifacts/trading_domain/demo_lane/KILL_SWITCH")
    result = demo_lane.perform_demo_lane_action(root, {"action": "STOP", "idempotency_key": "s1"})
    assert result["action"] == "STOP"
    assert (root / demo_lane.KILL_SWITCH).is_file()


# --- generic, non-reflecting handler errors ------------------------------------------


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


def test_invalid_action_error_does_not_reflect_the_request_value(root: Path) -> None:
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(root, {"action": "LAUNCH_LIVE", "idempotency_key": "k1"})
    assert "LAUNCH_LIVE" not in str(excinfo.value)
    assert str(excinfo.value) == "demo lane action is invalid"


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


# --- START / RUN_ONCE cannot clear a Stage B latch -----------------------------------


def test_start_and_run_once_cannot_clear_a_stage_b_latch(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dashboard controls only the operational kill switch; the Stage B ENTRY_BLOCK
    latch lives in the private evidence store the dashboard can neither read nor write."""
    entry_block = _projection("ENTRY_BLOCK", [])
    monkeypatch.setattr(demo_lane, "public_stage_b_projection", lambda _root: entry_block)
    private_root = root / "artifacts/evidence/private_demo/stage_b_v2"

    for action in ("START", "RUN_ONCE"):
        monkeypatch.setattr(
            demo_lane,
            "_spawn",
            lambda _r, mode: type("P", (), {"pid": 1})(),
        )
        demo_lane.perform_demo_lane_action(root, {"action": action, "idempotency_key": action})
        # The latch is unchanged and the action never touched the private runtime root.
        assert demo_lane.build_demo_lane(root)["stage_b"]["status"] == "ENTRY_BLOCK"
        assert not private_root.exists()


# --- confluence activity view (per-coin confidence) ----------------------------------


def _activity_heartbeat(
    root: Path,
    symbol: str,
    *,
    confidence: str,
    decision: str,
    bullish: list[dict[str, str]] | None = None,
    bearish: list[dict[str, str]] | None = None,
    long: bool = False,
) -> None:
    """Write a heartbeat_<SYMBOL>_activity.json shaped like run_activity_cycle's heartbeat_extra."""
    hb: dict[str, Any] = {
        "at": "2099-01-01T00:00:00+00:00",
        "symbol": symbol,
        "strategy": demo_lane.ACTIVITY_STRATEGY,
        "lane_base": "2" if long else "0",
        "mark_price": "110" if long else "0",
        "entry_price": "100" if long else None,
        "disaster_stop_price": "85" if long else None,
        "confluence": {
            "confidence": confidence,
            "bullish": bullish or [],
            "bearish": bearish or [],
            "entry_threshold": "0.25",
            "exit_threshold": "0.05",
            "timeframes": ["15m", "1h", "4h"],
            "reference_timeframe": "15m",
            "decision": decision,
        },
    }
    path = root / demo_lane.LANE_DIR / f"heartbeat_{symbol}_activity.json"
    path.write_text(json.dumps(hb))


def test_activity_covers_universe_sorted_by_confidence_desc(root: Path) -> None:
    _activity_heartbeat(root, "SOLUSDT", confidence="0.8", decision="BUY", long=True)
    _activity_heartbeat(root, "BTCUSDT", confidence="0.3", decision="HOLD")
    _activity_heartbeat(root, "ADAUSDT", confidence="-0.5", decision="SELL")
    lane = demo_lane.build_demo_lane(root)
    activity = lane["activity"]
    # Every activity-universe coin is present, exactly once, with the fixed field set.
    assert {r["symbol"] for r in activity} == set(demo_lane.ACTIVITY_COINS)
    assert len(activity) == len(demo_lane.ACTIVITY_COINS)
    assert all(set(r) == _ACTIVITY_KEYS for r in activity)
    # Strongest confidence first; every scored coin precedes every no-data (None) coin.
    scored = [r["confidence_score"] for r in activity if r["confidence_score"] is not None]
    assert scored == sorted(scored, reverse=True)
    assert scored[:3] == [0.8, 0.3, -0.5]
    none_index = next(i for i, r in enumerate(activity) if r["confidence_score"] is None)
    assert all(activity[i]["confidence_score"] is None for i in range(none_index, len(activity)))
    # No coin selector: build_demo_lane still takes only root.
    import inspect

    assert list(inspect.signature(demo_lane.build_demo_lane).parameters) == ["root"]


def test_activity_coin_projects_confidence_contributors_and_position(root: Path) -> None:
    bullish = [
        {"strategy": "EXT-KELTNER-BREAKOUT", "timeframe": "1h", "weight": "2"},
        {"strategy": "EXT-BB-BREAKOUT", "timeframe": "4h", "weight": "3"},
    ]
    bearish = [{"strategy": "SIG-VOLUME-BREAKOUT", "timeframe": "15m", "weight": "1"}]
    _activity_heartbeat(
        root,
        "SOLUSDT",
        confidence="0.75",
        decision="BUY",
        bullish=bullish,
        bearish=bearish,
        long=True,
    )
    sol = next(r for r in demo_lane.build_demo_lane(root)["activity"] if r["symbol"] == "SOLUSDT")
    assert sol["confidence_score"] == 0.75
    assert sol["decision"] == "BUY"
    # Contributors reduce to (strategy, timeframe) string pairs, order preserved.
    assert sol["bullish"] == [
        {"strategy": "EXT-KELTNER-BREAKOUT", "timeframe": "1h"},
        {"strategy": "EXT-BB-BREAKOUT", "timeframe": "4h"},
    ]
    assert sol["bearish"] == [{"strategy": "SIG-VOLUME-BREAKOUT", "timeframe": "15m"}]
    # Position reuses the same helpers as _coin_projection: 2 @ (110-100) = +20, +10%.
    assert sol["position"]["side"] == "LONG"
    assert sol["position"]["unrealised_pnl_usd"] == 20.0
    assert sol["position"]["unrealised_pnl_pct"] == 10.0
    assert sol["protection"]["disaster_stop_price_usd"] == 85.0


def test_activity_missing_or_malformed_heartbeat_degrades_gracefully(root: Path) -> None:
    # One malformed heartbeat (confluence not a dict, bad lane_base) plus the rest missing.
    bad = root / demo_lane.LANE_DIR / "heartbeat_ETHUSDT_activity.json"
    bad.write_text(json.dumps({"lane_base": "not-a-number", "confluence": ["not", "a", "dict"]}))
    activity = demo_lane.build_demo_lane(root)["activity"]
    assert {r["symbol"] for r in activity} == set(
        demo_lane.ACTIVITY_COINS
    )  # no crash, full universe
    eth = next(r for r in activity if r["symbol"] == "ETHUSDT")
    assert eth["confidence_score"] is None  # malformed confluence -> no score
    assert eth["decision"] is None
    assert eth["position"]["side"] == "FLAT"  # bad lane_base -> 0 -> flat
    btc = next(r for r in activity if r["symbol"] == "BTCUSDT")
    assert btc["data_available"] is False  # no file at all
    assert btc["confidence_score"] is None
    assert btc["position"]["side"] == "FLAT"


def test_activity_summary_sums_and_stage_b_stays_aggregate_only(root: Path) -> None:
    _activity_heartbeat(root, "SOLUSDT", confidence="0.8", decision="BUY", long=True)
    _activity_heartbeat(root, "BTCUSDT", confidence="0.4", decision="BUY", long=True)
    _activity_heartbeat(root, "ADAUSDT", confidence="-0.2", decision="SELL")
    lane = demo_lane.build_demo_lane(root)
    summary = lane["activity_summary"]
    assert summary["coins_scored"] == 3
    assert summary["coins_long"] == 2
    assert summary["highest_confidence"] == 0.8
    assert summary["average_confidence"] == round((0.8 + 0.4 - 0.2) / 3, 4)
    # Adding the activity view must NOT touch the aggregate-only, redacted stage_b field.
    assert set(lane["stage_b"]) == _STAGE_B_KEYS
    assert lane["stage_b"] == {"status": "NOT_ACTIVATED", "cohort_size": 30, "series": []}
    stage_b_body = json.dumps(lane["stage_b"]).lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in stage_b_body, f"forbidden token leaked into stage_b: {token}"
