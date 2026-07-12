"""Durable append-only local store for inert S3/S4 evidence records."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from tios.trading_domain import Stage

SCHEMA_VERSION = 1
MAX_QUERY_LIMIT = 1000


class SyntheticEvidenceStoreError(ValueError):
    """Evidence cannot be stored or verified without violating an invariant."""


@dataclass(frozen=True, slots=True)
class StoredSyntheticEvidence:
    sequence: int
    idempotency_key: str
    record_id: str
    record_type: str
    stage: Stage
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]
    payload_sha256: str


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise SyntheticEvidenceStoreError("evidence timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise SyntheticEvidenceStoreError(f"unsupported evidence value: {type(value).__name__}")


def _canonical(value: object) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))


def _utc(value: datetime, name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SyntheticEvidenceStoreError(f"{name} must be timezone-aware")
    return value.astimezone(UTC).isoformat()


class SyntheticEvidenceStore:
    """One-table SQLite evidence ledger with no update/delete API."""

    def __init__(self, path: Path, *, root: Path) -> None:
        self.root = root.resolve()
        allowed = (self.root / "artifacts/evidence").resolve()
        candidate = path if path.is_absolute() else self.root / path
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(allowed) or resolved == allowed:
            raise SyntheticEvidenceStoreError(
                "synthetic evidence database must remain in artifacts/evidence"
            )
        if candidate.is_symlink():
            raise SyntheticEvidenceStoreError("synthetic evidence database cannot be a symlink")
        self.path = resolved
        self.lock_path = resolved.with_suffix(resolved.suffix + ".lock")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        with self._lock(), self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL CHECK (version = 1)
                );
                INSERT INTO schema_version(version)
                SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
                CREATE TABLE IF NOT EXISTS evidence_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    record_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    stage TEXT NOT NULL CHECK (stage IN ('S3_PAPER_DEMO', 'S4_LIVE')),
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    UNIQUE(record_type, record_id, payload_sha256)
                );
                CREATE INDEX IF NOT EXISTS evidence_query_idx
                    ON evidence_events(record_type, stage, occurred_at, sequence);
                CREATE TRIGGER IF NOT EXISTS evidence_no_update
                    BEFORE UPDATE ON evidence_events
                    BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS evidence_no_delete
                    BEFORE DELETE ON evidence_events
                    BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
                """
            )
            version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
            if version != SCHEMA_VERSION:
                raise SyntheticEvidenceStoreError("unsupported synthetic evidence schema")

    def append(
        self,
        record: object,
        *,
        idempotency_key: str,
        record_id: str,
        record_type: str,
        stage: Stage,
        occurred_at: datetime,
        recorded_at: datetime,
    ) -> StoredSyntheticEvidence:
        if not idempotency_key.strip() or not record_id.strip() or not record_type.strip():
            raise SyntheticEvidenceStoreError("evidence identity fields must be non-empty")
        if stage not in (Stage.S3_PAPER_DEMO, Stage.S4_LIVE):
            raise SyntheticEvidenceStoreError("synthetic evidence is reserved for S3/S4")
        payload_json = _canonical(record)
        digest = hashlib.sha256(payload_json.encode()).hexdigest()
        occurred = _utc(occurred_at, "occurred_at")
        recorded = _utc(recorded_at, "recorded_at")
        self.initialize()
        with self._lock(), self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO evidence_events(
                        idempotency_key, record_id, record_type, stage, occurred_at,
                        recorded_at, payload_json, payload_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        idempotency_key,
                        record_id,
                        record_type,
                        stage.value,
                        occurred,
                        recorded,
                        payload_json,
                        digest,
                    ),
                )
            except sqlite3.IntegrityError:
                row = connection.execute(
                    "SELECT * FROM evidence_events WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if row is None or row["payload_sha256"] != digest:
                    raise SyntheticEvidenceStoreError(
                        "evidence idempotency key conflicts with retained content"
                    ) from None
                return _decode(row)
            row = connection.execute(
                "SELECT * FROM evidence_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            assert row is not None
            return _decode(row)

    def list(
        self,
        *,
        record_type: str | None = None,
        stage: Stage | None = None,
        limit: int = 100,
    ) -> tuple[StoredSyntheticEvidence, ...]:
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_QUERY_LIMIT
        ):
            raise SyntheticEvidenceStoreError(f"limit must be between 1 and {MAX_QUERY_LIMIT}")
        self.initialize()
        clauses, values = [], []
        if record_type is not None:
            clauses.append("record_type = ?")
            values.append(record_type)
        if stage is not None:
            clauses.append("stage = ?")
            values.append(stage.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock(), self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM evidence_events{where} ORDER BY sequence LIMIT ?",  # noqa: S608
                (*values, limit),
            ).fetchall()
        return tuple(_decode(row) for row in rows)

    def integrity_check(self) -> bool:
        self.initialize()
        with self._lock(), self._connect() as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            return str(result) == "ok"


def _decode(row: sqlite3.Row) -> StoredSyntheticEvidence:
    return StoredSyntheticEvidence(
        sequence=int(row["sequence"]),
        idempotency_key=str(row["idempotency_key"]),
        record_id=str(row["record_id"]),
        record_type=str(row["record_type"]),
        stage=Stage(str(row["stage"])),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        payload=json.loads(str(row["payload_json"])),
        payload_sha256=str(row["payload_sha256"]),
    )
