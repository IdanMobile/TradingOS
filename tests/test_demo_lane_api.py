"""Tests for the rich multi-coin demo-lane operator projection and bounded controls.

GET /api/v1/demo-lane returns the top-level safety envelope, a rich per-coin operator view
(`coins`) with a `portfolio` roll-up, and the fixed, fail-closed Stage B readiness object.
The `stage_b` EVIDENCE field stays aggregate-only and redacted even though the operator view is
rich. The action handler returns exactly four fixed fields.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tios.services.dashboard_api import demo_lane
from tios.services.dashboard_ui.server import Handler

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


# --- START_MULTI: fixed-argv multi-coin order-path lane (extends the D-106 audited spawn) --------


def test_start_multi_spawns_exact_fixed_argv_and_is_audited(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """START_MULTI spawns `demo_eth_lane.py --multi` with a fixed argv (no request value reaches
    it), returns the four-field body, and is audited like the rest of the D-106 surface."""
    captured: dict[str, Any] = {}

    class FakePopen:
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 8888

    monkeypatch.setattr(demo_lane.subprocess, "Popen", FakePopen)
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "START_MULTI", "idempotency_key": "m1"}
    )
    assert captured["argv"] == [sys.executable, str(root / demo_lane.LANE_SCRIPT), "--multi"]
    assert captured["kwargs"].get("shell") in (None, False)  # never a shell
    assert set(result) == {"schema_version", "ok", "action", "state"}
    assert result["action"] == "START_MULTI" and result["ok"] is True
    assert "8888" not in json.dumps(result)  # pid never leaks into the body
    audit = json.loads((root / demo_lane.AUDIT_PATH).read_text().splitlines()[-1])
    assert audit["action"] == "START_MULTI" and audit["idempotency_key"] == "m1"


def test_start_multi_refused_while_a_lane_holds_the_lock(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It shares lane.lock with the ETH/activity lanes, so it refuses to start a second lane."""
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
                root, {"action": "START_MULTI", "idempotency_key": "m1"}
            )
        assert excinfo.value.status_code == 409
    finally:
        handle.close()


# --- START_RESEARCH: fixed-argv offline search, own lock file (NOT lane.lock) ---------------------
# Two layers: the dashboard PID probe (fast 409, tested here) and the search script's own flock
# (exit 3, the actual single-run guarantee — tested in the section below).


def test_start_research_spawns_exact_fixed_argv_and_is_audited(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """START_RESEARCH spawns `run_universe_search.py` with a fixed no-flag argv (no request value
    reaches it), records the research guard lock, returns the four-field body, and is audited."""
    (root / demo_lane.RESEARCH_SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (root / demo_lane.RESEARCH_SCRIPT).write_text("# stand-in research script\n")
    captured: dict[str, Any] = {}

    class FakePopen:
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.pid = 6666

    monkeypatch.setattr(demo_lane.subprocess, "Popen", FakePopen)
    result = demo_lane.perform_demo_lane_action(
        root, {"action": "START_RESEARCH", "idempotency_key": "r1"}
    )
    # Fixed argv: interpreter + the research script, no flags, no request/user value.
    assert captured["argv"] == [sys.executable, str(root / demo_lane.RESEARCH_SCRIPT)]
    assert captured["kwargs"].get("shell") in (None, False)
    assert set(result) == {"schema_version", "ok", "action", "state"}
    assert result["action"] == "START_RESEARCH" and result["ok"] is True
    assert "6666" not in json.dumps(result)  # pid never leaks into the body
    # The research guard lock records the pid so a second search can be refused.
    lock = json.loads((root / demo_lane.RESEARCH_LOCK).read_text())
    assert lock["pid"] == 6666
    audit = json.loads((root / demo_lane.AUDIT_PATH).read_text().splitlines()[-1])
    assert audit["action"] == "START_RESEARCH" and audit["idempotency_key"] == "r1"


def test_start_research_does_not_touch_lane_lock(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held lane.lock (a demo lane running) must NOT block a research search — they are separate
    surfaces; research uses its own guard, not lane.lock."""
    import fcntl

    (root / demo_lane.RESEARCH_SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (root / demo_lane.RESEARCH_SCRIPT).write_text("# stand-in research script\n")
    lock = root / demo_lane.LANE_LOCK
    lock.write_text(json.dumps({"pid": 4242}))
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    class FakePopen:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            self.pid = 6667

    monkeypatch.setattr(demo_lane.subprocess, "Popen", FakePopen)
    try:
        result = demo_lane.perform_demo_lane_action(
            root, {"action": "START_RESEARCH", "idempotency_key": "r1"}
        )
        assert result["action"] == "START_RESEARCH" and result["ok"] is True
    finally:
        handle.close()


def test_start_research_refused_while_a_research_run_is_in_progress(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The research guard refuses a second search while a live one is recorded (409), and never
    spawns."""
    (root / demo_lane.RESEARCH_SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (root / demo_lane.RESEARCH_SCRIPT).write_text("# stand-in research script\n")
    # os.getpid() is a definitely-alive pid, so the PID-liveness guard reports the run as running.
    (root / demo_lane.RESEARCH_LOCK).parent.mkdir(parents=True, exist_ok=True)
    (root / demo_lane.RESEARCH_LOCK).write_text(json.dumps({"pid": os.getpid()}))
    monkeypatch.setattr(
        demo_lane,
        "_spawn_research",
        lambda *_a, **_k: pytest.fail("must not spawn a second search"),
    )
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(
            root, {"action": "START_RESEARCH", "idempotency_key": "r2"}
        )
    assert excinfo.value.status_code == 409


def test_start_research_missing_script_is_unavailable_not_a_crash(root: Path) -> None:
    """No research script present -> 503, never a crash (no stand-in script is written here)."""
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(
            root, {"action": "START_RESEARCH", "idempotency_key": "r1"}
        )
    assert excinfo.value.status_code == 503


@pytest.mark.parametrize(
    "pid",
    [10**40, True, 0, -1, "not-an-int", None],
    ids=["huge", "bool", "zero", "negative", "string", "none"],
)
def test_research_guard_never_crashes_on_a_hostile_lock_file(root: Path, pid: object) -> None:
    """A corrupt/hostile RESEARCH_LOCK pid (huge int -> OverflowError, bool, non-positive, wrong
    type) must fail closed to 'not running', never raise, so the guard can't crash the endpoint."""
    (root / demo_lane.RESEARCH_LOCK).parent.mkdir(parents=True, exist_ok=True)
    (root / demo_lane.RESEARCH_LOCK).write_text(json.dumps({"pid": pid}))
    assert demo_lane._research_running(root) is False


# --- the search script's OWN flock: the real single-run guarantee (dashboard 409 is only fast) ----


def _search_module(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """run_universe_search with its lock + report redirected into tmp (never the real artifacts)."""
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1])
    )  # scripts/ isn't installed
    import scripts.run_universe_search as search

    out = tmp / "universe_search"
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(search, "OUT", out)
    monkeypatch.setattr(search, "RUN_LOCK", out / ".research_run.lock")
    monkeypatch.setattr(search, "REPORT", out / "UNIVERSE_SEARCH_TRAIN_SELECT_V2_2026_07_13.json")
    return search


def test_second_concurrent_search_exits_3_and_writes_no_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held flock makes the search refuse with exit code 3 without running the search or touching
    the report / the live run's lock record — no full search is ever executed here."""
    import fcntl

    search = _search_module(tmp_path, monkeypatch)
    monkeypatch.setattr(
        search, "build_report", lambda: pytest.fail("a second search must not run the search")
    )
    search.REPORT.write_text("PRIOR REPORT\n")  # a live run's output must survive untouched
    search.RUN_LOCK.write_text(json.dumps({"pid": 4242}))
    handle = search.RUN_LOCK.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert search.main() == 3
    finally:
        handle.close()
    assert search.REPORT.read_text() == "PRIOR REPORT\n"
    assert json.loads(search.RUN_LOCK.read_text())["pid"] == 4242  # not truncated by the refusal


def test_search_lock_acquires_records_pid_and_releases_even_on_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first acquisition succeeds and records its pid, and the lock is released on normal exit AND
    after an exception (flock is per-open-file-description, so a fresh open really re-locks)."""
    search = _search_module(tmp_path, monkeypatch)
    with search.exclusive_search_lock() as acquired:
        assert acquired is True
        assert json.loads(search.RUN_LOCK.read_text())["pid"] == os.getpid()
    with pytest.raises(RuntimeError):
        with search.exclusive_search_lock() as acquired:
            assert acquired is True
            raise RuntimeError("boom")
    with search.exclusive_search_lock() as acquired:
        assert acquired is True  # released cleanly after both the normal exit and the exception


def test_single_run_writes_the_same_report_path_and_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The uncontended path is unchanged: exit 0, same filename, same indent=2/sort_keys JSON with a
    trailing newline (build_report is stubbed — no real search runs)."""
    search = _search_module(tmp_path, monkeypatch)
    report = {
        "dataset_count": 2,
        "pairs": ["BTCUSDT"],
        "strategy_count": 37,
        "context_pass_count": 0,
        "context_passes": [],
    }
    monkeypatch.setattr(search, "build_report", lambda: report)
    assert search.main() == 0
    assert search.REPORT.name == "UNIVERSE_SEARCH_TRAIN_SELECT_V2_2026_07_13.json"
    assert search.REPORT.read_text() == json.dumps(report, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize(
    "action",
    ["START_MULTI_LIVE", "MULTI", "START MULTI", "START_RESEARCH_LIVE", "RESEARCH", "RUN_RESEARCH"],
)
def test_mutated_multi_research_action_is_rejected_without_reflecting_it(
    root: Path, action: str
) -> None:
    """A string that does not normalize to an allowlisted action is rejected generically, without
    reflecting the request value back."""
    with pytest.raises(demo_lane.DemoLaneActionError) as excinfo:
        demo_lane.perform_demo_lane_action(root, {"action": action, "idempotency_key": "k1"})
    assert action not in str(excinfo.value)
    assert str(excinfo.value) == "demo lane action is invalid"


# --- read-only VIEW endpoints (no subprocess): schema_version 1 + graceful degradation -----------


def _write_universe_report(root: Path, contexts: list[dict[str, Any]]) -> None:
    path = root / demo_lane.RESEARCH_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "tios-universe-search-v2",
                "dataset_count": 3,
                "pairs": ["BTCUSDT", "ETHUSDT"],
                "context_passes": [{"strategy_id": "EXT-KELTNER-BREAKOUT", "contexts": contexts}],
            }
        )
    )


