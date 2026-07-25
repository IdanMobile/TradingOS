"""Tests for the global-allowlist demo-lane projection and bounded controls (Wave 3).

The GET /api/v1/demo-lane body is restricted to operational status plus the fixed,
fail-closed Stage B readiness object; every legacy per-trade/wallet/order/heartbeat
field is globally removed. The action handler returns exactly four fixed fields.
"""

from __future__ import annotations

import json
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
    "stage_b",
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
    assert lane["schema_version"] == 2
    assert lane["operational_status"] == "IDLE"
    assert lane["execution_authority"] == "NONE"
    assert lane["real_money"] is False
    assert lane["promotion_eligible"] is False
    assert lane["auto_tune"] is False
    assert lane["validation_state"] == "UNVALIDATED"
    assert set(lane["stage_b"]) == _STAGE_B_KEYS
    assert lane["stage_b"] == {"status": "NOT_ACTIVATED", "cohort_size": 30, "series": []}


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


def test_forbidden_fields_are_globally_stripped(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if upstream leaks private data, the API boundary reprojects to the allowlist."""
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

    body = json.dumps(lane).lower()
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
