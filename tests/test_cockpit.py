from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from tios.services.dashboard_api import cockpit as cockpit_module
from tios.services.dashboard_api.cockpit import (
    CockpitActionError,
    CockpitNotFoundError,
    CockpitUnavailableError,
    build_cockpit,
    perform_cockpit_action,
)
from tios.services.dashboard_ui.server import Handler
from tios.services.jobs import JobStore, JobType
from tios.services.jobs.runner import default_database as jobs_database
from tios.services.paper.store import PaperEventType, PaperStore

NOW = datetime(2026, 7, 12, 12, tzinfo=UTC)
BOT_ID = "PAPERBOT-0123456789abcdef0123"


def _handle_request(raw_request: bytes, root: Path) -> bytes:
    handler = object.__new__(Handler)
    handler.root = root
    handler.html = "dashboard"
    handler.rfile = BytesIO(raw_request)
    handler.wfile = BytesIO()
    handler.client_address = ("127.0.0.1", 1)
    handler.server = SimpleNamespace(server_name="test", server_port=80)
    handler.close_connection = True
    handler.handle_one_request()
    return handler.wfile.getvalue()


def _post(path: str, payload: dict[str, object], root: Path, *, extra: bytes = b"") -> bytes:
    body = json.dumps(payload).encode()
    return _handle_request(
        f"POST {path} HTTP/1.1\r\n".encode()
        + b"Host: localhost\r\nContent-Type: application/json\r\n"
        + extra
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body,
        root,
    )


