"""SQLite persistence for bounded local jobs."""

from __future__ import annotations

import builtins
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import threading
import uuid
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 4
MAX_LIST_LIMIT = 1000
MAX_DB_IMAGE_BYTES = 64 * 1024 * 1024
LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID = "s2-production-offline-research-lab-v0-every-6h-v1"
LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON = (
    "quarantined: legacy RESEARCH_LAB_V0 queue disabled before autonomous research rollout"
)
LEGACY_RESEARCH_LAB_V0_AUDIT_OUTBOX = "legacy_research_lab_v0_quarantine_audit_outbox"
LEGACY_RESEARCH_LAB_V0_AUDIT_PREFIX = "legacy_research_lab_v0_quarantine_"
LEGACY_RESEARCH_LAB_V0_OUTBOX_SQL = """CREATE TABLE legacy_research_lab_v0_quarantine_audit_outbox (
           operation_key INTEGER PRIMARY KEY CHECK (operation_key = 1),
           audit_sha256 TEXT NOT NULL UNIQUE CHECK (length(audit_sha256) = 64),
           plan_sha256 TEXT NOT NULL CHECK (length(plan_sha256) = 64),
           artifact_name TEXT NOT NULL UNIQUE,
           temporary_name TEXT NOT NULL UNIQUE,
           payload BLOB NOT NULL,
           applied_at TEXT NOT NULL,
           published_at TEXT
       )"""


class JobType(StrEnum):
    RESEARCH_LAB_V0 = "RESEARCH_LAB_V0"
    DATA_QUALITY = "DATA_QUALITY"
    REPORT_REFRESH = "REPORT_REFRESH"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC).isoformat()


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _identity(key: str) -> str:
    return f"JOB-{hashlib.sha256(key.encode()).hexdigest()[:20]}"


def _lease_duration(seconds: int) -> int:
    return min(300, max(5, seconds))


@dataclass(frozen=True)
class Job:
    job_id: str
    idempotency_key: str
    job_type: JobType
    state: JobState
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int
    timeout_seconds: int
    created_at: datetime
    due_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    result_artifact_ref: str | None
    result_digest: str | None
    result_reused: bool | None
    cancel_requested: bool
    error: str | None


@dataclass(frozen=True)
class Schedule:
    schedule_id: str
    job_type: JobType
    payload: dict[str, Any]
    interval_seconds: int
    next_due: datetime
    max_attempts: int
    timeout_seconds: int
    enabled: bool


@dataclass(frozen=True)
class LegacyResearchLabV0QuarantinePlan:
    db_schema_before: int
    schedule: dict[str, Any] | None
    queued_job_ids: tuple[str, ...]
    queued_count: int
    new_count: int
    retry_count: int
    preserved_terminal_counts: dict[str, int]
    research_job_fingerprints: tuple[dict[str, str], ...]
    research_schedule_fingerprints: tuple[dict[str, str], ...]
    terminal_evidence: tuple[dict[str, Any], ...]
    non_target_job_count: int
    non_target_jobs_sha256: str
    non_target_schedule_count: int
    non_target_schedules_sha256: str
    blockers: tuple[str, ...]
    plan_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "db_schema_before": self.db_schema_before,
            "schedule": self.schedule,
            "queued_job_ids": list(self.queued_job_ids),
            "queued_count": self.queued_count,
            "new_count": self.new_count,
            "retry_count": self.retry_count,
            "preserved_terminal_counts": self.preserved_terminal_counts,
            "research_job_fingerprints": list(self.research_job_fingerprints),
            "research_schedule_fingerprints": list(self.research_schedule_fingerprints),
            "terminal_evidence": list(self.terminal_evidence),
            "non_target_job_count": self.non_target_job_count,
            "non_target_jobs_sha256": self.non_target_jobs_sha256,
            "non_target_schedule_count": self.non_target_schedule_count,
            "non_target_schedules_sha256": self.non_target_schedules_sha256,
            "blockers": list(self.blockers),
            "plan_sha256": self.plan_sha256,
        }


@dataclass(frozen=True)
class LegacyResearchLabV0QuarantineResult:
    status: str
    plan: LegacyResearchLabV0QuarantinePlan
    cancelled_job_ids: tuple[str, ...]
    applied_at: datetime | None
    audit_artifact_ref: str | None
    audit_sha256: str | None
    audit_publication_state: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "plan": self.plan.as_dict(),
            "cancelled_job_ids": list(self.cancelled_job_ids),
            "applied_at": None if self.applied_at is None else _stamp(self.applied_at),
            "audit_artifact_ref": self.audit_artifact_ref,
            "audit_sha256": self.audit_sha256,
            "audit_publication_state": self.audit_publication_state,
        }


class LegacyResearchLabV0QuarantineRefusal(RuntimeError):
    """The fixed quarantine preconditions were not met; no database write occurred."""


class LegacyResearchLabV0AuditPublicationError(RuntimeError):
    """The database committed, but its immutable audit artifact was not published."""

    def __init__(
        self,
        message: str,
        *,
        result: LegacyResearchLabV0QuarantineResult,
        audit_payload: bytes,
        audit_artifact_ref: str,
    ) -> None:
        super().__init__(message)
        self.result = result
        self.audit_payload = audit_payload
        self.audit_artifact_ref = audit_artifact_ref


_MIGRATIONS: tuple[tuple[str, ...], ...] = (
    (
        "CREATE TABLE schema_version (version INTEGER NOT NULL)",
        "INSERT INTO schema_version(version) VALUES (0)",
        """CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL UNIQUE,
        job_type TEXT NOT NULL CHECK (
            job_type IN ('RESEARCH_LAB_V0', 'DATA_QUALITY', 'REPORT_REFRESH')
        ),
        state TEXT NOT NULL CHECK (
            state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
        ),
        payload_json TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        max_attempts INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
        timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds BETWEEN 1 AND 86400),
        created_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        lease_owner TEXT,
        lease_expires_at TEXT,
        result_artifact_ref TEXT,
        result_digest TEXT,
        result_reused INTEGER,
        error TEXT
    )""",
        "CREATE INDEX jobs_claim_idx ON jobs(state, due_at, lease_expires_at)",
        """CREATE TRIGGER jobs_identity_immutable
    BEFORE UPDATE OF job_id, idempotency_key, job_type ON jobs
    BEGIN
        SELECT RAISE(ABORT, 'job identity is immutable');
    END""",
        """CREATE TABLE schedules (
        schedule_id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL CHECK (
            job_type IN ('RESEARCH_LAB_V0', 'DATA_QUALITY', 'REPORT_REFRESH')
        ),
        payload_json TEXT NOT NULL,
        interval_seconds INTEGER NOT NULL CHECK (interval_seconds > 0),
        next_due TEXT NOT NULL,
        max_attempts INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
        timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds BETWEEN 1 AND 86400)
    )""",
    ),
    (
        """ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0
        CHECK (cancel_requested IN (0, 1))""",
    ),
    (
        """ALTER TABLE schedules ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1
        CHECK (enabled IN (0, 1))""",
    ),
    (LEGACY_RESEARCH_LAB_V0_OUTBOX_SQL,),
)


def confined_database(path: Path, root: Path) -> Path:
    repo = Path(os.path.realpath(root))
    allowed = (repo / "artifacts/jobs").resolve()
    if not allowed.is_relative_to(repo):
        raise ValueError("artifacts/jobs must remain within the repository")
    candidate = path if path.is_absolute() else repo / path
    normalized = candidate.resolve()
    try:
        relative = normalized.relative_to(allowed)
    except ValueError:
        raise ValueError("jobs database must remain within repository artifacts/jobs") from None
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("jobs database must name a file within repository artifacts/jobs")
    return normalized


def _open_directory(parent_fd: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    opened = os.fstat(descriptor)
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(linked.st_mode) or (opened.st_dev, opened.st_ino) != (
        linked.st_dev,
        linked.st_ino,
    ):
        os.close(descriptor)
        raise ValueError(f"directory anchor changed while opening {name}")
    return descriptor


def _verify_regular_entry(parent_fd: int, name: str, descriptor: int, label: str) -> None:
    opened = os.fstat(descriptor)
    try:
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise RuntimeError(f"{label} identity changed; refusing to overwrite") from None
    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
        linked.st_dev,
        linked.st_ino,
    ):
        raise RuntimeError(f"{label} identity changed; refusing to overwrite")


def _verify_directory_entry(parent_fd: int, name: str, descriptor: int) -> None:
    opened = os.fstat(descriptor)
    try:
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise RuntimeError("jobs directory identity changed; refusing publication") from None
    if not stat.S_ISDIR(linked.st_mode) or (opened.st_dev, opened.st_ino) != (
        linked.st_dev,
        linked.st_ino,
    ):
        raise RuntimeError("jobs directory identity changed; refusing publication")