def test_demo_trades_view_schema_version_1_with_report(root: Path) -> None:
    _long_coin_files(root, "ETHUSDT")  # one open ETH buy -> an OPEN round trip
    view = demo_lane.build_demo_trades_view(root)
    assert view["schema_version"] == 1  # matches the client fetchJson gate
    assert view["available"] is True
    report = view["report"]
    assert report["schema"] == "tios.demo_trade_report.v1"
    assert report["execution_authority"] == "NONE" and report["real_money"] is False
    assert isinstance(report["round_trips"], list)
    assert set(report["summary"]) >= {"closed_trades", "open_trades", "realised_pnl_usd"}


def test_demo_status_view_schema_version_1_with_report(root: Path) -> None:
    _long_coin_files(root, "ETHUSDT")
    view = demo_lane.build_demo_status_view(root)
    assert view["schema_version"] == 1
    assert view["available"] is True
    report = view["report"]
    assert report["schema"] == "tios.demo_status_report.v1"
    assert report["execution_authority"] == "NONE" and report["real_money"] is False
    assert report["position"]["side"] == "LONG"  # the open ETH buy is reflected
    assert "trade_history" in report and "protection" in report


def test_research_findings_view_schema_version_1_and_preserves_honest_framing(root: Path) -> None:
    _write_universe_report(root, [{"dataset": "BTCUSDT_1d", "holdout_total_return": 0.5}])
    view = demo_lane.build_research_findings_view(root)
    assert view["schema_version"] == 1
    assert view["available"] is True
    report = view["report"]
    assert report["schema"] == "tios.research_findings_summary.v1"
    # Honest framing is carried through verbatim, not stripped.
    assert report["validated"] is False
    assert report["promotion_eligible"] is False
    assert report["execution_authority"] == "NONE"
    assert report["evidence_scope"] == "CONTEXT_LEVEL_EXPLORATORY_SCREEN"
    body = json.dumps(report).lower()
    assert "multiple testing" in body and "cross-coin correlation" in body


def test_research_findings_view_degrades_when_source_missing(root: Path) -> None:
    # No universe-search report in this tmp root -> the pure function returns its own honest
    # 'no report' shape; the view still returns schema_version 1 and never crashes.
    view = demo_lane.build_research_findings_view(root)
    assert view["schema_version"] == 1
    assert view["available"] is True
    assert view["report"].get("error") == "no universe-search report"


@pytest.mark.parametrize(
    "builder",
    ["build_demo_trades_view", "build_demo_status_view"],
)
def test_views_fail_closed_on_malformed_source(root: Path, builder: str) -> None:
    # A malformed orders ledger makes the report function raise; the view must degrade to a safe
    # unavailable shape (schema_version 1, available False, report None) — never a 500 or a leak.
    (root / demo_lane.ORDERS_LEDGER).write_text("{not valid json\n")
    view = getattr(demo_lane, builder)(root)
    assert view["schema_version"] == 1
    assert view["available"] is False
    assert view["report"] is None