def _paper_fixture(
    root: Path,
    *,
    incident: bool = False,
    critical_incident: bool = False,
    heartbeat_age_seconds: int = 0,
    mark_price: str = "60000",
) -> PaperStore:
    store = PaperStore(root=root)
    risk_policy: dict[str, object] = {
        "starting_capital": "10000",
        "max_position_notional": "1000",
        "max_total_exposure": "2000",
        "max_daily_loss": "100",
        "max_drawdown_fraction": "0.05",
        "max_open_positions": 2,
        "fee_bps": "10",
        "slippage_bps": "2",
        "quote_max_age_seconds": 15,
        "max_fill_latency_seconds": 5,
        "heartbeat_interval_seconds": 10,
        "stale_after_seconds": 30,
    }
    encoded = json.dumps(risk_policy, sort_keys=True, separators=(",", ":"))
    store.append_event(
        PaperEventType.BOT,
        BOT_ID,
        {
            "kind": "STARTED",
            "strategy_version_ref": "STRATV-paper-fixture",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "config_digest": "a" * 64,
            "spec_sha256": "b" * 64,
            "gate_id": "GATE-paper-fixture",
            "approval_sha256": "c" * 64,
            "risk_policy": risk_policy,
            "policy_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
            "validation_approval_ref": "APR-paper-fixture",
            "validation_evidence_refs": ["EVIDENCE-paper-fixture"],
        },
        idempotency_key="bot-start-fixture",
        occurred_at=NOW - timedelta(minutes=5),
        recorded_at=NOW - timedelta(minutes=5),
    )
    store.append_portfolio_point(
        idempotency_key="paper-portfolio-initial-v1",
        observed_at=NOW - timedelta(minutes=5),
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        exposure=Decimal("0"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        fees=Decimal("0"),
    )
    for source in ("BINANCE_BOOK_TICKER", "BINANCE_KLINES"):
        store.append_event(
            PaperEventType.HEARTBEAT,
            BOT_ID,
            {"status": "OK", "source": source, "mark_price": mark_price},
            idempotency_key=f"heartbeat-{source.lower()}",
            occurred_at=NOW - timedelta(seconds=heartbeat_age_seconds),
            recorded_at=NOW - timedelta(seconds=heartbeat_age_seconds),
        )
    if incident:
        store.append_event(
            PaperEventType.INCIDENT,
            BOT_ID,
            {
                "summary": "Operator review requested",
                "source": "RISK_ENGINE" if critical_incident else "BINANCE_BOOK_TICKER",
            },
            idempotency_key="incident-risk-fixture",
            occurred_at=NOW,
            recorded_at=NOW,
        )
    return store


@pytest.mark.parametrize("range_name", ["24h", "1d", "3d", "7d", "1m", "all"])
def test_research_only_cockpit_is_honest_and_does_not_create_paper_db(
    tmp_path: Path, range_name: str
) -> None:
    snapshot = build_cockpit(tmp_path, range_name, now=NOW)

    assert snapshot["schema_version"] == 1
    assert snapshot["mode"] == "RESEARCH_ONLY"
    assert snapshot["range"] == range_name
    assert snapshot["available"] is False
    assert snapshot["portfolio"]["available"] is False
    assert snapshot["portfolio"]["equity"] is None
    assert snapshot["portfolio"]["pnl"] is None
    assert "approved" in snapshot["reason"]
    assert snapshot["capabilities"]["execution_authority"] == "NONE"
    assert snapshot["capabilities"]["order_endpoint"] == "ABSENT"
    assert not (tmp_path / "artifacts/paper/paper.sqlite3").exists()


def test_cockpit_projects_existing_paper_state_as_decimal_text(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path)
    before = store.path.stat().st_mtime_ns

    snapshot = build_cockpit(tmp_path, "1d", now=NOW)

    assert snapshot["available"] is True
    assert snapshot["mode"] == "SYNTHETIC_LOCAL_SIMULATOR"
    assert snapshot["portfolio"]["equity"] == "10000"
    assert snapshot["portfolio"]["pnl"] == "0"
    assert snapshot["bots"][0]["bot_id"] == BOT_ID
    assert snapshot["bots"][0]["allocated_capital"] is None
    assert snapshot["bots"][0]["return_fraction"] is None
    assert "risk cap is not allocation" in snapshot["bots"][0]["return_unavailable_reason"]
    assert snapshot["bots"][0]["conditions_met"] is None
    assert snapshot["bots"][0]["conditions_unavailable_reason"]
    assert snapshot["freshness"][0]["status"] == "LIVE"
    assert store.path.stat().st_mtime_ns == before


def test_position_separates_fill_entry_price_from_fee_loaded_cost_basis(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path, mark_price="110")
    store.append_event(
        PaperEventType.SIGNAL,
        BOT_ID,
        {
            "signal_id": "SIG-entry-fixture",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "side": "BUY",
            "rationale": "fixture",
        },
        idempotency_key="signal-entry-fixture",
        occurred_at=NOW,
        recorded_at=NOW,
    )
    store.append_event(
        PaperEventType.FILL,
        BOT_ID,
        {
            "signal_id": "SIG-entry-fixture",
            "fill_id": "FILL-entry-fixture",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "side": "BUY",
            "price": "100",
            "quantity": "2",
            "notional": "200",
            "fee": "0.2",
            "cash_after": "9799.8",
            "position_quantity_after": "2",
            "position_cost_after": "200.2",
            "realized_pnl_after": "0",
            "fees_after": "0.2",
        },
        idempotency_key="fill-entry-fixture",
        occurred_at=NOW,
        recorded_at=NOW,
    )

    snapshot = build_cockpit(tmp_path, "all", now=NOW)

    assert snapshot["positions"][0]["entry_price"] == "100"
    assert snapshot["positions"][0]["cost_basis_per_unit"] == "100.1"


def test_cockpit_get_validates_range_without_creating_state(tmp_path: Path) -> None:
    response = _handle_request(
        b"GET /api/v1/cockpit?range=year HTTP/1.1\r\nHost: localhost\r\n\r\n",
        tmp_path,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 400 " in headers
    assert "range must be" in json.loads(body)["error"]
    assert not (tmp_path / "artifacts/paper/paper.sqlite3").exists()


def test_unknown_bot_signal_fails_closed_as_unavailable_paper_state(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path)
    store.append_event(
        PaperEventType.SIGNAL,
        "PAPERBOT-unknown",
        {
            "signal_id": "SIG-unknown-bot",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "side": "BUY",
            "rationale": "fixture",
        },
        idempotency_key="signal-unknown-bot",
        occurred_at=NOW,
        recorded_at=NOW,
    )

    snapshot = build_cockpit(tmp_path, "24h", now=NOW)

    assert snapshot["available"] is False
    assert snapshot["portfolio"]["available"] is False
    assert "failed validation" in snapshot["reason"]


@pytest.mark.parametrize(("heartbeat_age_seconds", "expected"), [(11, "DELAYED"), (31, "STALE")])
def test_paper_freshness_distinguishes_delayed_and_stale_heartbeats(
    tmp_path: Path, heartbeat_age_seconds: int, expected: str
) -> None:
    _paper_fixture(tmp_path, heartbeat_age_seconds=heartbeat_age_seconds)

    snapshot = build_cockpit(tmp_path, "24h", now=NOW)

    assert snapshot["freshness"][0]["status"] == expected
    expected_working = 0 if expected == "STALE" else 1
    assert snapshot["now"]["paper_bots_working"] == expected_working


def test_unresolved_feed_incident_never_projects_live_freshness(tmp_path: Path) -> None:
    _paper_fixture(tmp_path, incident=True)

    snapshot = build_cockpit(tmp_path, "24h", now=NOW)

    assert snapshot["freshness"][0]["status"] == "UNAVAILABLE"


def test_stale_started_bot_is_not_headlined_as_working(tmp_path: Path) -> None:
    _paper_fixture(tmp_path, heartbeat_age_seconds=31)

    snapshot = build_cockpit(tmp_path, "24h", now=NOW)

    assert snapshot["now"]["paper_bots"] == 1
    assert snapshot["now"]["paper_bots_working"] == 0
    assert snapshot["now"]["paper_bots_stale"] == 1
    assert snapshot["now"]["paper_bots_historical"] is None
    assert snapshot["headline"].startswith("0 paper bots are working; 0 paused and 1 stale")


def test_running_job_count_is_not_truncated_by_latest_activity_limit(tmp_path: Path) -> None:
    with JobStore(jobs_database(tmp_path), root=tmp_path) as store:
        store.initialize()
        store.enqueue(JobType.RESEARCH_LAB_V0, "older-running", due_at=NOW)
        assert store.claim("fixture-worker", now=NOW) is not None
        for index in range(25):
            store.enqueue(JobType.DATA_QUALITY, f"newer-{index}", due_at=NOW + timedelta(days=1))

    snapshot = build_cockpit(tmp_path, "24h", now=NOW)

    assert snapshot["now"]["research_jobs_running"] == 1
    assert "1 research job is running" in snapshot["headline"]


def test_shared_post_guard_rejects_bad_media_type_and_cross_origin(tmp_path: Path) -> None:
    body = b"{}"
    media = _handle_request(
        b"POST /api/v1/cockpit-actions HTTP/1.1\r\nHost: localhost\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body,
        tmp_path,
    )
    assert b" 415 " in media.split(b"\r\n\r\n", 1)[0]

    cross_origin = _post(
        "/api/v1/cockpit-actions",
        {"action": "PAUSE_PAPER_ENTRIES", "subject_id": BOT_ID, "idempotency_key": "x"},
        tmp_path,
        extra=b"Origin: http://attacker.test\r\n",
    )
    assert b" 403 " in cross_origin.split(b"\r\n\r\n", 1)[0]

    wrong_scheme = _post(
        "/api/v1/cockpit-actions",
        {
            "action": "PAUSE_PAPER_ENTRIES",
            "subject_id": BOT_ID,
            "idempotency_key": "wrong-scheme",
        },
        tmp_path,
        extra=b"Origin: https://localhost\r\n",
    )
    assert b" 403 " in wrong_scheme.split(b"\r\n\r\n", 1)[0]

    cross_site = _post(
        "/api/v1/cockpit-actions",
        {"action": "PAUSE_PAPER_ENTRIES", "subject_id": BOT_ID, "idempotency_key": "y"},
        tmp_path,
        extra=b"Sec-Fetch-Site: cross-site\r\n",
    )
    assert b" 403 " in cross_site.split(b"\r\n\r\n", 1)[0]

    malformed = _handle_request(
        b"POST /api/v1/cockpit-actions HTTP/1.1\r\nHost: localhost\r\n"
        b"Content-Type: application/json\r\nContent-Length: 1\r\n\r\n{",
        tmp_path,
    )
    assert b" 400 " in malformed.split(b"\r\n\r\n", 1)[0]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/v1/workspace-actions/data-update", {}),
        (
            "/api/v1/workspace-actions/decision",
            {"task_id": "T-011-05", "choice": "keep_deferred"},
        ),
        (
            "/api/v1/cockpit-actions",
            {"action": "PAUSE_PAPER_ENTRIES", "subject_id": BOT_ID},
        ),
    ],
)
def test_every_post_route_requires_an_idempotency_key(
    tmp_path: Path, path: str, payload: dict[str, object]
) -> None:
    response = _post(path, payload, tmp_path)
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 400 " in headers
    assert "idempotency_key" in json.loads(body)["error"]