def _apply_migration(
    connection: sqlite3.Connection, statements: tuple[str, ...], version: int
) -> None:
    for statement in statements:
        connection.execute(statement)
    connection.execute("UPDATE schema_version SET version = ?", (version,))
    connection.execute(f"PRAGMA user_version = {version}")


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _canonical_sqlite_value(value: object) -> dict[str, Any]:
    if value is None:
        return {"sqlite_type": "NULL", "value": None}
    if isinstance(value, int):
        return {"sqlite_type": "INTEGER", "value": value}
    if isinstance(value, float):
        return {"sqlite_type": "REAL", "value": value.hex()}
    if isinstance(value, str):
        return {"sqlite_type": "TEXT", "value": value}
    if isinstance(value, bytes):
        return {"sqlite_type": "BLOB", "value_hex": value.hex()}
    raise LegacyResearchLabV0QuarantineRefusal(
        f"unsupported SQLite value type in quarantine plan: {type(value).__name__}"
    )


def _canonical_row(row: sqlite3.Row) -> dict[str, Any]:
    material: dict[str, Any] = {}
    for key in sorted(row.keys()):
        material[key] = _canonical_sqlite_value(row[key])
    return material


def _row_fingerprint(row: sqlite3.Row) -> str:
    return hashlib.sha256(_canonical_json(_canonical_row(row))).hexdigest()


def _rows_digest(rows: list[sqlite3.Row]) -> str:
    material = [_canonical_row(row) for row in rows]
    return hashlib.sha256(_canonical_json({"rows": material})).hexdigest()


def _quarantine_plan(
    connection: sqlite3.Connection,
) -> LegacyResearchLabV0QuarantinePlan:
    try:
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        version_rows = connection.execute("SELECT version FROM schema_version").fetchall()
        if len(version_rows) != 1:
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: schema_version must contain exactly one row"
            )
        recorded_version = int(version_rows[0][0])
        if user_version != recorded_version:
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: PRAGMA user_version and schema_version disagree"
            )
        if user_version not in {2, 3, 4}:
            raise LegacyResearchLabV0QuarantineRefusal(
                f"unsupported jobs schema version {user_version}; expected 2, 3, or 4"
            )
        _validate_quarantine_audit_outbox_schema(connection, required=user_version == 4)
        schedule_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(schedules)").fetchall()
        }
        job_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        expected_columns = {
            "schedule_id",
            "job_type",
            "payload_json",
            "interval_seconds",
            "next_due",
            "max_attempts",
            "timeout_seconds",
        }
        if not expected_columns.issubset(schedule_columns):
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: schedules columns are incomplete"
            )
        expected_job_columns = {
            "job_id",
            "job_type",
            "state",
            "payload_json",
            "attempt_count",
            "cancel_requested",
        }
        if not expected_job_columns.issubset(job_columns):
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: jobs columns are incomplete"
            )
        if user_version == 2 and "enabled" in schedule_columns:
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: v2 unexpectedly contains schedules.enabled"
            )
        if user_version in {3, 4} and "enabled" not in schedule_columns:
            raise LegacyResearchLabV0QuarantineRefusal(
                "malformed jobs schema: v3/v4 is missing schedules.enabled"
            )
        schedules = connection.execute("SELECT * FROM schedules ORDER BY schedule_id").fetchall()
        jobs = connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
        valid_job_types = {member.value for member in JobType}
        valid_job_states = {member.value for member in JobState}
        for row in schedules:
            if row["job_type"] not in valid_job_types:
                raise LegacyResearchLabV0QuarantineRefusal(
                    f"malformed schedule job_type: {row['schedule_id']}"
                )
            json.loads(row["payload_json"])
        for row in jobs:
            if row["job_type"] not in valid_job_types or row["state"] not in valid_job_states:
                raise LegacyResearchLabV0QuarantineRefusal(
                    f"malformed job type or state: {row['job_id']}"
                )
            json.loads(row["payload_json"])
    except LegacyResearchLabV0QuarantineRefusal:
        raise
    except (sqlite3.Error, TypeError, ValueError, IndexError) as error:
        raise LegacyResearchLabV0QuarantineRefusal(f"malformed jobs database: {error}") from error

    blockers: list[str] = []
    target = next(
        (row for row in schedules if row["schedule_id"] == LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID),
        None,
    )
    research_schedules = [row for row in schedules if row["job_type"] == JobType.RESEARCH_LAB_V0]
    extras = sorted(
        row["schedule_id"]
        for row in research_schedules
        if row["schedule_id"] != LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID
    )
    if extras:
        blockers.append(f"unexpected RESEARCH_LAB_V0 schedules: {', '.join(extras)}")

    schedule: dict[str, Any] | None = None
    if target is None:
        blockers.append(f"required schedule is missing: {LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID}")
    else:
        try:
            payload = json.loads(target["payload_json"])
            interval_seconds = int(target["interval_seconds"])
            max_attempts = int(target["max_attempts"])
            timeout_seconds = int(target["timeout_seconds"])
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            payload = None
            interval_seconds = -1
            max_attempts = -1
            timeout_seconds = -1
            blockers.append(f"target schedule payload is malformed: {error}")
        enabled = True if user_version == 2 else bool(target["enabled"])
        schedule = {
            "schedule_id": target["schedule_id"],
            "job_type": target["job_type"],
            "payload": payload,
            "interval_seconds": interval_seconds,
            "next_due": target["next_due"],
            "max_attempts": max_attempts,
            "timeout_seconds": timeout_seconds,
            "enabled": enabled,
            "enabled_source": "implicit_v2" if user_version == 2 else "explicit_v3_v4",
        }
        if target["job_type"] != JobType.RESEARCH_LAB_V0:
            blockers.append("target schedule job_type is not RESEARCH_LAB_V0")
        if payload != {}:
            blockers.append("target schedule payload is not the fixed empty object")
        if interval_seconds != 21_600:
            blockers.append("target schedule interval_seconds is not 21600")
        if max_attempts != 1:
            blockers.append("target schedule max_attempts is not 1")
        if timeout_seconds != 3_600:
            blockers.append("target schedule timeout_seconds is not 3600")

    research_jobs = [row for row in jobs if row["job_type"] == JobType.RESEARCH_LAB_V0]
    running_ids = sorted(row["job_id"] for row in research_jobs if row["state"] == JobState.RUNNING)
    if running_ids:
        blockers.append(f"RUNNING RESEARCH_LAB_V0 jobs exist: {', '.join(running_ids)}")
    queued = sorted(
        (row for row in research_jobs if row["state"] == JobState.QUEUED),
        key=lambda row: row["job_id"],
    )
    terminal_counts = {
        state.value: sum(row["state"] == state for row in research_jobs)
        for state in (JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED)
    }
    research_job_fingerprints = tuple(
        {"job_id": str(row["job_id"]), "row_sha256": _row_fingerprint(row)}
        for row in sorted(research_jobs, key=lambda item: item["job_id"])
    )
    research_schedule_fingerprints = tuple(
        {"schedule_id": str(row["schedule_id"]), "row_sha256": _row_fingerprint(row)}
        for row in sorted(research_schedules, key=lambda item: item["schedule_id"])
    )
    terminal_evidence = tuple(
        {
            "job_id": str(row["job_id"]),
            "state": str(row["state"]),
            "result_artifact_ref": row["result_artifact_ref"],
            "result_digest": row["result_digest"],
            "row_sha256": _row_fingerprint(row),
        }
        for row in sorted(research_jobs, key=lambda item: item["job_id"])
        if row["state"] in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
    )
    non_target_jobs = [row for row in jobs if row["job_type"] != JobType.RESEARCH_LAB_V0]
    non_target_schedules = [
        row for row in schedules if row["schedule_id"] != LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID
    ]
    body: dict[str, Any] = {
        "db_schema_before": user_version,
        "schedule": schedule,
        "queued_job_ids": [row["job_id"] for row in queued],
        "queued_count": len(queued),
        "new_count": sum(int(row["attempt_count"]) == 0 for row in queued),
        "retry_count": sum(int(row["attempt_count"]) > 0 for row in queued),
        "preserved_terminal_counts": terminal_counts,
        "research_job_fingerprints": list(research_job_fingerprints),
        "research_schedule_fingerprints": list(research_schedule_fingerprints),
        "terminal_evidence": list(terminal_evidence),
        "non_target_job_count": len(non_target_jobs),
        "non_target_jobs_sha256": _rows_digest(non_target_jobs),
        "non_target_schedule_count": len(non_target_schedules),
        "non_target_schedules_sha256": _rows_digest(non_target_schedules),
        "blockers": sorted(set(blockers)),
    }
    plan_sha256 = hashlib.sha256(_canonical_json(body)).hexdigest()
    return LegacyResearchLabV0QuarantinePlan(
        db_schema_before=user_version,
        schedule=schedule,
        queued_job_ids=tuple(body["queued_job_ids"]),
        queued_count=body["queued_count"],
        new_count=body["new_count"],
        retry_count=body["retry_count"],
        preserved_terminal_counts=terminal_counts,
        research_job_fingerprints=research_job_fingerprints,
        research_schedule_fingerprints=research_schedule_fingerprints,
        terminal_evidence=terminal_evidence,
        non_target_job_count=body["non_target_job_count"],
        non_target_jobs_sha256=body["non_target_jobs_sha256"],
        non_target_schedule_count=body["non_target_schedule_count"],
        non_target_schedules_sha256=body["non_target_schedules_sha256"],
        blockers=tuple(body["blockers"]),
        plan_sha256=plan_sha256,
    )