def test_views_are_pure_reads_no_subprocess(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The VIEW endpoints must never spawn a process — they are library calls only."""
    monkeypatch.setattr(
        demo_lane.subprocess, "Popen", lambda *_a, **_k: pytest.fail("view must not spawn")
    )
    monkeypatch.setattr(
        demo_lane.subprocess, "run", lambda *_a, **_k: pytest.fail("view must not spawn")
    )
    demo_lane.build_demo_trades_view(root)
    demo_lane.build_demo_status_view(root)
    demo_lane.build_research_findings_view(root)


# --- GET /api/v1/live-feed + /api/v1/equity-curve ------------------------------------------------
# Both are pure read-only projections of artifacts the lane already wrote: no subprocess, no write,
# no request-derived path. Every response carries schema_version 1 and fails closed to a safe empty
# shape rather than raising.

_FEED_KEYS = {
    "schema_version",
    "available",
    "generated_at",
    "lane",
    "events",
    "event_count",
    "truncated",
}
_FEED_LANE_KEYS = {
    "status",
    "mode",
    "kill_switch",
    "coins_scored",
    "last_scan_utc",
    "scan_age_seconds",
    "next_scan_eta_seconds",
}
_FEED_EVENT_KEYS = {
    "at",
    "age_seconds",
    "kind",
    "symbol",
    "headline",
    "detail",
    "agreement",
    "pnl_pct",
    "ok",
}
_CURVE_KEYS = {"schema_version", "available", "points", "summary", "disclaimer"}
_CURVE_POINT_KEYS = {"at", "trade_number", "cumulative_net_quote", "net_quote", "symbol"}
_CURVE_SUMMARY_KEYS = {
    "closed_count",
    "wins",
    "losses",
    "flat",
    "realised_net_quote",
    "fees_quote",
    "win_rate_pct",
}
# A secret-shaped venue message: the feed must never echo it back to the client.
_LEAKY_ERROR = "/Users/secret/.env BYBIT_API_KEY=abcd1234 pid=4242 rejected"


def _feed_order(**overrides: Any) -> dict[str, Any]:
    """One orders.jsonl record shaped exactly like scripts/demo_eth_lane._append_ledger writes."""
    order: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at": "2026-07-20T10:00:00+00:00",
        "symbol": "TRXUSDT",
        "side": "Buy",
        "unit": "quoteCoin",
        "signal_ref": "SIG-plain",
        "reason": "ENTRY_LONG",
        "strategy": demo_lane.ACTIVITY_STRATEGY,
        "ok": True,
        "stage": "done",
        "qty": "25",
        "order_id": "2263422258146184448",
        "order_status": "Filled",
        "avg_price": "0.30",
        "fee": "0.0001",
        "reconcile": {"USDT_delta": -25.0, "TRX_delta": 83.0},
        "wallet_after": {"USDT": "975.0", "TRX": "83.0"},
    }
    order.update(overrides)
    return order


def _write_feed_orders(root: Path, orders: list[dict[str, Any]]) -> None:
    (root / demo_lane.ORDERS_LEDGER).write_text(
        "\n".join(json.dumps(order) for order in orders) + "\n"
    )


def _scan_heartbeat(root: Path, symbol: str, at: datetime, agreement: str, bar: str) -> None:
    """A heartbeat_<SYMBOL>_activity.json shaped like run_activity_cycle's heartbeat_extra."""
    (root / demo_lane.LANE_DIR / f"heartbeat_{symbol}_activity.json").write_text(
        json.dumps(
            {
                "at": at.isoformat(),
                "symbol": symbol,
                "strategy": demo_lane.ACTIVITY_STRATEGY,
                "lane_base": "0",
                "latest_closed_bar": bar,
                "confluence": {
                    "confidence": agreement,
                    "bullish": [
                        {"strategy": "EXT-KELTNER-BREAKOUT", "timeframe": "1h", "weight": "2"},
                        {"strategy": "EXT-EMA-8-21", "timeframe": "15m", "weight": "1"},
                    ],
                    "bearish": [],
                    "entry_threshold": "0.15",
                    "exit_threshold": "0.05",
                    "timeframes": ["5m", "15m", "1h"],
                    "reference_timeframe": "5m",
                    "decision": "BUY",
                },
            }
        )
    )


def test_live_feed_contract_keys_and_newest_first(root: Path) -> None:
    """(a) schema_version 1, the documented key set, and events strictly newest-first."""
    _write_feed_orders(
        root,
        [
            _feed_order(recorded_at="2026-07-20T10:00:00+00:00"),
            _feed_order(
                recorded_at="2026-07-21T10:00:00+00:00",
                side="Sell",
                reason="EXIT_LONG",
                reconcile={"USDT_delta": 26.0, "TRX_delta": -83.0},
            ),
            _feed_order(recorded_at="2026-07-22T10:00:00+00:00"),
        ],
    )
    feed = demo_lane.build_live_feed(root)
    assert feed["schema_version"] == 1  # matches the client fetchJson gate
    assert set(feed) == _FEED_KEYS
    assert feed["available"] is True
    assert set(feed["lane"]) == _FEED_LANE_KEYS
    assert feed["lane"]["status"] in {"RUNNING", "STOPPED"}
    assert feed["lane"]["mode"] in {"ACTIVITY", "ETH", "MULTI", "NONE"}
    assert all(set(event) == _FEED_EVENT_KEYS for event in feed["events"])
    ages = [event["age_seconds"] for event in feed["events"]]
    assert ages == sorted(ages)  # smallest age first == newest first
    assert [event["at"] for event in feed["events"]] == [
        "2026-07-22T10:00:00+00:00",
        "2026-07-21T10:00:00+00:00",
        "2026-07-20T10:00:00+00:00",
    ]
    assert feed["event_count"] == 3 and feed["truncated"] is False
    # No 'confidence' vocabulary anywhere: the frontend calls this AGREEMENT.
    assert "confidence" not in json.dumps(feed).lower()


def test_live_feed_projects_enter_exit_reject_without_leaking(root: Path) -> None:
    """(b) a seeded ledger produces the expected kinds/symbols/pnl/detail and leaks nothing."""
    _write_feed_orders(
        root,
        [
            _feed_order(
                recorded_at="2026-07-20T10:00:00+00:00",
                signal_ref="ACT-CONF:0.4300:2026-07-20T09:55:00+00:00",
            ),
            _feed_order(
                recorded_at="2026-07-20T12:00:00+00:00",
                side="Sell",
                reason="EXIT_LONG",
                signal_ref="ACT-CONF:0.0300:2026-07-20T11:55:00+00:00",
                reconcile={"USDT_delta": 26.0, "TRX_delta": -83.0},
            ),
            _feed_order(
                recorded_at="2026-07-20T13:00:00+00:00",
                symbol="SOLUSDT",
                ok=False,
                stage="place",
                error=_LEAKY_ERROR,
                reconcile={},
            ),
        ],
    )
    feed = demo_lane.build_live_feed(root)
    by_kind = {event["kind"]: event for event in feed["events"]}
    assert set(by_kind) == {"ENTER", "EXIT", "REJECT"}

    enter = by_kind["ENTER"]
    assert enter["symbol"] == "TRXUSDT" and enter["headline"] == "TRX long opened"
    assert enter["agreement"] == "0.4300" and enter["ok"] is True
    assert "agreement 0.4300" in enter["detail"]

    exit_event = by_kind["EXIT"]
    assert exit_event["headline"] == "TRX long closed"
    assert exit_event["detail"] == "agreement fell to 0.0300"
    assert exit_event["pnl_pct"] == "4.0"  # (26.00 - 25.00) / 25.00 * 100

    reject = by_kind["REJECT"]
    assert reject["symbol"] == "SOLUSDT" and reject["ok"] is False
    assert reject["headline"] == "SOL order rejected"
    assert reject["detail"] == "the venue rejected the order"  # fixed phrase, not the venue text

    body = json.dumps(feed)
    for secret in ("BYBIT_API_KEY", "abcd1234", "/Users/", "pid=", "2263422258146184448", "975.0"):
        assert secret not in body, f"live feed leaked {secret!r}"


def test_live_feed_emits_one_scan_per_cycle_not_per_coin(root: Path) -> None:
    """(c) SCAN events are per scan CYCLE, reporting scored and at/above-gate counts."""
    now = datetime.now(tz=UTC)
    current_bar = "2026-07-24T12:00:00+00:00"
    older_bar = "2026-07-24T11:55:00+00:00"
    # Current cycle: three coins written seconds apart -> ONE SCAN event, two above the 0.15 gate.
    _scan_heartbeat(root, "TRXUSDT", now - timedelta(seconds=6), "0.4000", current_bar)
    _scan_heartbeat(root, "SOLUSDT", now - timedelta(seconds=4), "0.2000", current_bar)
    _scan_heartbeat(root, "ADAUSDT", now - timedelta(seconds=2), "-0.1000", current_bar)
    # An earlier cycle (a coin whose file was not refreshed) is its own SCAN, not merged in.
    _scan_heartbeat(root, "XRPUSDT", now - timedelta(minutes=10), "0.9000", older_bar)

    feed = demo_lane.build_live_feed(root)
    scans = [event for event in feed["events"] if event["kind"] == "SCAN"]
    assert len(scans) == 2  # two cycles, forty coin files would still be two events
    newest = scans[0]
    assert newest["symbol"] is None
    assert newest["headline"] == "3 coins scored"
    assert newest["detail"] == "3 coins scored - 2 above the agreement gate (0.15)"
    assert newest["agreement"] == "0.4000"  # strongest agreement in the cycle
    assert scans[1]["detail"] == "1 coins scored - 1 above the agreement gate (0.15)"

    # mode/cadence are inferred from the FRESH confluence heartbeats, 5m reference timeframe.
    lane = feed["lane"]
    assert lane["mode"] == "ACTIVITY"
    assert lane["coins_scored"] == 3
    assert lane["last_scan_utc"] is not None and lane["scan_age_seconds"] is not None
    assert lane["status"] == "STOPPED"  # no lane process holds the lock in this tmp root
    assert lane["next_scan_eta_seconds"] is None  # ETA only while the lane is running


def test_live_feed_caps_events_and_flags_truncated(root: Path) -> None:
    """(d) the newest LIVE_FEED_EVENT_LIMIT events are returned and `truncated` is set."""
    base = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    stamps = [
        (base + timedelta(minutes=minute)).isoformat()
        for minute in range(demo_lane.LIVE_FEED_EVENT_LIMIT + 5)
    ]
    _write_feed_orders(root, [_feed_order(recorded_at=stamp) for stamp in stamps])
    feed = demo_lane.build_live_feed(root)
    assert len(feed["events"]) == demo_lane.LIVE_FEED_EVENT_LIMIT
    assert feed["event_count"] == demo_lane.LIVE_FEED_EVENT_LIMIT
    assert feed["truncated"] is True
    assert feed["events"][0]["at"] == stamps[-1]  # newest kept
    assert feed["events"][-1]["at"] == stamps[5]  # the five oldest were dropped


def test_live_feed_and_equity_curve_degrade_on_missing_artifacts(root: Path) -> None:
    """(e1) an empty lane directory yields the safe empty shape, never a raise."""
    feed = demo_lane.build_live_feed(root)
    assert feed["schema_version"] == 1 and feed["events"] == []
    assert feed["event_count"] == 0 and feed["truncated"] is False
    assert feed["lane"]["status"] == "STOPPED" and feed["lane"]["mode"] == "NONE"
    assert feed["lane"]["coins_scored"] == 0 and feed["lane"]["last_scan_utc"] is None
    curve = demo_lane.build_equity_curve(root)
    assert curve["schema_version"] == 1 and curve["points"] == []
    assert curve["summary"]["closed_count"] == 0
    assert curve["summary"]["realised_net_quote"] == "0.0000"
    assert curve["disclaimer"] == demo_lane.DEMO_DISCLAIMER


def test_live_feed_and_equity_curve_fail_closed_on_malformed_artifacts(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(e2) a defect on either read path degrades to available False — never a 500/traceback."""
    (root / demo_lane.ORDERS_LEDGER).write_text("{not valid json\n")
    curve = demo_lane.build_equity_curve(root)
    assert curve["schema_version"] == 1 and curve["available"] is False
    assert curve["points"] == [] and curve["summary"]["closed_count"] == 0
    assert curve["disclaimer"] == demo_lane.DEMO_DISCLAIMER

    def boom(_root: Path) -> list[dict[str, Any]]:
        raise OSError("ledger exploded")

    monkeypatch.setattr(demo_lane, "_orders", boom)
    feed = demo_lane.build_live_feed(root)
    assert feed["schema_version"] == 1 and feed["available"] is False
    assert set(feed) == _FEED_KEYS and feed["events"] == []
    assert feed["lane"]["status"] == "STOPPED" and feed["lane"]["mode"] == "NONE"
    assert "exploded" not in json.dumps(feed)


def test_equity_curve_is_oldest_first_and_agrees_with_report_demo_trades(root: Path) -> None:
    """(f) points run oldest->newest with a correct running total; summary == the report's."""
    _write_feed_orders(
        root,
        [
            # +5 WIN
            _feed_order(recorded_at="2026-07-20T10:00:00+00:00", symbol="ETHUSDT"),
            _feed_order(
                recorded_at="2026-07-20T12:00:00+00:00",
                symbol="ETHUSDT",
                side="Sell",
                reason="EXIT_LONG",
                fee="0.03",
                reconcile={"USDT_delta": 30.0, "ETH_delta": -0.0134},
            ),
            # -5 LOSS
            _feed_order(recorded_at="2026-07-21T10:00:00+00:00", symbol="ETHUSDT"),
            _feed_order(
                recorded_at="2026-07-21T12:00:00+00:00",
                symbol="ETHUSDT",
                side="Sell",
                reason="EXIT_LONG",
                fee="0.02",
                reconcile={"USDT_delta": 20.0, "ETH_delta": -0.0134},
            ),
            # trailing unmatched buy -> OPEN, excluded from the curve
            _feed_order(recorded_at="2026-07-22T10:00:00+00:00", symbol="ETHUSDT"),
        ],
    )
    curve = demo_lane.build_equity_curve(root)
    assert set(curve) == _CURVE_KEYS
    assert curve["schema_version"] == 1 and curve["available"] is True
    points = curve["points"]
    assert all(set(point) == _CURVE_POINT_KEYS for point in points)
    assert [point["trade_number"] for point in points] == [1, 2]  # oldest -> newest, closed only
    assert [point["at"] for point in points] == [
        "2026-07-20T12:00:00+00:00",
        "2026-07-21T12:00:00+00:00",
    ]
    assert [point["net_quote"] for point in points] == ["5.0000", "-5.0000"]
    assert [point["cumulative_net_quote"] for point in points] == ["5.0000", "0.0000"]
    assert points[0]["symbol"] == "ETHUSDT"

    summary = curve["summary"]
    assert set(summary) == _CURVE_SUMMARY_KEYS
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import scripts.report_demo_trades as rpt

    report = rpt.build_report(root / demo_lane.ORDERS_LEDGER)["summary"]
    assert summary["closed_count"] == report["closed_trades"] == 2
    assert summary["wins"] == report["wins"] == 1
    assert summary["losses"] == report["losses"] == 1
    assert summary["flat"] == report["flats"] == 0
    assert summary["realised_net_quote"] == f"{report['realised_pnl_usd']:.4f}"
    assert summary["fees_quote"] == f"{report['total_fees_usd']:.4f}"
    assert summary["win_rate_pct"] == f"{report['win_rate_pct']:.1f}" == "50.0"
    # Decimal-safe: every money/number field is a STRING, so no float drift reaches the client.
    assert all(isinstance(point["cumulative_net_quote"], str) for point in points)
    assert isinstance(summary["realised_net_quote"], str)


def test_equity_curve_carries_the_unvalidated_disclaimer(root: Path) -> None:
    """(g) the disclaimer is present, non-empty, and names demo P&L as non-evidence."""
    for curve in (demo_lane.build_equity_curve(root), demo_lane._empty_equity_curve()):
        disclaimer = curve["disclaimer"]
        assert isinstance(disclaimer, str) and disclaimer
        assert "NOT validated edge" in disclaimer
        assert "not evidence" in disclaimer.lower()


def test_live_feed_and_equity_curve_never_spawn_a_subprocess(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(h) both endpoints are pure reads — a spawn would be a governance break."""
    monkeypatch.setattr(
        demo_lane.subprocess, "Popen", lambda *_a, **_k: pytest.fail("feed must not spawn")
    )
    monkeypatch.setattr(
        demo_lane.subprocess, "run", lambda *_a, **_k: pytest.fail("feed must not spawn")
    )
    _write_feed_orders(root, [_feed_order()])
    assert demo_lane.build_live_feed(root)["schema_version"] == 1
    assert demo_lane.build_equity_curve(root)["schema_version"] == 1


def _handle_get(path: str, root: Path) -> tuple[bytes, dict[str, Any]]:
    handler = object.__new__(Handler)
    handler.root = root
    handler.html = "dashboard"
    handler.rfile = BytesIO(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    handler.wfile = BytesIO()
    handler.client_address = ("127.0.0.1", 1)
    handler.server = SimpleNamespace(server_name="test", server_port=80)
    handler.close_connection = True
    handler.handle_one_request()
    headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
    return headers, json.loads(body)


@pytest.mark.parametrize("path", ["/api/v1/live-feed", "/api/v1/equity-curve"])
def test_new_routes_serve_schema_version_1_through_the_real_handler(path: str, root: Path) -> None:
    """(i) end-to-end through the real GET handler: 200 JSON with schema_version 1."""
    _write_feed_orders(root, [_feed_order()])
    headers, payload = _handle_get(path, root)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    assert payload["schema_version"] == 1


# --- GET /api/v1/wallet --------------------------------------------------------------------------
# The operator's money questions: what the venue holds, what was spent, what one trade may spend,
# and what is open right now. Pure read-only projection of orders.jsonl + the per-coin heartbeats,
# schema_version 1, fail-closed. The VENUE balance (pre-funded fake money) and the LANE BUDGET are
# separate blocks and are never added together.

_WALLET_KEYS = {
    "schema_version",
    "available",
    "as_of",
    "environment",
    "real_money",
    "execution_authority",
    "venue",
    "budget",
    "positions",
    "realised",
    "unrealised_total_usdt",
    "disclaimer",
}
_WALLET_VENUE_KEYS = {
    "name",
    "environment_label",
    "api_host",
    "url",
    "balances",
    "quote_usdt",
    "quote_usdc",
    "cash_total_usdt",
    "note",
}
_WALLET_BALANCE_KEYS = {"coin", "amount", "is_quote"}
_WALLET_BUDGET_KEYS = {
    "total_cap_usdt",
    "per_trade_usdt",
    "deployed_usdt",
    "free_usdt",
    "slots_total",
    "slots_used",
    "slots_free",
    "disaster_stop_pct",
}
_WALLET_POSITION_KEYS = {
    "symbol",
    "strategy",
    "opened_at",
    "held_seconds",
    "size_base",
    "entry_price",
    "mark_price",
    "spent_usdt",
    "value_usdt",
    "unrealised_usdt",
    "unrealised_pct",
    "stop_price",
    "distance_to_stop_pct",
}
_WALLET_REALISED_KEYS = {"closed_count", "wins", "losses", "realised_usdt", "fees_usdt"}
# Nothing identifying may reach the client: no venue order id, no signal ref, no filesystem path,
# no pid, no credential.
_WALLET_FORBIDDEN = ("order_id", "signal_ref", "/Users/", "pid", "key", "2263422258146184448")


def _wallet_buy(symbol: str, at: str, price: str, base: float, **overrides: Any) -> dict[str, Any]:
    """One 25-USDT confluence entry fill on `symbol` (the only shape the lane ever writes)."""
    order = _feed_order(
        symbol=symbol,
        recorded_at=at,
        avg_price=price,
        reconcile={"USDT_delta": -25.0, f"{symbol.removesuffix('USDT')}_delta": base},
    )
    order.update(overrides)
    return order


def _wallet_sell(symbol: str, at: str, price: str, base: float, received: float) -> dict[str, Any]:
    return _feed_order(
        symbol=symbol,
        recorded_at=at,
        side="Sell",
        reason="EXIT_LONG",
        avg_price=price,
        fee="0.02",
        reconcile={"USDT_delta": received, f"{symbol.removesuffix('USDT')}_delta": -base},
    )


def _mark_files(root: Path, symbol: str, mark: str, entry: str, resting: str | None = None) -> None:
    """The coin's confluence heartbeat — the ONLY source of a live mark this endpoint reads."""
    payload: dict[str, Any] = {
        "at": datetime.now(tz=UTC).isoformat(),
        "symbol": symbol,
        "strategy": demo_lane.ACTIVITY_STRATEGY,
        "mark_price": mark,
        "entry_price": entry,
    }
    if resting is not None:
        payload["resting_stop"] = {"state": "ACTIVE", "trigger_price": resting}
    (root / demo_lane.LANE_DIR / f"heartbeat_{symbol}_activity.json").write_text(
        json.dumps(payload)
    )


def _assert_wallet_shape(wallet: dict[str, Any]) -> None:
    assert wallet["schema_version"] == 1  # matches the client fetchJson gate
    assert set(wallet) == _WALLET_KEYS
    assert set(wallet["venue"]) == _WALLET_VENUE_KEYS
    assert set(wallet["budget"]) == _WALLET_BUDGET_KEYS
    assert set(wallet["realised"]) == _WALLET_REALISED_KEYS
    assert all(set(row) == _WALLET_BALANCE_KEYS for row in wallet["venue"]["balances"])
    assert all(set(row) == _WALLET_POSITION_KEYS for row in wallet["positions"])
    assert wallet["environment"] == "VENUE_DEMO"
    assert wallet["real_money"] is False
    assert wallet["execution_authority"] == "NONE"
    # Venue IDENTITY is stated in both states, with exactly these values — the operator must be
    # able to read "which platform is this?" off the payload without a lane running.
    assert wallet["venue"]["name"] == "Bybit"
    assert wallet["venue"]["environment_label"] == "VENUE_DEMO"
    assert wallet["venue"]["api_host"] == "api-demo.bybit.com"
    assert wallet["venue"]["url"] == "https://www.bybit.com"


def test_wallet_contract_keys_are_identical_available_and_unavailable(root: Path) -> None:
    """(a) schema_version 1 and the exact key set at every level, in BOTH states."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0)])
    wallet = demo_lane.build_wallet(root)
    _assert_wallet_shape(wallet)
    assert wallet["available"] is True
    empty = demo_lane._empty_wallet()
    _assert_wallet_shape(empty)
    assert empty["available"] is False
    assert set(wallet) == set(empty)
    for block in ("venue", "budget", "realised"):
        assert set(wallet[block]) == set(empty[block])


def test_wallet_balances_are_the_freshest_snapshot_quote_first_then_largest(root: Path) -> None:
    """(b) balances come from the NEWEST record's wallet_after, sorted quote coins first."""
    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "TRXUSDT",
                "2026-07-20T10:00:00+00:00",
                "0.30",
                83.0,
                wallet_after={"USDT": "1.0", "BTC": "9.0"},  # stale — must NOT be used
            ),
            _wallet_buy(
                "SOLUSDT",
                "2026-07-21T10:00:00+00:00",
                "100.0",
                0.25,
                wallet_after={
                    "BTC": "1.5",
                    "USDT": "49673.31775303",
                    "SOL": "0.25",
                    "USDC": "50000",
                    "ETH": "2.5",
                },
            ),
        ],
    )
    wallet = demo_lane.build_wallet(root)
    assert wallet["as_of"] == "2026-07-21T10:00:00+00:00"
    assert [row["coin"] for row in wallet["venue"]["balances"]] == [
        "USDC",
        "USDT",
        "ETH",
        "BTC",
        "SOL",
    ]
    assert [row["is_quote"] for row in wallet["venue"]["balances"]] == [
        True,
        True,
        False,
        False,
        False,
    ]
    # Exact strings, no float drift: 49673.31775303 survives to the client intact.
    assert wallet["venue"]["quote_usdt"] == "49673.31775303"
    assert wallet["venue"]["quote_usdc"] == "50000"
    assert all(isinstance(row["amount"], str) for row in wallet["venue"]["balances"])