def test_paper_pause_resume_and_acknowledgement_are_idempotent(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path, incident=True)
    pause = {
        "action": "PAUSE_PAPER_ENTRIES",
        "subject_id": BOT_ID,
        "idempotency_key": "cockpit-pause-1",
        "reason": "Operator pause",
    }

    first = perform_cockpit_action(tmp_path, pause)
    second = perform_cockpit_action(tmp_path, pause)
    assert first["idempotent"] is False and second["idempotent"] is True
    assert store.current_projection().entries_paused is True
    with pytest.raises(CockpitUnavailableError, match="idempotency key conflicts"):
        perform_cockpit_action(
            tmp_path,
            {
                "action": "RESUME_PAPER_ENTRIES",
                "subject_id": BOT_ID,
                "idempotency_key": "cockpit-pause-1",
                "reason": "Operator pause",
            },
        )

    perform_cockpit_action(
        tmp_path,
        {
            "action": "RESUME_PAPER_ENTRIES",
            "subject_id": BOT_ID,
            "idempotency_key": "cockpit-resume-1",
        },
    )
    assert store.current_projection().entries_paused is False

    item_id = build_cockpit(tmp_path, "all", now=NOW)["attention"][0]["item_id"]
    warning = build_cockpit(tmp_path, "all", now=NOW)["attention"][0]
    assert warning["severity"] == "WARNING"
    assert warning["action"] == "ACKNOWLEDGE"
    perform_cockpit_action(
        tmp_path,
        {"action": "ACKNOWLEDGE", "subject_id": item_id, "idempotency_key": "cockpit-ack-1"},
    )
    assert item_id in store.current_projection().acknowledged_item_ids
    audit_lines = (
        (tmp_path / "artifacts/human_decisions/cockpit_actions.jsonl").read_text().splitlines()
    )
    assert sum(json.loads(line)["phase"] == "COMPLETED" for line in audit_lines) == 3

    with pytest.raises(CockpitNotFoundError, match="unknown paper bot"):
        perform_cockpit_action(
            tmp_path,
            {
                "action": "PAUSE_PAPER_ENTRIES",
                "subject_id": "PAPERBOT-unknown",
                "idempotency_key": "cockpit-pause-unknown",
            },
        )


