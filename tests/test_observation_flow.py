"""Managed observation flow is deterministic, fail-closed, and order-inert."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tios.services.observations import flow

ROOT = Path(__file__).resolve().parents[1]
STARTED = datetime(2026, 7, 13, 21, 28, tzinfo=UTC)
HEARTBEAT = STARTED + timedelta(minutes=7)


def canonical(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def fixture_root(tmp_path: Path) -> Path:
    research = tmp_path / "research"
    research.mkdir(parents=True)
    for name in (
        "PROSPECTIVE_OBSERVATION_MANAGED_FLOW_V1.yaml",
        "PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml",
    ):
        (research / name).write_bytes((ROOT / "research" / name).read_bytes())
    script = tmp_path / "scripts/run_prospective_liquidation_checkpoints.py"
    script.parent.mkdir()
    script.write_text("# fixed observer fixture\n")
    observation = tmp_path / flow.OBSERVATION_ROOT
    (observation / "operations").mkdir(parents=True)
    status = {
        "schema_version": 1,
        "operations_contract_sha256": hashlib.sha256(
            (research / "PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml").read_bytes()
        ).hexdigest(),
        "run_commit": "2" * 40,
        "process_started_at": STARTED.isoformat(),
        "heartbeat_at": HEARTBEAT.isoformat(),
        "state": "OBSERVING",
        "connection_epoch": 2,
        "continuity_epoch": 2,
        "finalized_window_count": 1,
        "last_finalized_window_start": (STARTED + timedelta(minutes=2)).isoformat(),
        "last_failure_ref": None,
        "authority": flow.AUTHORITY,
    }
    (observation / "operations/status.json").write_bytes(canonical(status))
    session = {
        "schema_version": 5,
        "run_commit": status["run_commit"],
        "started_at": (STARTED + timedelta(minutes=2)).isoformat(),
        "ended_at": (STARTED + timedelta(minutes=7)).isoformat(),
        "source": {"status": "COMPLETE"},
        "authority": flow.AUTHORITY,
        "persistent_observation": {
            "operations_contract_sha256": status["operations_contract_sha256"],
            "run_id": "a" * 24,
            "checkpoint_index": 1,
            "connection_epoch": 2,
            "continuity_epoch": 2,
            "connection_opened_at": STARTED.isoformat(),
            "checkpoint_status": "FINALIZED",
            "planned_handoff": None,
        },
    }
    encoded = canonical(session)
    digest = hashlib.sha256(encoded).hexdigest()
    (observation / f"session_{digest}.json").write_bytes(encoded)
    return tmp_path


def test_adopted_intent_projects_target_continuity_and_freshness(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    intent = flow.write_run_intent(root, 8_640, mode="ADOPTED", now=HEARTBEAT)
    assert intent.stem.removeprefix("intent_") == hashlib.sha256(intent.read_bytes()).hexdigest()

    projection = flow.build_observation_projection(root, now=HEARTBEAT + timedelta(seconds=30))
    assert projection["availability"] == "AVAILABLE"
    assert projection["management"] == "MANAGED"
    assert projection["state"] == "OBSERVING"
    assert projection["freshness"] == "FRESH"
    assert projection["runtime"]["requested_checkpoint_count"] == 8_640
    assert projection["runtime"]["finalized_window_count"] == 1
    assert projection["runtime"]["remaining_checkpoint_count"] == 8_639
    assert projection["runtime"]["continuity_epoch"] == 2
    assert projection["evidence"]["longest_chain"] == 1
    assert projection["blockers"] == []
    assert projection["capabilities"]["execution_authority"] == "NONE"
    assert projection["capabilities"]["http_process_control"] is False


def test_projection_marks_stale_and_rejects_authority_drift(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    flow.write_run_intent(root, 10, mode="ADOPTED", now=HEARTBEAT)
    stale = flow.build_observation_projection(root, now=HEARTBEAT + timedelta(seconds=91))
    assert stale["state"] == stale["freshness"] == "STALE"
    assert stale["blockers"] == ["OBSERVER_STALE"]

    status_path = root / flow.OBSERVATION_ROOT / "operations/status.json"
    status = json.loads(status_path.read_text())
    status["authority"]["paper_orders"] = "ENABLED"
    status_path.write_bytes(canonical(status))
    drift = flow.build_observation_projection(root, now=HEARTBEAT)
    assert drift["availability"] == drift["state"] == "ERROR"
    assert "authority boundary changed" in drift["blockers"][0]


def test_projection_rejects_checkpoint_bytes_and_adopted_commit_drift(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    flow.write_run_intent(root, 10, mode="ADOPTED", now=HEARTBEAT)
    session = next((root / flow.OBSERVATION_ROOT).glob("session_*.json"))
    session.write_bytes(session.read_bytes() + b" ")
    changed = flow.build_observation_projection(root, now=HEARTBEAT)
    assert changed["availability"] == "ERROR"
    assert "checkpoint content hash mismatch" in changed["blockers"][0]

    root = fixture_root(tmp_path / "commit-drift")
    flow.write_run_intent(root, 10, mode="ADOPTED", now=HEARTBEAT)
    status_path = root / flow.OBSERVATION_ROOT / "operations/status.json"
    status = json.loads(status_path.read_text())
    status["run_commit"] = "4" * 40
    status_path.write_bytes(canonical(status))
    drift = flow.build_observation_projection(root, now=HEARTBEAT)
    assert drift["availability"] == "ERROR"
    assert "adopted observer commit drift" in drift["blockers"][0]


def test_fixed_command_and_active_run_refusal(tmp_path: Path) -> None:
    root = fixture_root(tmp_path)
    assert flow.observation_command(root, 2) == [
        sys.executable,
        str(root / flow.OBSERVER_SCRIPT),
        "--checkpoint-windows",
        "2",
    ]
    with pytest.raises(ValueError, match="between 1 and 8640"):
        flow.observation_command(root, 0)
    status_path = root / flow.OBSERVATION_ROOT / "operations/status.json"
    status = json.loads(status_path.read_text())
    status["heartbeat_at"] = datetime.now(tz=UTC).isoformat()
    status_path.write_bytes(canonical(status))
    with pytest.raises(flow.ObservationFlowError, match="already exists"):
        flow.run_managed_observation(root, 2)


def test_predeclared_intent_requires_clean_tracked_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = fixture_root(tmp_path)
    (root / flow.OBSERVATION_ROOT / "operations/status.json").unlink()
    monkeypatch.setattr(flow, "_git_head", lambda _: "3" * 40)
    monkeypatch.setattr(flow, "_tracked_worktree_clean", lambda _: False)
    with pytest.raises(flow.ObservationFlowError, match="clean tracked worktree"):
        flow.write_run_intent(root, 2, mode="PREDECLARED", now=STARTED)
    monkeypatch.setattr(flow, "_tracked_worktree_clean", lambda _: True)
    intent = flow.write_run_intent(root, 2, mode="PREDECLARED", now=STARTED)
    payload = json.loads(intent.read_text())
    assert payload["expected_run_commit"] == "3" * 40
    projection = flow.build_observation_projection(root, now=STARTED)
    assert projection["state"] == "PREDECLARED"
    assert projection["management"] == "MANAGED"