def test_wallet_cash_total_is_the_quote_only_sum_and_excludes_every_coin(root: Path) -> None:
    """(b2) "how much cash is in the account?" — USDT + USDC exactly, no coin valued in.

    The BTC/ETH/SOL rows sit right beside the quote rows and must contribute nothing: the figure is
    cash on hand, not a portfolio valuation, and it must survive as an exact Decimal string.
    """
    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "SOLUSDT",
                "2026-07-21T10:00:00+00:00",
                "100.0",
                0.25,
                wallet_after={
                    "BTC": "1.5",
                    "USDT": "49673.31775303",
                    "SOL": "0.25",
                    "USDC": "50000",
                    "ETH": "2.5",
                },
            )
        ],
    )
    venue = demo_lane.build_wallet(root)["venue"]
    cash = venue["cash_total_usdt"]
    assert isinstance(cash, str)
    # Exact quote-only sum: 49673.31775303 + 50000. No float drift, no coin, no rounding.
    assert cash == "99673.31775303"
    assert Decimal(cash) == Decimal(venue["quote_usdt"]) + Decimal(venue["quote_usdc"])
    quote_rows = [row for row in venue["balances"] if row["is_quote"]]
    assert Decimal(cash) == sum((Decimal(row["amount"]) for row in quote_rows), Decimal("0"))
    # And it is strictly LESS than "everything in the account counted as dollars" — the coins are
    # out, so the number can never quietly become a portfolio total.
    every_row = sum((Decimal(row["amount"]) for row in venue["balances"]), Decimal("0"))
    assert Decimal(cash) < every_row
    assert demo_lane._empty_wallet()["venue"]["cash_total_usdt"] == "0"