def _validate_quarantine_audit_outbox_schema(
    connection: sqlite3.Connection, *, required: bool
) -> None:
    row = connection.execute(
        """SELECT sql FROM sqlite_master
               WHERE type = 'table'
                   AND name = 'legacy_research_lab_v0_quarantine_audit_outbox'"""
    ).fetchone()
    if row is None:
        if required:
            raise LegacyResearchLabV0QuarantineRefusal(
                "jobs schema v4 is missing the quarantine audit outbox"
            )
        return
    if not required:
        raise LegacyResearchLabV0QuarantineRefusal(
            "pre-v4 jobs schema unexpectedly contains the quarantine audit outbox"
        )
    actual = " ".join(str(row["sql"]).split())
    expected = " ".join(LEGACY_RESEARCH_LAB_V0_OUTBOX_SQL.split())
    if actual != expected:
        raise LegacyResearchLabV0QuarantineRefusal(
            "jobs schema v4 quarantine audit outbox definition is not exact"
        )
    _validate_v4_master_schema(connection)


def _master_object_signature(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, str, str, str | None], ...]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    return tuple(
        (
            str(row["type"]),
            str(row["name"]),
            str(row["tbl_name"]),
            None if row["sql"] is None else " ".join(str(row["sql"]).split()),
        )
        for row in rows
    )


@cache
def _expected_v4_master_object_signature() -> tuple[tuple[str, str, str, str | None], ...]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        for migration in _MIGRATIONS:
            for statement in migration:
                connection.execute(statement)
        return _master_object_signature(connection)
    finally:
        connection.close()


def _validate_v4_master_schema(connection: sqlite3.Connection) -> None:
    actual = _master_object_signature(connection)
    expected = _expected_v4_master_object_signature()
    if actual != expected:
        raise LegacyResearchLabV0QuarantineRefusal(
            "jobs schema v4 contains unexpected or modified sqlite_master objects"
        )


def _assert_apply_time_quarantine_state(
    connection: sqlite3.Connection,
    *,
    expected_jobs_sha256: str,
    expected_schedules_sha256: str,
) -> None:
    _validate_quarantine_audit_outbox_schema(connection, required=True)
    active = int(
        connection.execute(
            """SELECT COUNT(*) FROM jobs WHERE job_type = 'RESEARCH_LAB_V0'
                   AND state IN ('QUEUED', 'RUNNING')"""
        ).fetchone()[0]
    )
    target = connection.execute(
        "SELECT enabled FROM schedules WHERE schedule_id = ?",
        (LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,),
    ).fetchone()
    jobs = connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
    schedules = connection.execute("SELECT * FROM schedules ORDER BY schedule_id").fetchall()
    if (
        active != 0
        or target is None
        or bool(target["enabled"])
        or _rows_digest(jobs) != expected_jobs_sha256
        or _rows_digest(schedules) != expected_schedules_sha256
    ):
        raise LegacyResearchLabV0QuarantineRefusal(
            "quarantine operational postconditions no longer match retained audit state"
        )


def _assert_persistent_quarantine_state(
    connection: sqlite3.Connection,
    *,
    expected_research_job_fingerprints: list[dict[str, str]],
    expected_target_schedule_sha256: str,
) -> None:
    _validate_quarantine_audit_outbox_schema(connection, required=True)
    active = int(
        connection.execute(
            """SELECT COUNT(*) FROM jobs WHERE job_type = 'RESEARCH_LAB_V0'
                   AND state IN ('QUEUED', 'RUNNING')"""
        ).fetchone()[0]
    )
    research_jobs = connection.execute(
        "SELECT * FROM jobs WHERE job_type = 'RESEARCH_LAB_V0' ORDER BY job_id"
    ).fetchall()
    research_schedules = connection.execute(
        "SELECT * FROM schedules WHERE job_type = 'RESEARCH_LAB_V0' ORDER BY schedule_id"
    ).fetchall()
    target = next(
        (
            row
            for row in research_schedules
            if row["schedule_id"] == LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID
        ),
        None,
    )
    actual_fingerprints = [
        {"job_id": str(row["job_id"]), "row_sha256": _row_fingerprint(row)} for row in research_jobs
    ]
    if (
        active != 0
        or len(research_schedules) != 1
        or target is None
        or bool(target["enabled"])
        or _row_fingerprint(target) != expected_target_schedule_sha256
        or actual_fingerprints != expected_research_job_fingerprints
    ):
        raise LegacyResearchLabV0QuarantineRefusal(
            "persistent research quarantine state no longer matches retained audit evidence"
        )


def _quarantine_audit_outbox_row(
    connection: sqlite3.Connection,
) -> sqlite3.Row | None:
    exists = connection.execute(
        """SELECT 1 FROM sqlite_master
               WHERE type = 'table'
                   AND name = 'legacy_research_lab_v0_quarantine_audit_outbox'"""
    ).fetchone()
    if exists is None:
        return None
    rows = connection.execute(
        "SELECT * FROM legacy_research_lab_v0_quarantine_audit_outbox"
    ).fetchall()
    if len(rows) > 1:
        raise LegacyResearchLabV0QuarantineRefusal(
            "malformed quarantine audit outbox: multiple operation rows"
        )
    if not rows:
        return None
    row = rows[0]
    payload = bytes(row["payload"])
    digest = hashlib.sha256(payload).hexdigest()
    expected_name = f"{LEGACY_RESEARCH_LAB_V0_AUDIT_PREFIX}{digest}.json"
    expected_temporary = f".{expected_name}.pending"
    if (
        row["operation_key"] != 1
        or row["audit_sha256"] != digest
        or row["artifact_name"] != expected_name
        or row["temporary_name"] != expected_temporary
    ):
        raise LegacyResearchLabV0QuarantineRefusal(
            "malformed quarantine audit outbox: digest or artifact mismatch"
        )
    try:
        decoded = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LegacyResearchLabV0QuarantineRefusal(
            "malformed quarantine audit outbox payload"
        ) from error
    if decoded.get("plan", {}).get("plan_sha256") != row["plan_sha256"]:
        raise LegacyResearchLabV0QuarantineRefusal(
            "malformed quarantine audit outbox: plan digest mismatch"
        )
    return cast(sqlite3.Row, row)


def _quarantine_plan_from_dict(payload: dict[str, Any]) -> LegacyResearchLabV0QuarantinePlan:
    return LegacyResearchLabV0QuarantinePlan(
        db_schema_before=int(payload["db_schema_before"]),
        schedule=payload["schedule"],
        queued_job_ids=tuple(payload["queued_job_ids"]),
        queued_count=int(payload["queued_count"]),
        new_count=int(payload["new_count"]),
        retry_count=int(payload["retry_count"]),
        preserved_terminal_counts=dict(payload["preserved_terminal_counts"]),
        research_job_fingerprints=tuple(payload["research_job_fingerprints"]),
        research_schedule_fingerprints=tuple(payload["research_schedule_fingerprints"]),
        terminal_evidence=tuple(payload["terminal_evidence"]),
        non_target_job_count=int(payload["non_target_job_count"]),
        non_target_jobs_sha256=str(payload["non_target_jobs_sha256"]),
        non_target_schedule_count=int(payload["non_target_schedule_count"]),
        non_target_schedules_sha256=str(payload["non_target_schedules_sha256"]),
        blockers=tuple(payload["blockers"]),
        plan_sha256=str(payload["plan_sha256"]),
    )


