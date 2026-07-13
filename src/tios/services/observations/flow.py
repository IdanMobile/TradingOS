"""Deterministic ownership and projection for the prospective observer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

FLOW_ID = "PROSPECTIVE-OBSERVATION-MANAGED-FLOW-V1"
FLOW_SPEC = Path("research/PROSPECTIVE_OBSERVATION_MANAGED_FLOW_V1.yaml")
OPERATIONS_CONTRACT = Path("research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml")
OBSERVATION_ROOT = Path("artifacts/prospective/BTC-LIQUIDATION-STRESS-V1")
OBSERVER_SCRIPT = Path("scripts/run_prospective_liquidation_checkpoints.py")
HEARTBEAT_FRESH_SECONDS = 60
HEARTBEAT_DELAYED_SECONDS = 90
ACTIVE_STATES = {"CONNECTING", "OBSERVING", "CHECKPOINTED"}
RUNTIME_STATES = {*ACTIVE_STATES, "FAILED_PARTIAL", "COMPLETED"}
AUTHORITY = {
    "execution_authority": "NONE",
    "venue_connection": "NONE",
    "market_data_transport": "PUBLIC_READ_ONLY",
    "paper_orders": "DISABLED",
    "live_orders": "DISABLED",
    "credentials_used": False,
}


class ObservationFlowError(RuntimeError):
    """Fail-closed managed-flow contract violation."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ObservationFlowError("observation timestamp is invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ObservationFlowError("observation timestamp has no timezone")
    return parsed.astimezone(UTC)


def _relative_file(root: Path, relative: Path) -> Path:
    repo = root.resolve()
    path = (repo / relative).resolve()
    if not path.is_relative_to(repo) or not path.is_file():
        raise ObservationFlowError(f"required managed-flow file is missing: {relative}")
    return path


def _contract_hash(root: Path, relative: Path) -> str:
    return _sha256(_relative_file(root, relative).read_bytes())


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ObservationFlowError(f"{label} is unreadable") from error
    if not isinstance(payload, dict):
        raise ObservationFlowError(f"{label} must be a JSON object")
    return cast(dict[str, Any], payload)


def _status_path(root: Path) -> Path:
    return root.resolve() / OBSERVATION_ROOT / "operations/status.json"