def test_wallet_venue_identity_is_fixed_constants_never_derived_from_a_request(
    root: Path,
) -> None:
    """(b3) name/api_host/url come from module constants, not from the ledger and not from a caller.

    The API host mirrors scripts/demo_preflight.py DEMO_HOST (the verified fact); the site URL is a
    fixed convenience link. A ledger that tries to inject its own host/url must be ignored, and
    build_wallet takes no parameter that could reach either field.
    """
    import scripts.demo_preflight as preflight

    assert demo_lane.VENUE_API_HOST == preflight.DEMO_HOST  # mirrored constant stays in sync
    assert demo_lane.VENUE_SITE_URL.startswith("https://")
    assert "{" not in demo_lane.VENUE_SITE_URL and " " not in demo_lane.VENUE_SITE_URL

    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "TRXUSDT",
                "2026-07-20T10:00:00+00:00",
                "0.30",
                83.0,
                url="https://evil.test/steal",
                api_host="evil.test",
                venue={"name": "EvilVenue", "url": "javascript:alert(1)"},
                wallet_after={"USDT": "10", "url": "https://evil.test/steal"},
            )
        ],
    )
    venue = demo_lane.build_wallet(root)["venue"]
    assert venue["api_host"] == "api-demo.bybit.com"
    assert venue["url"] == "https://www.bybit.com"
    assert venue["name"] == "Bybit"
    assert "evil.test" not in json.dumps(venue)
    assert "javascript:" not in json.dumps(demo_lane.build_wallet(root))
    # build_wallet's ONLY parameter is the repo root — there is no request-shaped input at all, so
    # the identity has no path by which a caller could influence it.
    assert list(inspect.signature(demo_lane.build_wallet).parameters) == ["root"]
    # The fail-closed shape carries the identical identity, from the identical constants.
    for field in ("name", "environment_label", "api_host", "url"):
        assert demo_lane._empty_wallet()["venue"][field] == venue[field]


