"""Read-only operator projection of the local jobs database."""

from __future__ import annotations

import fcntl
import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.services.jobs.runner import default_database
from tios.services.jobs.store import (
    MAX_DB_IMAGE_BYTES,
    SCHEMA_VERSION,
    JobState,
    JobStore,
    JobType,
    _verify_directory_entry,
)

PROJECTION_SCHEMA_VERSION = 1
LATEST_LIMIT = 20
_SENSITIVE = re.compile(r"(?i)(api[_-]?key|authorization|bearer|credential|password|secret|token)")


def _base(availability: str) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "availability": availability,
        "database": {
            "schema_version": None,
            "integrity": "UNAVAILABLE",
            "capacity": {"bytes": None, "max_bytes": MAX_DB_IMAGE_BYTES, "usage_ratio": None},
        },
        "counts": {
            "states": {state.value: 0 for state in JobState},
            "types": {job_type.value: 0 for job_type in JobType},
        },
        "latest_jobs": [],
        "schedules": [],
        "worker": {
            "mode": "LOCAL_OPERATOR_CLI_ONLY",
            "polling": "ON_DEMAND_OR_CONTINUOUS",
            "http_endpoint": False,
        },
        "capabilities": {
            "allowed": [
                "OFFLINE_RESEARCH_LAB_V0",
                "DATA_QUALITY_PLACEHOLDER",
                "REPORT_REFRESH_PLACEHOLDER",
                "READ_ONLY_STATUS",
            ],
            "prohibited": [
                "VENUE_CONNECTIVITY",
                "ORDER_EXECUTION",
                "PAPER_EXECUTION",
                "LIVE_EXECUTION",
                "CREDENTIAL_ACCESS",
                "NETWORK_JOB_EXECUTION",
                "HTTP_JOB_CONTROL",
            ],
        },
    }