def _validate_status(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ObservationFlowError("observer status schema is invalid")
    if payload.get("operations_contract_sha256") != _contract_hash(root, OPERATIONS_CONTRACT):
        raise ObservationFlowError("observer status contract hash mismatch")
    if payload.get("authority") != AUTHORITY:
        raise ObservationFlowError("observer status authority boundary changed")
    if payload.get("state") not in RUNTIME_STATES:
        raise ObservationFlowError("observer status state is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("run_commit"))):
        raise ObservationFlowError("observer status commit is invalid")
    if any(
        not isinstance(payload.get(key), int) or int(payload[key]) < minimum
        for key, minimum in (
            ("connection_epoch", 1),
            ("continuity_epoch", 1),
            ("finalized_window_count", 0),
        )
    ):
        raise ObservationFlowError("observer status counters are invalid")
    started = _parse_utc(payload.get("process_started_at"))
    heartbeat = _parse_utc(payload.get("heartbeat_at"))
    if heartbeat < started:
        raise ObservationFlowError("observer heartbeat predates process start")
    last_window = payload.get("last_finalized_window_start")
    finalized = int(payload["finalized_window_count"])
    if (last_window is None) != (finalized == 0):
        raise ObservationFlowError("observer finalized-window status is inconsistent")
    if last_window is not None:
        _parse_utc(last_window)
    failure = payload.get("last_failure_ref")
    if failure is not None and (
        not isinstance(failure, str)
        or Path(failure).name != failure
        or not re.fullmatch(r"session_[0-9a-f]{64}\.json", failure)
    ):
        raise ObservationFlowError("observer failure reference is invalid")
    return payload


def _load_status(root: Path) -> dict[str, Any] | None:
    path = _status_path(root)
    return _validate_status(root, _load_object(path, "observer status")) if path.is_file() else None


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", result):
        raise ObservationFlowError("repository commit is invalid")
    return result


def _tracked_worktree_clean(root: Path) -> bool:
    output = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return not output.strip()


def _validate_checkpoint_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8_640:
        raise ValueError("checkpoint_windows must be between 1 and 8640")
    return value


def _intent_directory(root: Path) -> Path:
    return root.resolve() / OBSERVATION_ROOT / "operations/intents"


def write_run_intent(
    root: Path,
    checkpoint_windows: int,
    *,
    mode: Literal["PREDECLARED", "ADOPTED"],
    now: datetime | None = None,
) -> Path:
    """Write one immutable intent; ADOPTED binds the currently running frozen process."""
    root = root.resolve()
    requested = _validate_checkpoint_count(checkpoint_windows)
    created = (now or datetime.now(tz=UTC)).astimezone(UTC)
    status = _load_status(root) if mode == "ADOPTED" else None
    if mode == "ADOPTED" and (status is None or status["state"] not in ACTIVE_STATES):
        raise ObservationFlowError("only an active observer can be adopted")
    if mode == "PREDECLARED" and not _tracked_worktree_clean(root):
        raise ObservationFlowError("managed observation requires a clean tracked worktree")
    commit = str(status["run_commit"]) if status is not None else _git_head(root)
    payload = {
        "schema_version": 1,
        "managed_flow_id": FLOW_ID,
        "managed_flow_contract_sha256": _contract_hash(root, FLOW_SPEC),
        "intent_mode": mode,
        "created_at": created.isoformat(),
        "adopted_process_started_at": (
            status["process_started_at"] if status is not None else None
        ),
        "expected_run_commit": commit,
        "requested_checkpoint_count": requested,
        "operations_contract_sha256": _contract_hash(root, OPERATIONS_CONTRACT),
        "observer_command": OBSERVER_SCRIPT.as_posix(),
        "output_dir": OBSERVATION_ROOT.as_posix(),
        "authority": AUTHORITY,
    }
    encoded = _canonical(payload)
    digest = _sha256(encoded)
    directory = _intent_directory(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"intent_{digest}.json"
    if path.exists():
        if path.read_bytes() != encoded:
            raise ObservationFlowError("managed intent hash collision")
        return path
    descriptor, temporary = tempfile.mkstemp(prefix=".intent-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def _intents(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    directory = _intent_directory(root)
    if not directory.exists():
        return []
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("intent_*.json")):
        if path.stem.removeprefix("intent_") != _sha256(path.read_bytes()):
            raise ObservationFlowError("managed intent content hash mismatch")
        payload = _load_object(path, "managed intent")
        expected = {
            "schema_version": 1,
            "managed_flow_id": FLOW_ID,
            "managed_flow_contract_sha256": _contract_hash(root, FLOW_SPEC),
            "operations_contract_sha256": _contract_hash(root, OPERATIONS_CONTRACT),
            "observer_command": OBSERVER_SCRIPT.as_posix(),
            "output_dir": OBSERVATION_ROOT.as_posix(),
            "authority": AUTHORITY,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ObservationFlowError("managed intent contract changed")
        if payload.get("intent_mode") not in {"PREDECLARED", "ADOPTED"}:
            raise ObservationFlowError("managed intent mode is invalid")
        _parse_utc(payload.get("created_at"))
        if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("expected_run_commit"))):
            raise ObservationFlowError("managed intent commit is invalid")
        _validate_checkpoint_count(payload.get("requested_checkpoint_count"))
        adopted = payload.get("adopted_process_started_at")
        if (payload["intent_mode"] == "ADOPTED") != (adopted is not None):
            raise ObservationFlowError("managed adoption identity is invalid")
        if adopted is not None:
            _parse_utc(adopted)
        found.append((path, payload))
    return found


def _matching_intent(
    status: dict[str, Any] | None, intents: list[tuple[Path, dict[str, Any]]]
) -> tuple[Path, dict[str, Any]] | None:
    if status is None:
        predeclared = [item for item in intents if item[1]["intent_mode"] == "PREDECLARED"]
        return (
            max(predeclared, key=lambda item: _parse_utc(item[1]["created_at"]))
            if predeclared
            else None
        )
    started = _parse_utc(status["process_started_at"])
    for _, payload in intents:
        adopted = payload.get("adopted_process_started_at")
        if (
            payload["intent_mode"] == "ADOPTED"
            and adopted is not None
            and _parse_utc(adopted) == started
            and payload["expected_run_commit"] != status["run_commit"]
        ):
            raise ObservationFlowError("adopted observer commit drift")
    candidates = []
    for item in intents:
        payload = item[1]
        if payload["expected_run_commit"] != status["run_commit"]:
            continue
        if payload["intent_mode"] == "ADOPTED":
            if _parse_utc(payload["adopted_process_started_at"]) == started:
                candidates.append(item)
        elif _parse_utc(payload["created_at"]) <= started:
            candidates.append(item)
    return (
        max(candidates, key=lambda item: _parse_utc(item[1]["created_at"])) if candidates else None
    )


def _run_checkpoints(root: Path, status: dict[str, Any]) -> list[dict[str, Any]]:
    directory = root.resolve() / OBSERVATION_ROOT
    started = _parse_utc(status["process_started_at"])
    rows = []
    for path in directory.glob("session_*.json"):
        if path.stem.removeprefix("session_") != _sha256(path.read_bytes()):
            raise ObservationFlowError("prospective checkpoint content hash mismatch")
        payload = _load_object(path, "prospective checkpoint")
        metadata = payload.get("persistent_observation")
        if not isinstance(metadata, dict) or payload.get("schema_version") != 5:
            continue
        if payload.get("run_commit") != status["run_commit"]:
            continue
        if _parse_utc(payload.get("started_at")) < started:
            continue
        if payload.get("authority") != AUTHORITY:
            raise ObservationFlowError("prospective checkpoint authority boundary changed")
        if metadata.get("operations_contract_sha256") != status["operations_contract_sha256"]:
            raise ObservationFlowError("prospective checkpoint contract hash mismatch")
        if metadata.get("checkpoint_status") not in {"FINALIZED", "FAILED_PARTIAL"}:
            raise ObservationFlowError("prospective checkpoint status is invalid")
        rows.append(
            {
                "artifact_ref": path.relative_to(root).as_posix(),
                "started_at": payload["started_at"],
                "checkpoint_status": metadata["checkpoint_status"],
                "checkpoint_index": int(metadata["checkpoint_index"]),
                "connection_epoch": int(metadata["connection_epoch"]),
                "continuity_epoch": int(metadata["continuity_epoch"]),
            }
        )
    return sorted(rows, key=lambda row: (row["started_at"], row["artifact_ref"]))


def _longest_chain(rows: list[dict[str, Any]]) -> int:
    longest = current = 0
    previous: tuple[int, datetime] | None = None
    for row in (item for item in rows if item["checkpoint_status"] == "FINALIZED"):
        key = (int(row["continuity_epoch"]), _parse_utc(row["started_at"]))
        current = (
            current + 1
            if previous is not None
            and key[0] == previous[0]
            and key[1] - previous[1] == timedelta(minutes=5)
            else 1
        )
        longest = max(longest, current)
        previous = key
    return longest


def _base_projection() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "managed_flow_id": FLOW_ID,
        "availability": "MISSING",
        "management": "UNMANAGED",
        "state": "MISSING",
        "freshness": "UNAVAILABLE",
        "intent": None,
        "runtime": None,
        "evidence": {"finalized": 0, "failed_partial": 0, "longest_chain": 0, "latest": []},
        "blockers": ["RUN_INTENT_MISSING", "OBSERVER_STATUS_MISSING"],
        "capabilities": {
            "market_data_transport": "PUBLIC_READ_ONLY",
            "credentials_used": False,
            "venue_connection": "NONE",
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "execution_authority": "NONE",
            "http_process_control": False,
            "auto_restart": False,
            "backfill": False,
        },
    }


def build_observation_projection(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Build one fail-closed read-only projection from intent, heartbeat, and checkpoints."""
    projection = _base_projection()
    try:
        as_of = (now or datetime.now(tz=UTC)).astimezone(UTC)
        status = _load_status(root)
        intents = _intents(root)
        matched = _matching_intent(status, intents)
        if status is None:
            if matched is not None:
                path, intent = matched
                projection.update(
                    availability="AVAILABLE",
                    management="MANAGED",
                    state="PREDECLARED",
                    freshness="WAITING",
                    intent={**intent, "artifact_ref": path.relative_to(root).as_posix()},
                    blockers=["OBSERVER_STATUS_MISSING"],
                )
            return projection
        heartbeat = _parse_utc(status["heartbeat_at"])
        age = max(0, int((as_of - heartbeat).total_seconds()))
        if status["state"] in ACTIVE_STATES:
            if age <= HEARTBEAT_FRESH_SECONDS:
                state, freshness = status["state"], "FRESH"
            elif age <= HEARTBEAT_DELAYED_SECONDS:
                state, freshness = "DELAYED", "DELAYED"
            else:
                state, freshness = "STALE", "STALE"
        else:
            state, freshness = status["state"], "TERMINAL"
        checkpoints = _run_checkpoints(root, status)
        finalized = [row for row in checkpoints if row["checkpoint_status"] == "FINALIZED"]
        failures = [row for row in checkpoints if row["checkpoint_status"] == "FAILED_PARTIAL"]
        if len(finalized) != status["finalized_window_count"]:
            raise ObservationFlowError("observer status/checkpoint count mismatch")
        intent_payload = matched[1] if matched is not None else None
        target = int(intent_payload["requested_checkpoint_count"]) if intent_payload else None
        blockers = []
        if matched is None:
            blockers.append("RUN_INTENT_MISSING")
        if state in {"DELAYED", "STALE", "FAILED_PARTIAL"}:
            blockers.append(f"OBSERVER_{state}")
        projection.update(
            availability="AVAILABLE",
            management="MANAGED" if matched else "UNMANAGED",
            state=state,
            freshness=freshness,
            intent=(
                {**intent_payload, "artifact_ref": matched[0].relative_to(root).as_posix()}
                if matched and intent_payload
                else None
            ),
            runtime={
                "run_commit": status["run_commit"],
                "process_started_at": status["process_started_at"],
                "heartbeat_at": status["heartbeat_at"],
                "heartbeat_age_seconds": age,
                "requested_checkpoint_count": target,
                "finalized_window_count": len(finalized),
                "remaining_checkpoint_count": None
                if target is None
                else max(0, target - len(finalized)),
                "connection_epoch": status["connection_epoch"],
                "continuity_epoch": status["continuity_epoch"],
                "last_finalized_window_start": status["last_finalized_window_start"],
                "last_failure_ref": status["last_failure_ref"],
            },
            evidence={
                "finalized": len(finalized),
                "failed_partial": len(failures),
                "longest_chain": _longest_chain(checkpoints),
                "latest": checkpoints[-5:],
            },
            blockers=blockers,
        )
        return projection
    except Exception as error:
        projection.update(
            availability="ERROR",
            state="ERROR",
            freshness="UNAVAILABLE",
            blockers=[f"{type(error).__name__}: {error}"],
        )
        return projection


def observation_command(root: Path, checkpoint_windows: int) -> list[str]:
    requested = _validate_checkpoint_count(checkpoint_windows)
    script = _relative_file(root, OBSERVER_SCRIPT)
    return [sys.executable, str(script), "--checkpoint-windows", str(requested)]


def run_managed_observation(root: Path, checkpoint_windows: int) -> int:
    """Predeclare and run exactly the fixed prospective-observer command."""
    root = root.resolve()
    status = _load_status(root)
    if status is not None and status["state"] in ACTIVE_STATES:
        age = (datetime.now(tz=UTC) - _parse_utc(status["heartbeat_at"])).total_seconds()
        if age <= HEARTBEAT_DELAYED_SECONDS:
            raise ObservationFlowError("an active prospective observer already exists")
    write_run_intent(root, checkpoint_windows, mode="PREDECLARED")
    environment = {
        "HOME": str(root),
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    }
    return subprocess.call(
        observation_command(root, checkpoint_windows),
        cwd=root,
        env=environment,
        start_new_session=False,
    )