def test_wallet_budget_slot_math_when_partially_deployed(root: Path) -> None:
    """(c) deployed is SUMMED from the open positions; free/slots follow from the lane's caps."""
    _write_feed_orders(
        root,
        [
            _wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0),
            _wallet_buy("SOLUSDT", "2026-07-20T11:00:00+00:00", "100.0", 0.25),
        ],
    )
    budget = demo_lane.build_wallet(root)["budget"]
    assert budget["total_cap_usdt"] == "300" and budget["per_trade_usdt"] == "25"
    assert budget["deployed_usdt"] == "50" and budget["free_usdt"] == "250"
    assert budget["slots_total"] == 12  # floor(300 / 25)
    assert budget["slots_used"] == 2 and budget["slots_free"] == 10
    assert budget["disaster_stop_pct"] == "15"
    assert all(isinstance(budget[field], str) for field in ("deployed_usdt", "free_usdt"))


def test_wallet_budget_is_full_when_every_slot_is_used(root: Path) -> None:
    """(d) twelve open positions exhaust the shared cap: free 0, slots_free 0 — never negative."""
    coins = [
        "AAVE",
        "APT",
        "AXS",
        "BCH",
        "BNB",
        "BTC",
        "ETH",
        "LINK",
        "RUNE",
        "SOL",
        "TIA",
        "UNI",
    ]
    _write_feed_orders(
        root,
        [
            _wallet_buy(f"{coin}USDT", f"2026-07-20T{hour:02d}:00:00+00:00", "10.0", 2.5)
            for hour, coin in enumerate(coins)
        ],
    )
    budget = demo_lane.build_wallet(root)["budget"]
    assert budget["deployed_usdt"] == "300" and budget["free_usdt"] == "0"
    assert budget["slots_used"] == 12 and budget["slots_free"] == 0


def test_wallet_positions_carry_marks_and_sort_by_unrealised_desc_nulls_last(root: Path) -> None:
    """(e) entry/mark/unrealised/held_seconds per position, best first, unmarked positions last."""
    opened = datetime.now(tz=UTC) - timedelta(hours=2)
    _write_feed_orders(
        root,
        [
            _wallet_buy("TRXUSDT", opened.isoformat(), "0.30", 100.0),
            _wallet_buy("SOLUSDT", opened.isoformat(), "100.0", 0.25),
            _wallet_buy("ADAUSDT", opened.isoformat(), "0.50", 50.0),
        ],
    )
    _mark_files(root, "TRXUSDT", mark="0.315", entry="0.30")  # +5%
    _mark_files(root, "SOLUSDT", mark="110.0", entry="100.0", resting="85.0")  # +10%
    # ADAUSDT deliberately has NO heartbeat -> no mark.
    positions = demo_lane.build_wallet(root)["positions"]
    assert [p["symbol"] for p in positions] == ["SOLUSDT", "TRXUSDT", "ADAUSDT"]

    sol = positions[0]
    assert sol["strategy"] == demo_lane.ACTIVITY_STRATEGY
    # Plain Decimal strings: trailing-zero noise is normalized away ('100.0' -> '100').
    assert sol["size_base"] == "0.25" and sol["entry_price"] == "100"
    assert sol["mark_price"] == "110" and sol["spent_usdt"] == "25"
    assert sol["value_usdt"] == "27.5" and sol["unrealised_usdt"] == "2.5"
    assert sol["unrealised_pct"] == "10"
    assert sol["stop_price"] == "85"  # the live venue resting stop wins over the -15% floor
    assert sol["distance_to_stop_pct"] == "22.73"
    assert sol["opened_at"] == opened.isoformat()
    assert 7195 <= sol["held_seconds"] <= 7215  # ~2h, computed to now (UTC)

    trx = positions[1]
    assert trx["unrealised_pct"] == "5" and trx["mark_price"] == "0.315"
    assert trx["stop_price"] == "0.26"  # no resting stop -> the derived -15% disaster floor
    assert all(isinstance(p["spent_usdt"], str) for p in positions)


def test_wallet_position_without_a_mark_is_null_and_the_total_stays_partial(root: Path) -> None:
    """(f) a markless position nulls only its own mark fields and never zeroes the total."""
    at = "2026-07-20T10:00:00+00:00"
    _write_feed_orders(
        root,
        [
            _wallet_buy("TRXUSDT", at, "0.30", 100.0),
            _wallet_buy("ADAUSDT", at, "0.50", 50.0),
        ],
    )
    _mark_files(root, "TRXUSDT", mark="0.315", entry="0.30")
    wallet = demo_lane.build_wallet(root)
    ada = next(p for p in wallet["positions"] if p["symbol"] == "ADAUSDT")
    for field in ("mark_price", "value_usdt", "unrealised_usdt", "unrealised_pct"):
        assert ada[field] is None, field
    # Still a real position: size/spend/entry are ledger truth and still counted in the budget.
    assert ada["spent_usdt"] == "25" and ada["size_base"] == "50"
    assert wallet["budget"]["deployed_usdt"] == "50"
    # PARTIAL total: the one known unrealised, not a fabricated 0 for the unmarked coin.
    assert wallet["unrealised_total_usdt"] == "1.5"

    # No mark anywhere at all -> null, not "0".
    (root / demo_lane.LANE_DIR / "heartbeat_TRXUSDT_activity.json").unlink()
    assert demo_lane.build_wallet(root)["unrealised_total_usdt"] is None