def _safe_text(value: object, *, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = str(value)
    if _SENSITIVE.search(text):
        return "[REDACTED]"
    return text[:limit]


def _safe_error(value: object) -> str | None:
    if value is None:
        return None
    return "[REDACTED]"


@contextmanager
def _snapshot(store: JobStore) -> Iterator[tuple[sqlite3.Connection, int] | None]:
    anchor_fd, parent_fd, parent_name = store._open_parent_anchor(create=False)
    connection: sqlite3.Connection | None = None
    try:
        fcntl.flock(parent_fd, fcntl.LOCK_SH)
        _verify_directory_entry(anchor_fd, parent_name, parent_fd)
        store._assert_legacy_wal_inactive(parent_fd)
        retained = store._read_file(parent_fd, store._filename)
        store._assert_legacy_wal_inactive(parent_fd)
        if not retained:
            yield None
            return
        if len(retained) >= 20 and retained[18:20] == b"\x02\x02":
            raise RuntimeError("legacy WAL image requires operator migration")
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.deserialize(retained)
        yield connection, len(retained)
    finally:
        if connection is not None:
            connection.close()
        _verify_directory_entry(anchor_fd, parent_name, parent_fd)
        fcntl.flock(parent_fd, fcntl.LOCK_UN)
        os.close(parent_fd)
        os.close(anchor_fd)


def _validated_connection(connection: sqlite3.Connection, image_bytes: int) -> int:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    recorded = int(connection.execute("SELECT version FROM schema_version").fetchone()[0])
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    if version != SCHEMA_VERSION or recorded != SCHEMA_VERSION or integrity != "ok":
        raise RuntimeError("jobs database schema or integrity check failed")
    if image_bytes > MAX_DB_IMAGE_BYTES:
        raise RuntimeError("jobs database capacity check failed")
    return version


def _counts(connection: sqlite3.Connection, field: str, allowed: set[str]) -> dict[str, int]:
    rows = connection.execute(f"SELECT {field}, COUNT(*) AS count FROM jobs GROUP BY {field}")
    found = {str(row[field]): int(row["count"]) for row in rows}
    if not set(found).issubset(allowed):
        raise RuntimeError("jobs database contains a prohibited value")
    return {name: found.get(name, 0) for name in sorted(allowed)}


def _artifact(value: object) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("jobs database contains an unsafe artifact reference")
    return path.as_posix()


def _time(value: object, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise RuntimeError("jobs database is missing a required timestamp")
        return None
    if not isinstance(value, str):
        raise RuntimeError("jobs database contains an invalid timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise RuntimeError("jobs database timestamp is not UTC")
    return value


def _latest(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT job_id, job_type, state, attempt_count, max_attempts,
                  created_at, due_at, started_at, finished_at,
                  result_artifact_ref, result_digest, result_reused, error
           FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?""",
        (LATEST_LIMIT,),
    )
    jobs: list[dict[str, Any]] = []
    for row in rows:
        job_id = str(row["job_id"])
        if not job_id.startswith("JOB-"):
            raise RuntimeError("jobs database contains an invalid job identity")
        digest = row["result_digest"]
        if digest is not None and (
            len(str(digest)) != 64
            or any(character not in "0123456789abcdef" for character in str(digest))
        ):
            raise RuntimeError("jobs database contains an invalid result digest")
        jobs.append(
            {
                "job_id": job_id,
                "type": str(row["job_type"]),
                "state": str(row["state"]),
                "times": {
                    "created": _time(row["created_at"], required=True),
                    "due": _time(row["due_at"], required=True),
                    "started": _time(row["started_at"]),
                    "finished": _time(row["finished_at"]),
                },
                "attempt": {"count": int(row["attempt_count"]), "max": int(row["max_attempts"])},
                "result": {
                    "artifact_ref": _artifact(row["result_artifact_ref"]),
                    "digest": digest,
                    "reused": None if row["result_reused"] is None else bool(row["result_reused"]),
                },
                "error": _safe_error(row["error"]),
            }
        )
    return jobs


def _schedules(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT schedule_id, job_type, interval_seconds, next_due,
                  max_attempts, timeout_seconds
           FROM schedules ORDER BY next_due, schedule_id"""
    )
    schedules = [
        {
            "schedule_id": _safe_text(row["schedule_id"], limit=120),
            "type": str(row["job_type"]),
            "interval_seconds": int(row["interval_seconds"]),
            "next_due": _time(row["next_due"], required=True),
            "max_attempts": int(row["max_attempts"]),
            "timeout_seconds": int(row["timeout_seconds"]),
        }
        for row in rows
    ]
    if any(item["type"] not in {job_type.value for job_type in JobType} for item in schedules):
        raise RuntimeError("jobs schedule contains a prohibited type")
    return schedules


def build_jobs_projection(root: Path) -> dict[str, Any]:
    """Return a fail-closed, JSON-safe snapshot without changing retained state."""
    projection = _base("MISSING")
    store: JobStore | None = None
    try:
        store = JobStore(default_database(root), root=root)
        with _snapshot(store) as snapshot:
            if snapshot is None:
                return projection
            connection, image_bytes = snapshot
            version = _validated_connection(connection, image_bytes)
            projection["availability"] = "AVAILABLE"
            projection["database"] = {
                "schema_version": version,
                "integrity": "PASS",
                "capacity": {
                    "bytes": image_bytes,
                    "max_bytes": MAX_DB_IMAGE_BYTES,
                    "usage_ratio": round(image_bytes / MAX_DB_IMAGE_BYTES, 6),
                },
            }
            projection["counts"] = {
                "states": _counts(connection, "state", {state.value for state in JobState}),
                "types": _counts(connection, "job_type", {job_type.value for job_type in JobType}),
            }
            projection["latest_jobs"] = _latest(connection)
            projection["schedules"] = _schedules(connection)
        return projection
    except FileNotFoundError:
        return projection
    except Exception:
        return _base("ERROR")
    finally:
        if store is not None:
            store.close()
