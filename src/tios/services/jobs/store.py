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
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
MAX_LIST_LIMIT = 1000
MAX_DB_IMAGE_BYTES = 64 * 1024 * 1024


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
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
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
                "SELECT * FROM schedules WHERE next_due <= ? ORDER BY next_due",
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
    )