def test_critical_attention_cannot_be_acknowledged(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path, incident=True, critical_incident=True)
    item = next(
        item
        for item in build_cockpit(tmp_path, "all", now=NOW)["attention"]
        if item["source"] == "PAPER_RUNTIME"
    )

    assert item["severity"] == "CRITICAL"
    assert item["action"] is None
    with pytest.raises(CockpitActionError, match="informational or warning"):
        perform_cockpit_action(
            tmp_path,
            {
                "action": "ACKNOWLEDGE",
                "subject_id": item["item_id"],
                "idempotency_key": "critical-ack-rejected",
            },
        )
    assert item["item_id"] not in store.current_projection().acknowledged_item_ids
    assert (tmp_path / "artifacts/human_decisions/cockpit_actions.jsonl").read_text() == ""
    store.acknowledge_attention(
        item["item_id"],
        actor="legacy-operator",
        idempotency_key="legacy-critical-ack",
        occurred_at=NOW,
    )
    retained = next(
        candidate
        for candidate in build_cockpit(tmp_path, "all", now=NOW)["attention"]
        if candidate["item_id"] == item["item_id"]
    )
    assert retained["severity"] == "CRITICAL"
    assert retained["acknowledged"] is False
    assert retained["action"] is None


def test_informational_attention_can_be_acknowledged(tmp_path: Path) -> None:
    todo = tmp_path / "todos/99_test.md"
    todo.parent.mkdir(parents=True)
    todo.write_text("# Test initiative\n\n## T-999-01 Review evidence\n- Status: **TODO**.\n")
    item = build_cockpit(tmp_path, "24h", now=NOW)["attention"][0]

    assert item["severity"] == "INFO"
    assert item["action"] == "ACKNOWLEDGE"
    perform_cockpit_action(
        tmp_path,
        {
            "action": "ACKNOWLEDGE",
            "subject_id": item["item_id"],
            "idempotency_key": "info-ack-allowed",
        },
    )

    projected = next(
        candidate
        for candidate in build_cockpit(tmp_path, "24h", now=NOW)["attention"]
        if candidate["item_id"] == item["item_id"]
    )
    assert projected["acknowledged"] is True
    assert projected["action"] is None


def test_cockpit_audit_refuses_parent_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "human_decisions").symlink_to(outside, target_is_directory=True)

    with pytest.raises(CockpitUnavailableError):
        perform_cockpit_action(
            tmp_path,
            {
                "action": "ACKNOWLEDGE",
                "subject_id": "T-999-01",
                "idempotency_key": "symlink-escape",
            },
        )
    assert not (outside / "cockpit_actions.jsonl").exists()