class JobStore:
    _locks_guard = threading.Lock()
    _locks: dict[str, threading.RLock] = {}

    def __init__(self, path: Path, *, root: Path | None = None) -> None:
        repo = root or Path(__file__).resolve().parents[4]
        self.root = Path(os.path.realpath(repo))
        self.path = confined_database(path, self.root)
        jobs_root = (self.root / "artifacts/jobs").resolve()
        relative = self.path.relative_to(jobs_root)
        self._parent_parts = relative.parts[:-1]
        self._filename = relative.name
        self._root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._finalizer = weakref.finalize(self, os.close, self._root_fd)
        key = f"{self.root}:{relative}"
        with self._locks_guard:
            self._process_lock = self._locks.setdefault(key, threading.RLock())

    def __enter__(self) -> JobStore:
        if not self._finalizer.alive:
            raise RuntimeError("job store is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._finalizer()

    def _open_parent_anchor(self, *, create: bool) -> tuple[int, int, str]:
        if not self._finalizer.alive:
            raise RuntimeError("job store is closed")
        descriptor = os.dup(self._root_fd)
        components = ("artifacts", "jobs", *self._parent_parts)
        try:
            for index, component in enumerate(components):
                child = _open_directory(descriptor, component, create=create)
                if index == len(components) - 1:
                    return descriptor, child, component
                os.close(descriptor)
                descriptor = child
        except BaseException:
            os.close(descriptor)
            raise
        raise RuntimeError("jobs database has no parent directory")

    def _open_parent(self, *, create: bool) -> int:
        anchor_fd, parent_fd, _ = self._open_parent_anchor(create=create)
        os.close(anchor_fd)
        return parent_fd

    @staticmethod
    def _read_file(parent_fd: int, name: str) -> bytes:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            return b""
        try:
            opened = os.fstat(descriptor)
            _verify_regular_entry(parent_fd, name, descriptor, "jobs database")
            if opened.st_size > MAX_DB_IMAGE_BYTES:
                raise RuntimeError(
                    f"jobs database exceeds {MAX_DB_IMAGE_BYTES} byte capacity limit"
                )
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    def _write_file(self, parent_fd: int, payload: bytes) -> None:
        if len(payload) > MAX_DB_IMAGE_BYTES:
            raise RuntimeError(f"jobs database exceeds {MAX_DB_IMAGE_BYTES} byte capacity limit")
        temporary = f".{self._filename}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        except BaseException:
            os.unlink(temporary, dir_fd=parent_fd)
            raise
        finally:
            os.close(descriptor)
        os.rename(temporary, self._filename, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)

    @staticmethod
    def _entry_size(parent_fd: int, name: str) -> int | None:
        try:
            linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(linked.st_mode):
            raise RuntimeError(f"legacy SQLite sidecar is not a regular file: {name}")
        if linked.st_size > MAX_DB_IMAGE_BYTES:
            raise RuntimeError(f"legacy SQLite sidecar exceeds capacity limit: {name}")
        return linked.st_size

    @staticmethod
    def _write_new_file(parent_fd: int, name: str, payload: bytes) -> None:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
            _verify_regular_entry(parent_fd, name, descriptor, "conversion database")
        finally:
            os.close(descriptor)

    def _convert_clean_wal(self, parent_fd: int, retained: bytes) -> bytes:
        conversion = f".jobs-convert-{uuid.uuid4().hex}"
        os.mkdir(conversion, 0o700, dir_fd=parent_fd)
        conversion_fd = _open_directory(parent_fd, conversion, create=False)
        database_name = "legacy.sqlite3"
        try:
            self._write_new_file(conversion_fd, database_name, retained)
            parent_stat = os.stat(self.path.parent)
            anchored = os.fstat(parent_fd)
            if (parent_stat.st_dev, parent_stat.st_ino) != (anchored.st_dev, anchored.st_ino):
                raise RuntimeError("jobs directory changed during WAL conversion")
            conversion_path = self.path.parent / conversion
            conversion_stat = os.stat(conversion_path, follow_symlinks=False)
            if (conversion_stat.st_dev, conversion_stat.st_ino) != (
                os.fstat(conversion_fd).st_dev,
                os.fstat(conversion_fd).st_ino,
            ):
                raise RuntimeError("WAL conversion directory identity changed")
            connection = sqlite3.connect(conversion_path / database_name, isolation_level=None)
            try:
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
                if str(mode).lower() != "delete":
                    raise RuntimeError("could not convert legacy WAL database to DELETE mode")
            finally:
                connection.close()
            converted = self._read_file(conversion_fd, database_name)
            if len(converted) < 20 or converted[18:20] != b"\x01\x01":
                raise RuntimeError("legacy WAL database conversion did not produce a safe image")
            return converted
        finally:
            for suffix in ("", "-wal", "-shm", "-journal"):
                try:
                    os.unlink(database_name + suffix, dir_fd=conversion_fd)
                except FileNotFoundError:
                    pass
            os.close(conversion_fd)
            os.rmdir(conversion, dir_fd=parent_fd)

    def _assert_legacy_wal_inactive(self, parent_fd: int) -> None:
        wal_size = self._entry_size(parent_fd, self._filename + "-wal")
        shm_size = self._entry_size(parent_fd, self._filename + "-shm")
        if (wal_size or 0) > 0 or shm_size is not None:
            raise RuntimeError(
                "legacy WAL database is active; close all SQLite users and run "
                "PRAGMA wal_checkpoint(TRUNCATE), then retry"
            )

    def _load_database(self, parent_fd: int) -> bytes:
        self._assert_legacy_wal_inactive(parent_fd)
        retained = self._read_file(parent_fd, self._filename)
        self._assert_legacy_wal_inactive(parent_fd)
        if retained and len(retained) >= 20 and retained[18:20] == b"\x02\x02":
            return self._convert_clean_wal(parent_fd, retained)
        return retained

    @contextmanager
    def _connect(self, *, create: bool = False, write: bool = True) -> Iterator[sqlite3.Connection]:
        with self._process_lock:
            anchor_fd, parent_fd, parent_name = self._open_parent_anchor(create=create)
            try:
                fcntl.flock(parent_fd, fcntl.LOCK_EX)
                try:
                    _verify_directory_entry(anchor_fd, parent_name, parent_fd)
                    retained = self._load_database(parent_fd)
                    connection = sqlite3.connect(":memory:", isolation_level=None)
                    connection.row_factory = sqlite3.Row
                    if retained:
                        connection.deserialize(retained)
                    try:
                        yield connection
                    except BaseException:
                        connection.rollback()
                        raise
                    else:
                        if not write:
                            _verify_directory_entry(anchor_fd, parent_name, parent_fd)
                            return
                        payload = connection.serialize()
                        self._assert_legacy_wal_inactive(parent_fd)
                        _verify_directory_entry(anchor_fd, parent_name, parent_fd)
                        self._write_file(parent_fd, payload)
                        _verify_directory_entry(anchor_fd, parent_name, parent_fd)
                        _verify_directory_entry(anchor_fd, parent_name, parent_fd)
                    finally:
                        connection.close()
                finally:
                    fcntl.flock(parent_fd, fcntl.LOCK_UN)
            finally:
                os.close(parent_fd)
                os.close(anchor_fd)

    def initialize(self) -> None:
        with self._connect(create=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("PRAGMA user_version").fetchone()[0]
            if current > SCHEMA_VERSION:
                connection.rollback()
                raise RuntimeError(f"unsupported jobs schema version {current}")
            try:
                for index in range(current, SCHEMA_VERSION):
                    _apply_migration(connection, _MIGRATIONS[index], index + 1)
            except BaseException:
                connection.rollback()
                raise
            connection.commit()
            recorded = connection.execute("SELECT version FROM schema_version").fetchone()[0]
            if recorded != SCHEMA_VERSION:
                raise RuntimeError("jobs schema version mismatch")

    def plan_legacy_research_lab_v0_quarantine(
        self,
    ) -> LegacyResearchLabV0QuarantinePlan:
        """Plan the one supported legacy quarantine without changing database bytes."""
        with self._connect(write=False) as connection:
            return _quarantine_plan(connection)

    def apply_legacy_research_lab_v0_quarantine(
        self,
        *,
        expected_plan_sha256: str,
        expected_job_ids: tuple[str, ...],
    ) -> LegacyResearchLabV0QuarantineResult:
        """Atomically disable and cancel the exact reviewed legacy research workload."""
        if len(expected_plan_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in expected_plan_sha256
        ):
            raise LegacyResearchLabV0QuarantineRefusal(
                "expected_plan_sha256 must be one lowercase SHA-256 digest"
            )
        if expected_job_ids != tuple(sorted(set(expected_job_ids))):
            raise LegacyResearchLabV0QuarantineRefusal(
                "expected_job_ids must be unique and sorted exactly as the plan"
            )

        preliminary = self.plan_legacy_research_lab_v0_quarantine()
        if preliminary.blockers:
            raise LegacyResearchLabV0QuarantineRefusal(
                "quarantine plan has blockers: " + "; ".join(preliminary.blockers)
            )
        if preliminary.plan_sha256 != expected_plan_sha256:
            raise LegacyResearchLabV0QuarantineRefusal(
                "plan digest changed; refusing stale quarantine apply"
            )
        if preliminary.queued_job_ids != expected_job_ids:
            raise LegacyResearchLabV0QuarantineRefusal(
                "queued job IDs changed; refusing stale quarantine apply"
            )
        if (
            preliminary.schedule is not None
            and not preliminary.schedule["enabled"]
            and not preliminary.queued_job_ids
        ):
            outbox = self._read_quarantine_audit_outbox()
            if outbox is not None:
                repaired = self.repair_legacy_research_lab_v0_quarantine_audit(
                    expected_audit_sha256=str(outbox["audit_sha256"]),
                    expected_plan_sha256=str(outbox["plan_sha256"]),
                )
                return LegacyResearchLabV0QuarantineResult(
                    status="ALREADY_QUARANTINED",
                    plan=repaired.plan,
                    cancelled_job_ids=repaired.cancelled_job_ids,
                    applied_at=repaired.applied_at,
                    audit_artifact_ref=repaired.audit_artifact_ref,
                    audit_sha256=repaired.audit_sha256,
                    audit_publication_state="PUBLISHED",
                )
            return LegacyResearchLabV0QuarantineResult(
                status="ALREADY_QUARANTINED",
                plan=preliminary,
                cancelled_job_ids=(),
                applied_at=None,
                audit_artifact_ref=None,
                audit_sha256=None,
                audit_publication_state="NOT_APPLICABLE",
            )

        applied_at = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            plan = _quarantine_plan(connection)
            if plan.blockers:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "quarantine plan has blockers: " + "; ".join(plan.blockers)
                )
            if plan.plan_sha256 != expected_plan_sha256:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "plan digest changed; refusing stale quarantine apply"
                )
            if plan.queued_job_ids != expected_job_ids:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "queued job IDs changed; refusing stale quarantine apply"
                )
            if plan.schedule is None:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal("fixed schedule was not found")
            if not plan.schedule["enabled"] and not plan.queued_job_ids:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "quarantine state changed after planning; re-plan before retrying"
                )

            job_columns = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            )
            schedule_columns_before = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(schedules)").fetchall()
            )
            jobs_before = {
                row["job_id"]: tuple(row[column] for column in job_columns)
                for row in connection.execute("SELECT * FROM jobs").fetchall()
            }
            schedules_before = {
                row["schedule_id"]: tuple(row[column] for column in schedule_columns_before)
                for row in connection.execute("SELECT * FROM schedules").fetchall()
            }
            for migration_index in range(plan.db_schema_before, SCHEMA_VERSION):
                _apply_migration(
                    connection,
                    _MIGRATIONS[migration_index],
                    migration_index + 1,
                )
            _validate_quarantine_audit_outbox_schema(connection, required=True)

            connection.execute(
                "UPDATE schedules SET enabled = 0 WHERE schedule_id = ?",
                (LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,),
            )
            if plan.queued_job_ids:
                placeholders = ",".join("?" for _ in plan.queued_job_ids)
                cursor = connection.execute(
                    f"""UPDATE jobs SET state = 'CANCELLED', cancel_requested = 1,
                               finished_at = ?, lease_owner = NULL, lease_expires_at = NULL,
                               error = CASE
                                   WHEN attempt_count > 0 AND error IS NOT NULL AND error != ''
                                   THEN error || '\n' || ? ELSE ? END
                           WHERE job_type = 'RESEARCH_LAB_V0' AND state = 'QUEUED'
                               AND job_id IN ({placeholders})""",
                    (
                        _stamp(applied_at),
                        LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON,
                        LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON,
                        *plan.queued_job_ids,
                    ),
                )
                if cursor.rowcount != len(plan.queued_job_ids):
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        "cancelled row count did not match the approved plan"
                    )

            active = connection.execute(
                """SELECT COUNT(*) FROM jobs WHERE job_type = 'RESEARCH_LAB_V0'
                       AND state IN ('QUEUED', 'RUNNING')"""
            ).fetchone()[0]
            target_enabled = connection.execute(
                "SELECT enabled FROM schedules WHERE schedule_id = ?",
                (LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,),
            ).fetchone()
            if active != 0 or target_enabled is None or bool(target_enabled[0]):
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "quarantine postconditions were not satisfied"
                )

            jobs_after_rows = connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
            jobs_after = {
                row["job_id"]: tuple(row[column] for column in job_columns)
                for row in jobs_after_rows
            }
            if jobs_before.keys() != jobs_after.keys():
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "job identity set changed during quarantine"
                )
            cancelled_ids = set(plan.queued_job_ids)
            for job_id, before in jobs_before.items():
                if job_id not in cancelled_ids and jobs_after[job_id] != before:
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        f"unapproved job row changed during quarantine: {job_id}"
                    )
            for row in jobs_after_rows:
                if row["job_id"] not in cancelled_ids:
                    continue
                before_row = dict(zip(job_columns, jobs_before[row["job_id"]], strict=True))
                allowed = {
                    "state",
                    "cancel_requested",
                    "finished_at",
                    "lease_owner",
                    "lease_expires_at",
                    "error",
                }
                for column in job_columns:
                    if column not in allowed and row[column] != before_row[column]:
                        connection.rollback()
                        raise LegacyResearchLabV0QuarantineRefusal(
                            f"quarantine changed protected job field {column}"
                        )
                if (
                    row["state"] != JobState.CANCELLED
                    or not bool(row["cancel_requested"])
                    or row["finished_at"] != _stamp(applied_at)
                    or row["lease_owner"] is not None
                    or row["lease_expires_at"] is not None
                ):
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        f"cancelled job postcondition failed: {row['job_id']}"
                    )
                old_error = before_row["error"]
                expected_error = (
                    f"{old_error}\n{LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON}"
                    if int(before_row["attempt_count"]) > 0 and old_error
                    else LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON
                )
                if row["error"] != expected_error:
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        f"cancelled job reason postcondition failed: {row['job_id']}"
                    )

            schedule_columns_after = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(schedules)").fetchall()
            )
            schedules_after_rows = connection.execute(
                "SELECT * FROM schedules ORDER BY schedule_id"
            ).fetchall()
            schedules_after = {row["schedule_id"]: dict(row) for row in schedules_after_rows}
            if schedules_before.keys() != schedules_after.keys():
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "schedule identity set changed during quarantine"
                )
            for schedule_id, before_values in schedules_before.items():
                before_schedule = dict(zip(schedule_columns_before, before_values, strict=True))
                after = schedules_after[schedule_id]
                for column in schedule_columns_before:
                    if schedule_id == LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID and column == "enabled":
                        continue
                    if after[column] != before_schedule[column]:
                        connection.rollback()
                        raise LegacyResearchLabV0QuarantineRefusal(
                            f"unapproved schedule field changed: {schedule_id}.{column}"
                        )
                if schedule_id != LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID:
                    expected_enabled = before_schedule.get("enabled", 1)
                    if after["enabled"] != expected_enabled:
                        connection.rollback()
                        raise LegacyResearchLabV0QuarantineRefusal(
                            f"unapproved schedule changed during quarantine: {schedule_id}"
                        )
            if "enabled" not in schedule_columns_after:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal("v3 migration postcondition failed")
            post_jobs_sha256 = _rows_digest(jobs_after_rows)
            post_schedules_sha256 = _rows_digest(schedules_after_rows)
            post_research_job_fingerprints = [
                {"job_id": str(row["job_id"]), "row_sha256": _row_fingerprint(row)}
                for row in jobs_after_rows
                if row["job_type"] == JobType.RESEARCH_LAB_V0
            ]
            post_target_schedule = next(
                row
                for row in schedules_after_rows
                if row["schedule_id"] == LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID
            )
            audit_body: dict[str, Any] = {
                "schema_version": 2,
                "operation": "LEGACY_RESEARCH_LAB_V0_QUARANTINE",
                "status": "APPLIED",
                "database_ref": str(self.path.relative_to(self.root)),
                "applied_at": _stamp(applied_at),
                "db_schema_after": SCHEMA_VERSION,
                "plan": plan.as_dict(),
                "cancelled_job_ids": list(plan.queued_job_ids),
                "post_quarantine_jobs_sha256": post_jobs_sha256,
                "post_quarantine_schedules_sha256": post_schedules_sha256,
                "post_quarantine_research_job_fingerprints": (post_research_job_fingerprints),
                "post_quarantine_target_schedule_sha256": _row_fingerprint(post_target_schedule),
            }
            audit_payload = _canonical_json(audit_body) + b"\n"
            audit_sha256 = hashlib.sha256(audit_payload).hexdigest()
            artifact_name = f"{LEGACY_RESEARCH_LAB_V0_AUDIT_PREFIX}{audit_sha256}.json"
            temporary_name = f".{artifact_name}.pending"
            if _quarantine_audit_outbox_row(connection) is not None:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "quarantine audit outbox already exists before first apply"
                )
            connection.execute(
                """INSERT INTO legacy_research_lab_v0_quarantine_audit_outbox (
                       operation_key, audit_sha256, plan_sha256, artifact_name,
                       temporary_name, payload, applied_at, published_at
                   ) VALUES (1, ?, ?, ?, ?, ?, ?, NULL)""",
                (
                    audit_sha256,
                    plan.plan_sha256,
                    artifact_name,
                    temporary_name,
                    audit_payload,
                    _stamp(applied_at),
                ),
            )
            retained = _quarantine_audit_outbox_row(connection)
            if retained is None or bytes(retained["payload"]) != audit_payload:
                connection.rollback()
                raise LegacyResearchLabV0QuarantineRefusal(
                    "quarantine audit outbox retention postcondition failed"
                )
            _assert_apply_time_quarantine_state(
                connection,
                expected_jobs_sha256=post_jobs_sha256,
                expected_schedules_sha256=post_schedules_sha256,
            )
            connection.commit()

        pending_result = LegacyResearchLabV0QuarantineResult(
            status="APPLIED",
            plan=plan,
            cancelled_job_ids=plan.queued_job_ids,
            applied_at=applied_at,
            audit_artifact_ref=f"artifacts/jobs/quarantine/{artifact_name}",
            audit_sha256=audit_sha256,
            audit_publication_state="PENDING",
        )
        try:
            published = self.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=audit_sha256,
                expected_plan_sha256=plan.plan_sha256,
            )
        except Exception as error:
            raise LegacyResearchLabV0AuditPublicationError(
                "database commit succeeded and retained the quarantine audit outbox, but "
                "artifact publication failed; run the fixed repair-audit command",
                result=pending_result,
                audit_payload=audit_payload,
                audit_artifact_ref=pending_result.audit_artifact_ref or "",
            ) from error
        return LegacyResearchLabV0QuarantineResult(
            status="APPLIED",
            plan=published.plan,
            cancelled_job_ids=published.cancelled_job_ids,
            applied_at=published.applied_at,
            audit_artifact_ref=published.audit_artifact_ref,
            audit_sha256=published.audit_sha256,
            audit_publication_state="PUBLISHED",
        )

    def _read_quarantine_audit_outbox(self) -> dict[str, Any] | None:
        with self._connect(write=False) as connection:
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            recorded = int(connection.execute("SELECT version FROM schema_version").fetchone()[0])
            if user_version != recorded or user_version not in {2, 3, 4}:
                raise LegacyResearchLabV0QuarantineRefusal(
                    "jobs schema version is not valid for quarantine audit repair"
                )
            _validate_quarantine_audit_outbox_schema(connection, required=user_version == 4)
            row = _quarantine_audit_outbox_row(connection)
            if row is None:
                return None
            result = dict(row)
            result["payload"] = bytes(result["payload"])
            return result

    def repair_legacy_research_lab_v0_quarantine_audit(
        self,
        *,
        expected_audit_sha256: str,
        expected_plan_sha256: str,
    ) -> LegacyResearchLabV0QuarantineResult:
        """Publish one exact durable outbox row and mark it published."""
        for label, digest in (
            ("expected_audit_sha256", expected_audit_sha256),
            ("expected_plan_sha256", expected_plan_sha256),
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise LegacyResearchLabV0QuarantineRefusal(
                    f"{label} must be one lowercase SHA-256 digest"
                )
        outbox = self._read_quarantine_audit_outbox()
        if outbox is None:
            raise LegacyResearchLabV0QuarantineRefusal("no durable quarantine audit outbox exists")
        if outbox["audit_sha256"] != expected_audit_sha256:
            raise LegacyResearchLabV0QuarantineRefusal(
                "audit digest changed; refusing stale audit repair"
            )
        if outbox["plan_sha256"] != expected_plan_sha256:
            raise LegacyResearchLabV0QuarantineRefusal(
                "audit plan digest changed; refusing stale audit repair"
            )
        payload = bytes(outbox["payload"])
        decoded = json.loads(payload)
        plan = _quarantine_plan_from_dict(decoded["plan"])
        artifact_name = str(outbox["artifact_name"])
        temporary_name = str(outbox["temporary_name"])
        self._publish_legacy_quarantine_audit(artifact_name, temporary_name, payload)
        was_pending = outbox["published_at"] is None
        expected_research_fingerprints = list(decoded["post_quarantine_research_job_fingerprints"])
        expected_target_schedule_sha256 = str(decoded["post_quarantine_target_schedule_sha256"])
        if was_pending:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                _assert_persistent_quarantine_state(
                    connection,
                    expected_research_job_fingerprints=expected_research_fingerprints,
                    expected_target_schedule_sha256=expected_target_schedule_sha256,
                )
                current_jobs_sha256 = _rows_digest(
                    connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
                )
                current_schedules_sha256 = _rows_digest(
                    connection.execute("SELECT * FROM schedules ORDER BY schedule_id").fetchall()
                )
                retained = _quarantine_audit_outbox_row(connection)
                if (
                    retained is None
                    or retained["audit_sha256"] != expected_audit_sha256
                    or retained["plan_sha256"] != expected_plan_sha256
                    or bytes(retained["payload"]) != payload
                ):
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        "audit outbox changed before publication acknowledgement"
                    )
                connection.execute(
                    """UPDATE legacy_research_lab_v0_quarantine_audit_outbox
                           SET published_at = COALESCE(published_at, ?)
                           WHERE operation_key = 1""",
                    (_stamp(utc_now()),),
                )
                current_jobs_after_sha256 = _rows_digest(
                    connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
                )
                current_schedules_after_sha256 = _rows_digest(
                    connection.execute("SELECT * FROM schedules ORDER BY schedule_id").fetchall()
                )
                if (
                    current_jobs_after_sha256 != current_jobs_sha256
                    or current_schedules_after_sha256 != current_schedules_sha256
                ):
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        "publication acknowledgement caused an operational table mutation"
                    )
                _assert_persistent_quarantine_state(
                    connection,
                    expected_research_job_fingerprints=expected_research_fingerprints,
                    expected_target_schedule_sha256=expected_target_schedule_sha256,
                )
                acknowledged = _quarantine_audit_outbox_row(connection)
                if (
                    acknowledged is None
                    or bytes(acknowledged["payload"]) != payload
                    or acknowledged["published_at"] is None
                ):
                    connection.rollback()
                    raise LegacyResearchLabV0QuarantineRefusal(
                        "audit publication acknowledgement postcondition failed"
                    )
                connection.commit()
        with self._connect(write=False) as connection:
            _assert_persistent_quarantine_state(
                connection,
                expected_research_job_fingerprints=expected_research_fingerprints,
                expected_target_schedule_sha256=expected_target_schedule_sha256,
            )
        return LegacyResearchLabV0QuarantineResult(
            status="AUDIT_REPAIRED" if was_pending else "AUDIT_VERIFIED",
            plan=plan,
            cancelled_job_ids=tuple(decoded["cancelled_job_ids"]),
            applied_at=datetime.fromisoformat(str(outbox["applied_at"])),
            audit_artifact_ref=f"artifacts/jobs/quarantine/{artifact_name}",
            audit_sha256=expected_audit_sha256,
            audit_publication_state="PUBLISHED",
        )

    def _open_quarantine_audit_chain(self) -> tuple[tuple[int, ...], tuple[str, ...]]:
        descriptors = [os.dup(self._root_fd)]
        names = ("artifacts", "jobs", "quarantine")
        try:
            for name in names:
                descriptors.append(_open_directory(descriptors[-1], name, create=True))
            self._verify_quarantine_audit_chain(tuple(descriptors), names)
            return tuple(descriptors), names
        except BaseException:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            raise

    def _verify_quarantine_audit_chain(
        self, descriptors: tuple[int, ...], names: tuple[str, ...]
    ) -> None:
        root_opened = os.fstat(descriptors[0])
        root_linked = os.stat(self.root, follow_symlinks=False)
        if not stat.S_ISDIR(root_linked.st_mode) or (
            root_opened.st_dev,
            root_opened.st_ino,
        ) != (root_linked.st_dev, root_linked.st_ino):
            raise RuntimeError("repository root identity changed during audit publication")
        for parent_fd, child_fd, name in zip(descriptors[:-1], descriptors[1:], names, strict=True):
            opened = os.fstat(child_fd)
            linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(linked.st_mode) or (opened.st_dev, opened.st_ino) != (
                linked.st_dev,
                linked.st_ino,
            ):
                raise RuntimeError(f"audit directory identity changed during publication: {name}")

    @staticmethod
    def _verify_existing_quarantine_audit(
        directory_fd: int,
        name: str,
        payload: bytes,
        *,
        expected_nlink: int,
    ) -> os.stat_result:
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(linked.st_mode) or linked.st_nlink != expected_nlink:
            raise RuntimeError("existing quarantine audit is a symlink or hardlink")
        if linked.st_size != len(payload):
            raise RuntimeError("quarantine audit content-address collision")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
                raise RuntimeError("quarantine audit identity changed while opening")
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            if b"".join(chunks) != payload:
                raise RuntimeError("quarantine audit content-address collision")
            linked_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (linked_after.st_dev, linked_after.st_ino, linked_after.st_nlink) != (
                opened.st_dev,
                opened.st_ino,
                expected_nlink,
            ):
                raise RuntimeError("quarantine audit identity changed while reading")
        finally:
            os.close(descriptor)
        return linked

    def _recover_quarantine_audit_link_state(
        self,
        directory_fd: int,
        artifact_name: str,
        temporary_name: str,
        payload: bytes,
    ) -> bool:
        try:
            os.stat(artifact_name, dir_fd=directory_fd, follow_symlinks=False)
            final_exists = True
        except FileNotFoundError:
            final_exists = False
        try:
            os.stat(temporary_name, dir_fd=directory_fd, follow_symlinks=False)
            temporary_exists = True
        except FileNotFoundError:
            temporary_exists = False
        if final_exists and temporary_exists:
            final = self._verify_existing_quarantine_audit(
                directory_fd, artifact_name, payload, expected_nlink=2
            )
            temporary = self._verify_existing_quarantine_audit(
                directory_fd, temporary_name, payload, expected_nlink=2
            )
            if (final.st_dev, final.st_ino) != (temporary.st_dev, temporary.st_ino):
                raise RuntimeError("quarantine audit final and retained temp identities differ")
            os.unlink(temporary_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
            self._verify_existing_quarantine_audit(
                directory_fd, artifact_name, payload, expected_nlink=1
            )
            return True
        if final_exists:
            self._verify_existing_quarantine_audit(
                directory_fd, artifact_name, payload, expected_nlink=1
            )
            return True
        if temporary_exists:
            self._verify_existing_quarantine_audit(
                directory_fd, temporary_name, payload, expected_nlink=1
            )
        return False

    def _publish_legacy_quarantine_audit(
        self, artifact_name: str, temporary_name: str, payload: bytes
    ) -> None:
        digest = hashlib.sha256(payload).hexdigest()
        if artifact_name != f"{LEGACY_RESEARCH_LAB_V0_AUDIT_PREFIX}{digest}.json":
            raise ValueError("quarantine audit name is not canonical")
        if temporary_name != f".{artifact_name}.pending":
            raise ValueError("quarantine audit temporary name is not canonical")
        descriptors, names = self._open_quarantine_audit_chain()
        directory_fd = descriptors[-1]
        created_temporary = False
        created_inode: tuple[int, int] | None = None
        linked_by_call = False
        try:
            self._verify_quarantine_audit_chain(descriptors, names)
            if self._recover_quarantine_audit_link_state(
                directory_fd, artifact_name, temporary_name, payload
            ):
                self._verify_quarantine_audit_chain(descriptors, names)
                return
            try:
                os.stat(temporary_name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory_fd,
                )
                created_temporary = True
                try:
                    view = memoryview(payload)
                    while view:
                        written = os.write(descriptor, view)
                        if written <= 0:
                            raise RuntimeError("quarantine audit write made no progress")
                        view = view[written:]
                    os.fsync(descriptor)
                    temporary_stat = os.fstat(descriptor)
                    if not stat.S_ISREG(temporary_stat.st_mode) or temporary_stat.st_nlink != 1:
                        raise RuntimeError("quarantine audit temporary file is unsafe")
                    created_inode = (temporary_stat.st_dev, temporary_stat.st_ino)
                finally:
                    os.close(descriptor)
                os.fsync(directory_fd)
            self._verify_quarantine_audit_chain(descriptors, names)
            os.link(
                temporary_name,
                artifact_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
            linked_by_call = True
            if not self._recover_quarantine_audit_link_state(
                directory_fd, artifact_name, temporary_name, payload
            ):
                raise RuntimeError("quarantine audit link-window recovery failed")
            self._verify_quarantine_audit_chain(descriptors, names)
        except BaseException:
            if created_temporary:
                try:
                    linked = os.stat(temporary_name, dir_fd=directory_fd, follow_symlinks=False)
                    if linked.st_nlink == 1:
                        os.unlink(temporary_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
            if linked_by_call and created_inode is not None:
                try:
                    linked = os.stat(artifact_name, dir_fd=directory_fd, follow_symlinks=False)
                    if (
                        linked.st_dev,
                        linked.st_ino,
                        linked.st_nlink,
                    ) == (*created_inode, 1):
                        os.unlink(artifact_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
            os.fsync(directory_fd)
            raise
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def enqueue(
        self,
        job_type: JobType,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
        *,
        due_at: datetime | None = None,
        max_attempts: int = 1,
        timeout_seconds: int = 3600,
    ) -> Job:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")
        created = utc_now()
        values = (
            _identity(idempotency_key),
            idempotency_key,
            JobType(job_type).value,
            JobState.QUEUED.value,
            json.dumps(payload or {}, sort_keys=True, separators=(",", ":")),
            max_attempts,
            timeout_seconds,
            _stamp(created),
            _stamp(due_at or created),
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO jobs (
                       job_id, idempotency_key, job_type, state, payload_json,
                       max_attempts, timeout_seconds, created_at, due_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            row = connection.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        if row is None:
            raise RuntimeError("job enqueue failed")
        return _job(row)

    def get(self, job_id: str) -> Job | None:
        with self._connect(write=False) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _job(row) if row else None

    def list(self, *, limit: int = 100) -> list[Job]:
        if not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIST_LIMIT}")
        with self._connect(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_job(row) for row in rows]

    def claim(
        self,
        owner: str,
        *,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> Job | None:
        if not owner.strip() or lease_seconds < 1:
            raise ValueError("owner and a positive lease are required")
        claimed_at = now or utc_now()
        stamp = _stamp(claimed_at)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE jobs SET state = 'CANCELLED', finished_at = ?, lease_owner = NULL,
                       lease_expires_at = NULL, error = 'cancelled after worker lease expired'
                   WHERE state = 'RUNNING' AND cancel_requested = 1 AND lease_expires_at <= ?""",
                (stamp, stamp),
            )
            connection.execute(
                """UPDATE jobs SET state = 'FAILED', finished_at = ?, lease_owner = NULL,
                       lease_expires_at = NULL, error = 'worker lease expired after final attempt'
                   WHERE state = 'RUNNING' AND lease_expires_at <= ?
                       AND attempt_count >= max_attempts AND cancel_requested = 0""",
                (stamp, stamp),
            )
            row = connection.execute(
                """SELECT job_id, state, timeout_seconds FROM jobs
                   WHERE attempt_count < max_attempts AND cancel_requested = 0 AND (
                       (state = 'QUEUED' AND due_at <= ?)
                       OR (state = 'RUNNING' AND lease_expires_at <= ?)
                   )
                   ORDER BY due_at, created_at, job_id LIMIT 1""",
                (stamp, stamp),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            bounded_lease = _lease_duration(lease_seconds)
            lease_expires = claimed_at + timedelta(seconds=bounded_lease)
            recovered_error = (
                "worker lease expired; recovered" if row["state"] == "RUNNING" else None
            )
            connection.execute(
                """UPDATE jobs SET state = 'RUNNING', attempt_count = attempt_count + 1,
                       started_at = ?, finished_at = NULL, lease_owner = ?, lease_expires_at = ?,
                       error = COALESCE(?, error)
                   WHERE job_id = ?""",
                (stamp, owner, _stamp(lease_expires), recovered_error, row["job_id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
            connection.commit()
        return _job(claimed)

    def renew_lease(
        self,
        job_id: str,
        owner: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> Job:
        renewed_at = now or utc_now()
        expires = renewed_at + timedelta(seconds=_lease_duration(lease_seconds))
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET lease_expires_at = ?
                   WHERE job_id = ? AND state = 'RUNNING' AND lease_owner = ?""",
                (_stamp(expires), job_id, owner),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if cursor.rowcount != 1 or row is None:
            raise RuntimeError("job lease ownership was lost")
        return _job(row)

    def succeed(
        self,
        job_id: str,
        owner: str,
        *,
        artifact_ref: str | None,
        digest: str | None,
        reused: bool | None,
        now: datetime | None = None,
    ) -> Job:
        return self._finish(
            job_id,
            owner,
            JobState.SUCCEEDED,
            now or utc_now(),
            artifact_ref=artifact_ref,
            digest=digest,
            reused=reused,
        )

    def fail(
        self,
        job_id: str,
        owner: str,
        error: str,
        *,
        now: datetime | None = None,
        backoff_seconds: int = 30,
    ) -> Job:
        failed_at = now or utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ? AND state = 'RUNNING' AND lease_owner = ?",
                (job_id, owner),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise RuntimeError("job is not owned by this worker")
            cancelled = bool(row["cancel_requested"])
            retry = not cancelled and row["attempt_count"] < row["max_attempts"]
            state = (
                JobState.CANCELLED if cancelled else (JobState.QUEUED if retry else JobState.FAILED)
            )
            due = failed_at + timedelta(seconds=max(1, backoff_seconds) * row["attempt_count"])
            connection.execute(
                """UPDATE jobs SET state = ?, due_at = ?, finished_at = ?, lease_owner = NULL,
                       lease_expires_at = NULL, error = ? WHERE job_id = ?""",
                (
                    state.value,
                    _stamp(due),
                    None if retry else _stamp(failed_at),
                    ("cancelled by operator" if cancelled else error)[:8000],
                    job_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            connection.commit()
        return _job(updated)

    def cancel(self, job_id: str, *, now: datetime | None = None) -> Job:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET
                       state = CASE WHEN state = 'QUEUED' THEN 'CANCELLED' ELSE state END,
                       finished_at = CASE WHEN state = 'QUEUED' THEN ? ELSE finished_at END,
                       lease_owner = CASE WHEN state = 'QUEUED' THEN NULL ELSE lease_owner END,
                       lease_expires_at = CASE
                           WHEN state = 'QUEUED' THEN NULL ELSE lease_expires_at END,
                       cancel_requested = 1,
                       error = CASE
                           WHEN state = 'QUEUED' THEN 'cancelled by operator' ELSE error END
                   WHERE job_id = ? AND state IN ('QUEUED', 'RUNNING')""",
                (_stamp(now or utc_now()), job_id),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        if cursor.rowcount != 1 and row["state"] != JobState.CANCELLED:
            raise RuntimeError("only active jobs can be cancelled")
        return _job(row)

    def is_cancel_requested(self, job_id: str, owner: str) -> bool:
        with self._connect(write=False) as connection:
            row = connection.execute(
                """SELECT cancel_requested FROM jobs
                   WHERE job_id = ? AND state = 'RUNNING' AND lease_owner = ?""",
                (job_id, owner),
            ).fetchone()
        return bool(row and row["cancel_requested"])

    def finish_cancelled(
        self, job_id: str, owner: str, error: str = "cancelled by operator"
    ) -> Job:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET state = 'CANCELLED', cancel_requested = 1,
                       finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error = ?
                   WHERE job_id = ? AND state = 'RUNNING' AND lease_owner = ?""",
                (_stamp(utc_now()), error[:8000], job_id, owner),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if cursor.rowcount != 1 or row is None:
            raise RuntimeError("job is not owned by this worker")
        return _job(row)

    def add_schedule(
        self,
        schedule_id: str,
        job_type: JobType,
        interval_seconds: int,
        next_due: datetime,
        payload: dict[str, Any] | None = None,
        *,
        max_attempts: int = 1,
        timeout_seconds: int = 3600,
    ) -> Schedule:
        if not schedule_id.strip():
            raise ValueError("schedule_id must not be empty")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO schedules (
                       schedule_id, job_type, payload_json, interval_seconds, next_due,
                       max_attempts, timeout_seconds
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(schedule_id) DO NOTHING""",
                (
                    schedule_id,
                    JobType(job_type).value,
                    json.dumps(payload or {}, sort_keys=True, separators=(",", ":")),
                    interval_seconds,
                    _stamp(next_due),
                    max_attempts,
                    timeout_seconds,
                ),
            )
            row = connection.execute(
                "SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("schedule creation failed")
        return _schedule(row)

    def materialize_due(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> builtins.list[Job]:
        if limit < 1:
            raise ValueError("limit must be positive")
        cutoff = now or utc_now()
        made: builtins.list[Job] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM schedules WHERE enabled = 1 AND next_due <= ? ORDER BY next_due",
                (_stamp(cutoff),),
            ).fetchall()
            for row in rows:
                due = datetime.fromisoformat(row["next_due"])
                while due <= cutoff and len(made) < limit:
                    key = f"schedule:{row['schedule_id']}:{_stamp(due)}"
                    values = (
                        _identity(key),
                        key,
                        row["job_type"],
                        JobState.QUEUED.value,
                        row["payload_json"],
                        row["max_attempts"],
                        row["timeout_seconds"],
                        _stamp(cutoff),
                        _stamp(due),
                    )
                    connection.execute(
                        """INSERT OR IGNORE INTO jobs (
                               job_id, idempotency_key, job_type, state, payload_json,
                               max_attempts, timeout_seconds, created_at, due_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        values,
                    )
                    job_row = connection.execute(
                        "SELECT * FROM jobs WHERE idempotency_key = ?", (key,)
                    ).fetchone()
                    made.append(_job(job_row))
                    due += timedelta(seconds=row["interval_seconds"])
                connection.execute(
                    "UPDATE schedules SET next_due = ? WHERE schedule_id = ?",
                    (_stamp(due), row["schedule_id"]),
                )
                if len(made) >= limit:
                    break
            connection.commit()
        return made

    def set_schedule_enabled(
        self, schedule_id: str, enabled: bool, *, now: datetime | None = None
    ) -> Schedule:
        """Pause future occurrences; resume at the first future slot without backfill."""
        if not schedule_id.strip() or not isinstance(enabled, bool):
            raise ValueError("a schedule_id and boolean enabled state are required")
        with self._connect() as connection:
            current = connection.execute(
                "SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            if current is None:
                raise KeyError(schedule_id)
            next_due = datetime.fromisoformat(current["next_due"])
            if enabled:
                resumed_at = now or utc_now()
                if next_due <= resumed_at:
                    interval = int(current["interval_seconds"])
                    steps = int((resumed_at - next_due).total_seconds() // interval) + 1
                    next_due += timedelta(seconds=steps * interval)
            cursor = connection.execute(
                "UPDATE schedules SET enabled = ?, next_due = ? WHERE schedule_id = ?",
                (int(enabled), _stamp(next_due), schedule_id),
            )
            row = connection.execute(
                "SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
        if row is None or cursor.rowcount != 1:
            raise KeyError(schedule_id)
        return _schedule(row)

    def _finish(
        self,
        job_id: str,
        owner: str,
        state: JobState,
        now: datetime,
        *,
        artifact_ref: str | None,
        digest: str | None,
        reused: bool | None,
    ) -> Job:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET
                       state = CASE WHEN cancel_requested = 1 THEN 'CANCELLED' ELSE ? END,
                       finished_at = ?, lease_owner = NULL, lease_expires_at = NULL,
                       result_artifact_ref = CASE
                           WHEN cancel_requested = 1 THEN NULL ELSE ? END,
                       result_digest = CASE WHEN cancel_requested = 1 THEN NULL ELSE ? END,
                       result_reused = CASE WHEN cancel_requested = 1 THEN NULL ELSE ? END,
                       error = CASE
                           WHEN cancel_requested = 1 THEN 'cancelled by operator' ELSE NULL END
                   WHERE job_id = ? AND state = 'RUNNING' AND lease_owner = ?""",
                (
                    state.value,
                    _stamp(now),
                    artifact_ref,
                    digest,
                    None if reused is None else int(reused),
                    job_id,
                    owner,
                ),
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if cursor.rowcount != 1 or row is None:
            raise RuntimeError("job is not owned by this worker")
        return _job(row)


def _job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=row["job_id"],
        idempotency_key=row["idempotency_key"],
        job_type=JobType(row["job_type"]),
        state=JobState(row["state"]),
        payload=json.loads(row["payload_json"]),
        attempt_count=row["attempt_count"],
        max_attempts=row["max_attempts"],
        timeout_seconds=row["timeout_seconds"],
        created_at=datetime.fromisoformat(row["created_at"]),
        due_at=datetime.fromisoformat(row["due_at"]),
        started_at=_parse(row["started_at"]),
        finished_at=_parse(row["finished_at"]),
        lease_owner=row["lease_owner"],
        lease_expires_at=_parse(row["lease_expires_at"]),
        result_artifact_ref=row["result_artifact_ref"],
        result_digest=row["result_digest"],
        result_reused=None if row["result_reused"] is None else bool(row["result_reused"]),
        cancel_requested=bool(row["cancel_requested"]),
        error=row["error"],
    )


def _schedule(row: sqlite3.Row) -> Schedule:
    return Schedule(
        schedule_id=row["schedule_id"],
        job_type=JobType(row["job_type"]),
        payload=json.loads(row["payload_json"]),
        interval_seconds=row["interval_seconds"],
        next_due=datetime.fromisoformat(row["next_due"]),
        max_attempts=row["max_attempts"],
        timeout_seconds=row["timeout_seconds"],
        enabled=bool(row["enabled"]),
    )