def test_wallet_realised_agrees_field_for_field_with_report_demo_trades(root: Path) -> None:
    """(g) realised totals ARE report_demo_trades.summarize — the two can never disagree."""
    _write_feed_orders(
        root,
        [
            _wallet_buy("ETHUSDT", "2026-07-20T10:00:00+00:00", "1862.37", 0.01341033),
            _wallet_sell("ETHUSDT", "2026-07-20T12:00:00+00:00", "1900.0", 0.01341033, 25.5379),
            _wallet_buy("TRXUSDT", "2026-07-21T10:00:00+00:00", "0.30", 100.0),  # still open
        ],
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import scripts.report_demo_trades as rpt

    trips, unmatched = rpt.fold_fills(rpt.load_filled(root / demo_lane.ORDERS_LEDGER))
    report = rpt.summarize(trips, unmatched)
    realised = demo_lane.build_wallet(root)["realised"]
    assert realised["closed_count"] == report["closed_trades"] == 1
    assert realised["wins"] == report["wins"] == 1
    assert realised["losses"] == report["losses"] == 0
    assert realised["realised_usdt"] == str(report["realised_pnl_usd"]) == "0.5379"
    assert realised["fees_usdt"] == str(report["total_fees_usd"])
    # The OPEN trip is a position, not a realised trade.
    assert [p["symbol"] for p in demo_lane.build_wallet(root)["positions"]] == ["TRXUSDT"]


@pytest.mark.parametrize("ledger", [None, "{not valid json\n", "", "[]\n"])
def test_wallet_missing_or_malformed_artifacts_fail_closed(root: Path, ledger: str | None) -> None:
    """(h) a missing or corrupt ledger degrades to the same keys with available False — no raise."""
    if ledger is not None:
        (root / demo_lane.ORDERS_LEDGER).write_text(ledger)
    wallet = demo_lane.build_wallet(root)
    _assert_wallet_shape(wallet)
    assert wallet["available"] is False
    assert wallet["as_of"] is None
    assert wallet["venue"]["balances"] == [] and wallet["positions"] == []
    assert wallet["budget"]["deployed_usdt"] == "0" and wallet["budget"]["slots_total"] == 0
    assert wallet["realised"] == {
        "closed_count": 0,
        "wins": 0,
        "losses": 0,
        "realised_usdt": "0",
        "fees_usdt": "0",
    }
    assert wallet["unrealised_total_usdt"] is None


def test_wallet_fails_closed_when_a_read_raises_without_leaking_the_reason(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(i) any exception on the read path is contained — never a 500, never a traceback."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0)])

    def boom(_root: Path) -> list[dict[str, Any]]:
        raise OSError("ledger exploded at /Users/secret/orders.jsonl")

    monkeypatch.setattr(demo_lane, "_orders", boom)
    wallet = demo_lane.build_wallet(root)
    assert wallet["available"] is False and set(wallet) == _WALLET_KEYS
    assert "exploded" not in json.dumps(wallet)


def test_wallet_is_a_pure_read_and_never_spawns_a_subprocess(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(j) a spawn from a read-only money view would be a governance break."""
    monkeypatch.setattr(
        demo_lane.subprocess, "Popen", lambda *_a, **_k: pytest.fail("wallet must not spawn")
    )
    monkeypatch.setattr(
        demo_lane.subprocess, "run", lambda *_a, **_k: pytest.fail("wallet must not spawn")
    )
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0)])
    assert demo_lane.build_wallet(root)["schema_version"] == 1


def test_wallet_leaks_no_identifying_token(root: Path) -> None:
    """(k) the serialized body carries no order id, signal ref, path, pid or credential."""
    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "TRXUSDT",
                "2026-07-20T10:00:00+00:00",
                "0.30",
                83.0,
                signal_ref="ACT-CONF:0.4300:2026-07-20T09:55:00+00:00",
                error=_LEAKY_ERROR,
            )
        ],
    )
    _mark_files(root, "TRXUSDT", mark="0.315", entry="0.30")
    body = json.dumps(demo_lane.build_wallet(root))
    for token in _WALLET_FORBIDDEN:
        assert token not in body, f"wallet leaked {token!r}"
    assert "BYBIT" not in body and "abcd1234" not in body


def test_wallet_separates_venue_holdings_from_what_the_lane_controls(root: Path) -> None:
    """(l) the note and disclaimer are present, non-empty, and refuse to read as performance."""
    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "TRXUSDT",
                "2026-07-20T10:00:00+00:00",
                "0.30",
                83.0,
                wallet_after={"USDT": "49673.31775303", "USDC": "50000", "BTC": "1.0"},
            )
        ],
    )
    wallet = demo_lane.build_wallet(root)
    note = wallet["venue"]["note"]
    assert isinstance(note, str) and note
    assert "pre-funded" in note.lower() and "fake-money" in note.lower()
    assert "not" in note.lower() and "lane" in note.lower()

    disclaimer = wallet["disclaimer"]
    assert isinstance(disclaimer, str) and disclaimer
    assert "fake money" in disclaimer.lower()
    assert "NONE" in disclaimer and "UNVALIDATED" in disclaimer
    assert "not evidence" in disclaimer.lower()
    assert "not performance" in disclaimer.lower()
    # The ~$99.7k of venue CASH is reported honestly — the operator asked "how much is in the
    # account?" and hiding it would be its own dishonesty — but only as the quote-only sum.
    venue = wallet["venue"]
    assert venue["cash_total_usdt"] == "99673.31775303"
    assert Decimal(venue["cash_total_usdt"]) == Decimal(venue["quote_usdt"]) + Decimal(
        venue["quote_usdc"]
    )

    # It is NEVER merged with the lane's money: the cap stays 300, and no field anywhere in the
    # payload carries cash+budget, cash+P&L, or cash+coins as one number.
    assert wallet["budget"]["total_cap_usdt"] == "300"
    cash = Decimal(venue["cash_total_usdt"])
    coins = sum(
        (Decimal(row["amount"]) for row in venue["balances"] if not row["is_quote"]),
        Decimal("0"),
    )
    body = json.dumps(wallet)
    forbidden_totals = {
        cash + Decimal(wallet["budget"]["total_cap_usdt"]),  # cash + lane cap
        cash + Decimal(wallet["realised"]["realised_usdt"]),  # cash + realised P&L
        cash + coins,  # cash + coins valued at 1:1 — a portfolio "grand total"
    } - {cash}  # a zero addend is not a combined total, it is the cash figure itself
    assert forbidden_totals
    for total in forbidden_totals:
        assert demo_lane._plain(total) not in body, f"combined total {total} leaked into the wallet"


def test_wallet_route_serves_schema_version_1_through_the_real_handler(root: Path) -> None:
    """(m) end-to-end through the real GET handler: 200 JSON with schema_version 1."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0)])
    headers, payload = _handle_get("/api/v1/wallet", root)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    assert payload["schema_version"] == 1
    assert set(payload) == _WALLET_KEYS


# --- GET /api/v1/price-history --------------------------------------------------------------------
# "What did the price actually do while we held this?" answered from the closes the LANE captured
# itself. No request parameter, no venue call, no subprocess, no write. One series per HELD coin
# (the wallet's own open positions), so the payload stays bounded; a held coin whose history file
# does not exist yet is the normal empty case, never an error.

_HISTORY_KEYS = {"schema_version", "available", "generated_at", "series", "coverage"}
_HISTORY_SERIES_KEYS = {
    "symbol",
    "interval",
    "updated_at",
    "point_count",
    "first_at",
    "last_at",
    "closes",
    "entry_price",
    "stop_price",
    "mark_price",
    "held",
}
_HISTORY_COVERAGE_KEYS = {"held_count", "series_count", "missing"}


def _price_file(root: Path, symbol: str, points: Any, **overrides: Any) -> None:
    """A price_history_<SYMBOL>.json exactly as the lane persists it (bars it already fetched)."""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "symbol": symbol,
        "interval": "5m",
        "updated_at": "2026-07-26T15:00:00+00:00",
        "max_points": 288,
        "points": points,
    }
    payload.update(overrides)
    (root / demo_lane.LANE_DIR / f"price_history_{symbol}.json").write_text(json.dumps(payload))


def _closes(count: int, start: float = 100.0) -> list[dict[str, str]]:
    base = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    return [
        {"at": (base + timedelta(minutes=5 * i)).isoformat(), "close": str(start + i)}
        for i in range(count)
    ]


def _assert_history_shape(history: dict[str, Any]) -> None:
    assert history["schema_version"] == 1  # matches the client fetchJson gate
    assert set(history) == _HISTORY_KEYS
    assert set(history["coverage"]) == _HISTORY_COVERAGE_KEYS
    assert all(set(row) == _HISTORY_SERIES_KEYS for row in history["series"])
    for row in history["series"]:
        assert all(set(point) == {"at", "close"} for point in row["closes"])
        assert all(isinstance(point["close"], str) for point in row["closes"])


def test_price_history_contract_keys_are_identical_available_and_unavailable(root: Path) -> None:
    """(a) schema_version 1 and the exact key set at every level, in BOTH states."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 83.0)])
    _price_file(root, "TRXUSDT", _closes(3, 0.3))
    history = demo_lane.build_price_history(root)
    _assert_history_shape(history)
    assert history["available"] is True
    empty = demo_lane._empty_price_history()
    _assert_history_shape(empty)
    assert empty["available"] is False
    assert set(history) == set(empty)
    assert empty["series"] == []
    assert empty["coverage"] == {"held_count": 0, "series_count": 0, "missing": []}


def test_price_history_emits_one_series_per_held_coin_only(root: Path) -> None:
    """(b) held coins only: a closed trip and an unheld coin's file are both ignored."""
    _write_feed_orders(
        root,
        [
            _wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0),
            _wallet_buy("SOLUSDT", "2026-07-20T11:00:00+00:00", "100.0", 0.25),
            _wallet_sell("SOLUSDT", "2026-07-20T12:00:00+00:00", "110.0", 0.25, 27.5),  # closed
        ],
    )
    _price_file(root, "TRXUSDT", _closes(4, 0.3))
    _price_file(root, "SOLUSDT", _closes(4, 100.0))  # closed position — must NOT be emitted
    _price_file(root, "ADAUSDT", _closes(4, 0.5))  # never held at all
    history = demo_lane.build_price_history(root)
    assert [row["symbol"] for row in history["series"]] == ["TRXUSDT"]
    assert history["coverage"] == {"held_count": 1, "series_count": 1, "missing": []}
    assert all(row["held"] is True for row in history["series"])
    # Held set and order are the wallet's own, never a second derivation.
    held = [p["symbol"] for p in demo_lane.build_wallet(root)["positions"]]
    assert [row["symbol"] for row in history["series"]] == held


def test_price_history_held_coin_without_a_file_is_empty_not_an_error(root: Path) -> None:
    """(c) the lane has not written the file yet: empty closes, null stamps, named in coverage."""
    at = "2026-07-20T10:00:00+00:00"
    _write_feed_orders(
        root, [_wallet_buy("TRXUSDT", at, "0.30", 100.0), _wallet_buy("ADAUSDT", at, "0.50", 50.0)]
    )
    _price_file(root, "TRXUSDT", _closes(2, 0.3))
    history = demo_lane.build_price_history(root)
    _assert_history_shape(history)
    assert history["available"] is True
    ada = next(row for row in history["series"] if row["symbol"] == "ADAUSDT")
    assert ada["closes"] == [] and ada["point_count"] == 0
    assert ada["first_at"] is None and ada["last_at"] is None
    assert ada["updated_at"] is None and ada["interval"] is None  # never a guessed cadence
    assert history["coverage"]["missing"] == ["ADAUSDT"]
    assert history["coverage"]["held_count"] == 2 == history["coverage"]["series_count"]


def test_price_history_closes_are_oldest_first_capped_and_string_valued(root: Path) -> None:
    """(d) the series stays bounded and Decimal-exact: newest tail kept, oldest -> newest."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    points = _closes(demo_lane.PRICE_HISTORY_POINT_LIMIT + 40, 0.3)
    _price_file(root, "TRXUSDT", points)
    series = demo_lane.build_price_history(root)["series"][0]
    assert series["point_count"] == demo_lane.PRICE_HISTORY_POINT_LIMIT
    assert series["closes"][0] == points[40]  # the oldest 40 are dropped, not the newest
    assert series["closes"][-1]["at"] == points[-1]["at"]
    assert series["first_at"] == series["closes"][0]["at"]
    assert series["last_at"] == series["closes"][-1]["at"]
    assert series["interval"] == "5m" and series["updated_at"] == "2026-07-26T15:00:00+00:00"
    stamps = [point["at"] for point in series["closes"]]
    assert stamps == sorted(stamps)


def test_price_history_drops_malformed_points_without_failing_the_response(root: Path) -> None:
    """(e) one bad row must never cost the operator the rest of the series."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    good = _closes(2, 0.3)
    _price_file(
        root,
        "TRXUSDT",
        [
            good[0],
            "not a dict",
            {"at": "2026-07-26T12:00:00+00:00"},  # no close
            {"close": "0.31"},  # no timestamp
            {"at": "not-a-time", "close": "0.31"},
            {"at": "2026-07-26T12:05:00+00:00", "close": "not-a-number"},
            {"at": "2026-07-26T12:10:00+00:00", "close": None},
            good[1],
        ],
    )
    history = demo_lane.build_price_history(root)
    assert history["available"] is True
    assert history["series"][0]["closes"] == good
    assert history["series"][0]["point_count"] == 2


@pytest.mark.parametrize(
    "content", ["{not valid json", "[]", '{"points": "nope"}', '{"points": null}', ""]
)
def test_price_history_malformed_file_degrades_to_an_empty_series(root: Path, content: str) -> None:
    """(f) a corrupt history file yields an empty series, never an exception or a 500."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    (root / demo_lane.LANE_DIR / "price_history_TRXUSDT.json").write_text(content)
    history = demo_lane.build_price_history(root)
    _assert_history_shape(history)
    assert history["available"] is True
    assert history["series"][0]["closes"] == []
    assert history["coverage"]["missing"] == ["TRXUSDT"]


def test_price_history_entry_stop_and_mark_agree_with_the_wallet(root: Path) -> None:
    """(g) the three price levels ARE build_wallet's — no second mark, no second stop precedence."""
    at = "2026-07-20T10:00:00+00:00"
    _write_feed_orders(
        root,
        [
            _wallet_buy("TRXUSDT", at, "0.30", 100.0),
            _wallet_buy("SOLUSDT", at, "100.0", 0.25),
            _wallet_buy("ADAUSDT", at, "0.50", 50.0),
        ],
    )
    _mark_files(root, "TRXUSDT", mark="0.315", entry="0.30")  # -15% floor, no resting stop
    _mark_files(root, "SOLUSDT", mark="110.0", entry="100.0", resting="85.0")  # resting stop wins
    # ADAUSDT has no heartbeat at all -> no mark anywhere.
    for symbol in ("TRXUSDT", "SOLUSDT", "ADAUSDT"):
        _price_file(root, symbol, _closes(3, 1.0))
    positions = {p["symbol"]: p for p in demo_lane.build_wallet(root)["positions"]}
    for series in demo_lane.build_price_history(root)["series"]:
        position = positions[series["symbol"]]
        for field in ("entry_price", "stop_price", "mark_price"):
            assert series[field] == position[field], f"{series['symbol']}.{field}"
    by_symbol = {row["symbol"]: row for row in demo_lane.build_price_history(root)["series"]}
    assert by_symbol["SOLUSDT"]["stop_price"] == "85"  # venue resting stop, not the -15% floor
    assert by_symbol["TRXUSDT"]["stop_price"] == "0.26"  # derived disaster floor
    assert by_symbol["ADAUSDT"]["mark_price"] is None  # never invented


def test_price_history_fails_closed_when_a_read_raises_without_leaking_the_reason(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(h) any exception on the read path is contained — never a 500, never a traceback."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    _price_file(root, "TRXUSDT", _closes(3, 0.3))

    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise OSError("history exploded at /Users/secret/price_history_TRXUSDT.json")

    monkeypatch.setattr(demo_lane, "_price_series", boom)
    history = demo_lane.build_price_history(root)
    _assert_history_shape(history)
    assert history["available"] is False and history["series"] == []
    assert "exploded" not in json.dumps(history)
    # A wallet that cannot be read leaves no honest held set: same fail-closed shape.
    monkeypatch.setattr(demo_lane, "build_wallet", lambda _root: demo_lane._empty_wallet())
    closed = demo_lane.build_price_history(root)
    _assert_history_shape(closed)
    assert closed["available"] is False


def test_price_history_is_a_pure_read_and_never_spawns_a_subprocess(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(i) a spawn from a read-only chart source would be a governance break."""
    monkeypatch.setattr(
        demo_lane.subprocess, "Popen", lambda *_a, **_k: pytest.fail("history must not spawn")
    )
    monkeypatch.setattr(
        demo_lane.subprocess, "run", lambda *_a, **_k: pytest.fail("history must not spawn")
    )
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    _price_file(root, "TRXUSDT", _closes(3, 0.3))
    assert demo_lane.build_price_history(root)["schema_version"] == 1


def test_price_history_leaks_no_identifying_token(root: Path) -> None:
    """(j) the serialized body carries no order id, signal ref, path, pid or credential."""
    _write_feed_orders(
        root,
        [
            _wallet_buy(
                "TRXUSDT",
                "2026-07-20T10:00:00+00:00",
                "0.30",
                100.0,
                signal_ref="ACT-CONF:0.4300:2026-07-20T09:55:00+00:00",
                error=_LEAKY_ERROR,
            )
        ],
    )
    _mark_files(root, "TRXUSDT", mark="0.315", entry="0.30")
    _price_file(root, "TRXUSDT", _closes(3, 0.3))
    body = json.dumps(demo_lane.build_price_history(root))
    for token in _WALLET_FORBIDDEN:
        assert token not in body, f"price history leaked {token!r}"
    assert "BYBIT" not in body and "abcd1234" not in body


def test_price_history_route_serves_schema_version_1_through_the_real_handler(root: Path) -> None:
    """(k) end-to-end through the real GET handler: 200 JSON with schema_version 1."""
    _write_feed_orders(root, [_wallet_buy("TRXUSDT", "2026-07-20T10:00:00+00:00", "0.30", 100.0)])
    _price_file(root, "TRXUSDT", _closes(3, 0.3))
    headers, payload = _handle_get("/api/v1/price-history", root)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    assert payload["schema_version"] == 1
    assert payload["series"][0]["symbol"] == "TRXUSDT"