def test_cockpit_action_retry_recovers_after_state_mutation_before_audit_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _paper_fixture(tmp_path)
    original = cockpit_module._append_action_record  # noqa: SLF001
    failed = False

    def crash_once(handle: object, record: dict[str, object]) -> None:
        nonlocal failed
        if record.get("phase") == "COMPLETED" and not failed:
            failed = True
            raise OSError("injected completion crash")
        original(handle, record)  # type: ignore[arg-type]

    monkeypatch.setattr(cockpit_module, "_append_action_record", crash_once)
    payload = {
        "action": "PAUSE_PAPER_ENTRIES",
        "subject_id": BOT_ID,
        "idempotency_key": "recover-after-mutation",
    }

    with pytest.raises(CockpitUnavailableError, match="audit is unavailable"):
        perform_cockpit_action(tmp_path, payload)
    assert store.current_projection().entries_paused is True

    retried = perform_cockpit_action(tmp_path, payload)
    assert retried["idempotent"] is True
    controls = [
        audit
        for audit in store.current_projection().audits
        if audit.idempotency_key == "recover-after-mutation"
    ]
    assert len(controls) == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts/human_decisions/cockpit_actions.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [record["phase"] for record in records] == ["PREPARED", "COMPLETED"]


def test_cockpit_retry_reconciles_pre_repair_paper_audit_orphan(tmp_path: Path) -> None:
    store = _paper_fixture(tmp_path)
    occurred_at = NOW - timedelta(seconds=1)
    store.set_entries_paused(
        True,
        actor="local_dashboard_operator",
        idempotency_key="legacy-orphan-pause",
        occurred_at=occurred_at,
    )
    assert not (tmp_path / "artifacts/human_decisions/cockpit_actions.jsonl").exists()

    result = perform_cockpit_action(
        tmp_path,
        {
            "action": "PAUSE_PAPER_ENTRIES",
            "subject_id": BOT_ID,
            "idempotency_key": "legacy-orphan-pause",
        },
    )

    assert result["idempotent"] is True
    assert result["recorded"]["acted_at"] == occurred_at.isoformat()
    retained = [
        audit
        for audit in store.current_projection().audits
        if audit.idempotency_key == "legacy-orphan-pause"
    ]
    assert len(retained) == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts/human_decisions/cockpit_actions.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [record["phase"] for record in records] == ["PREPARED", "COMPLETED"]
    assert {record["acted_at"] for record in records} == {occurred_at.isoformat()}


def test_schedule_actions_only_gate_future_materialization(tmp_path: Path) -> None:
    with JobStore(jobs_database(tmp_path), root=tmp_path) as store:
        store.initialize()
        store.add_schedule("daily-research", JobType.RESEARCH_LAB_V0, 60, NOW)
        perform_cockpit_action(
            tmp_path,
            {
                "action": "PAUSE_RESEARCH_SCHEDULE",
                "subject_id": "daily-research",
                "idempotency_key": "schedule-pause-1",
            },
        )
        assert store.materialize_due(now=NOW) == []
        resumed = perform_cockpit_action(
            tmp_path,
            {
                "action": "RESUME_RESEARCH_SCHEDULE",
                "subject_id": "daily-research",
                "idempotency_key": "schedule-resume-1",
            },
        )
        next_due = store.set_schedule_enabled(
            "daily-research",
            True,
            now=datetime.fromisoformat(resumed["recorded"]["acted_at"]),
        ).next_due
        assert next_due > datetime.fromisoformat(resumed["recorded"]["acted_at"])
        assert store.materialize_due(now=next_due - timedelta(microseconds=1)) == []
        assert len(store.materialize_due(now=next_due)) == 1


def test_cockpit_post_rejects_malformed_action_and_preserves_forbidden_routes(
    tmp_path: Path,
) -> None:
    malformed = _post("/api/v1/cockpit-actions", {"action": "PLACE_ORDER"}, tmp_path)
    assert b" 400 " in malformed.split(b"\r\n\r\n", 1)[0]

    missing = _post(
        "/api/v1/cockpit-actions",
        {"action": "PAUSE_PAPER_ENTRIES", "subject_id": BOT_ID, "idempotency_key": "missing"},
        tmp_path,
    )
    assert b" 409 " in missing.split(b"\r\n\r\n", 1)[0]
    assert not (tmp_path / "artifacts/paper/paper.sqlite3").exists()

    blocked = _post("/api/v1/orders", {}, tmp_path)
    assert b" 404 " in blocked.split(b"\r\n\r\n", 1)[0]
