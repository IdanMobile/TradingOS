"""Symlink-safe append-only SQLite state for the synthetic paper cockpit."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any

from .models import PaperRuntimeError, _decimal_identity, jsonable

SCHEMA_VERSION = 1
MAX_PAYLOAD_BYTES = 64 * 1024
MAX_DECIMAL_ABS = Decimal("1e50")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")


class PaperStoreError(ValueError):
    """Paper state cannot be retained without violating a storage invariant."""


class PaperEventType(StrEnum):
    BOT = "BOT"
    SIGNAL = "SIGNAL"
    RISK = "RISK"
    FILL = "FILL"
    HEARTBEAT = "HEARTBEAT"
    INCIDENT = "INCIDENT"


class PaperAuditAction(StrEnum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    PAUSE_ENTRIES = "PAUSE_ENTRIES"
    RESUME_ENTRIES = "RESUME_ENTRIES"


@dataclass(frozen=True, slots=True)
class StoredPaperEvent:
    sequence: int
    idempotency_key: str
    event_type: PaperEventType
    subject_id: str
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class StoredPaperAudit:
    sequence: int
    idempotency_key: str
    action: PaperAuditAction
    subject_id: str
    actor: str
    occurred_at: datetime
    payload: dict[str, Any]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class StoredPortfolioPoint:
    sequence: int
    idempotency_key: str
    observed_at: datetime
    equity: Decimal
    cash: Decimal
    exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    external_cash_flow: Decimal
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class PaperStoreProjection:
    entries_paused: bool
    latest_heartbeat_at: datetime | None
    events: tuple[StoredPaperEvent, ...]
    portfolio_points: tuple[StoredPortfolioPoint, ...]
    audits: tuple[StoredPaperAudit, ...]
    acknowledged_item_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class PaperEventWrite:
    event_type: PaperEventType
    subject_id: str
    payload: Mapping[str, object]
    idempotency_key: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PortfolioPointWrite:
    idempotency_key: str
    observed_at: datetime
    equity: Decimal
    cash: Decimal
    exposure: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    external_cash_flow: Decimal = Decimal(0)


def confined_database(path: Path, root: Path) -> Path:
    repo = Path(os.path.realpath(root))
    allowed = repo / "artifacts/paper"
    candidate = path if path.is_absolute() else repo / path
    normalized = Path(os.path.abspath(candidate))
    try:
        relative = normalized.relative_to(allowed)
    except ValueError:
        raise PaperStoreError("paper database must remain in artifacts/paper") from None
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise PaperStoreError("paper database must name a file in artifacts/paper")
    return normalized


def default_database(root: Path) -> Path:
    return Path(os.path.realpath(root)) / "artifacts/paper/paper.sqlite3"


def _stamp(value: datetime, name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PaperStoreError(f"{name} must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise PaperStoreError(f"{name} must be a bounded identifier")


def _validate_json(value: object, *, depth: int = 0) -> None:
    if depth > 6:
        raise PaperStoreError("paper payload nesting is too deep")
    if isinstance(value, float):
        raise PaperStoreError("floating-point JSON values are prohibited")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if isinstance(value, bool) or abs(value) > 2**63 - 1:
            raise PaperStoreError("paper payload integer is invalid")
        return
    if isinstance(value, str):
        if len(value) > 4096:
            raise PaperStoreError("paper payload string is too large")
        return
    if isinstance(value, list):
        if len(value) > 100:
            raise PaperStoreError("paper payload list is too large")
        for item in value:
            _validate_json(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 100 or any(not isinstance(key, str) or len(key) > 100 for key in value):
            raise PaperStoreError("paper payload mapping is invalid")
        for item in value.values():
            _validate_json(item, depth=depth + 1)
        return
    raise PaperStoreError(f"unsupported paper payload value: {type(value).__name__}")


def _decimal_text(
    payload: dict[str, Any],
    names: tuple[str, ...],
    *,
    positive: tuple[str, ...] = (),
    nonnegative: tuple[str, ...] = (),
) -> dict[str, Decimal]:
    parsed_values: dict[str, Decimal] = {}
    for name in names:
        value = payload.get(name)
        if not isinstance(value, str):
            raise PaperStoreError(f"{name} must be an exact decimal string")
        try:
            parsed = Decimal(value)
        except InvalidOperation as error:
            raise PaperStoreError(f"{name} must be an exact decimal string") from error
        if not parsed.is_finite():
            raise PaperStoreError(f"{name} must be finite")
        if parsed.copy_abs() > MAX_DECIMAL_ABS:
            raise PaperStoreError(f"{name} exceeds the retained magnitude limit")
        if name in positive and parsed <= 0:
            raise PaperStoreError(f"{name} must be positive")
        if name in nonnegative and parsed < 0:
            raise PaperStoreError(f"{name} must be nonnegative")
        parsed_values[name] = parsed
    return parsed_values


def _keys(payload: dict[str, Any], required: set[str], optional: set[str] | None = None) -> None:
    if not required <= payload.keys() or payload.keys() - required - (optional or set()):
        raise PaperStoreError("paper event payload does not match its event schema")


def _text_fields(payload: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        if not isinstance(payload.get(name), str) or not str(payload[name]).strip():
            raise PaperStoreError(f"{name} must be non-empty text")


def _validate_event_payload(event_type: PaperEventType, payload: dict[str, Any]) -> None:
    if event_type is PaperEventType.BOT:
        kind = payload.get("kind")
        if kind == "STARTED":
            required = {
                "kind",
                "strategy_version_ref",
                "symbol",
                "timeframe",
                "config_digest",
                "spec_sha256",
                "gate_id",
                "approval_sha256",
                "risk_policy",
                "policy_sha256",
                "validation_approval_ref",
                "validation_evidence_refs",
            }
            _keys(payload, required)
            _text_fields(
                payload,
                tuple(required - {"risk_policy", "validation_evidence_refs"}),
            )
            refs = payload["validation_evidence_refs"]
            if (
                not isinstance(refs, list)
                or not refs
                or any(not isinstance(ref, str) or not ref for ref in refs)
            ):
                raise PaperStoreError("STARTED validation evidence must be retained")
            risk_policy = payload["risk_policy"]
            expected_policy = {
                "starting_capital",
                "max_position_notional",
                "max_total_exposure",
                "max_daily_loss",
                "max_drawdown_fraction",
                "max_open_positions",
                "fee_bps",
                "slippage_bps",
                "quote_max_age_seconds",
                "max_fill_latency_seconds",
                "heartbeat_interval_seconds",
                "stale_after_seconds",
            }
            if not isinstance(risk_policy, dict) or set(risk_policy) != expected_policy:
                raise PaperStoreError("STARTED risk policy must be retained in full")
            _decimal_text(
                risk_policy,
                (
                    "starting_capital",
                    "max_position_notional",
                    "max_total_exposure",
                    "max_daily_loss",
                    "max_drawdown_fraction",
                    "fee_bps",
                    "slippage_bps",
                ),
                positive=(
                    "starting_capital",
                    "max_position_notional",
                    "max_total_exposure",
                    "max_daily_loss",
                    "max_drawdown_fraction",
                ),
                nonnegative=("fee_bps", "slippage_bps"),
            )
            for name in expected_policy - {
                "starting_capital",
                "max_position_notional",
                "max_total_exposure",
                "max_daily_loss",
                "max_drawdown_fraction",
                "fee_bps",
                "slippage_bps",
            }:
                value = risk_policy[name]
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise PaperStoreError(f"{name} must be a positive integer")
        elif kind == "EVALUATED":
            _keys(payload, {"kind", "last_evaluated_bar_at", "signal_count"})
            _text_fields(payload, ("last_evaluated_bar_at",))
            if (
                not isinstance(payload["signal_count"], int)
                or isinstance(payload["signal_count"], bool)
                or payload["signal_count"] < 0
            ):
                raise PaperStoreError("signal_count must be a nonnegative integer")
        else:
            raise PaperStoreError("BOT event kind is invalid")
    elif event_type is PaperEventType.SIGNAL:
        _keys(payload, {"signal_id", "symbol", "timeframe", "side", "rationale"})
        _text_fields(payload, ("signal_id", "symbol", "timeframe", "side", "rationale"))
        if payload["side"] not in {"BUY", "SELL"}:
            raise PaperStoreError("signal side is invalid")
    elif event_type is PaperEventType.RISK:
        required = {
            "signal_id",
            "decision",
            "reason",
            "proposed_notional",
            "capital_at_risk",
            "daily_loss",
            "drawdown_fraction",
            "open_positions",
        }
        _keys(payload, required)
        _text_fields(payload, ("signal_id", "decision", "reason"))
        if payload["decision"] not in {"PASS", "BLOCK"}:
            raise PaperStoreError("risk decision is invalid")
        risk_values = _decimal_text(
            payload,
            ("proposed_notional", "capital_at_risk", "daily_loss", "drawdown_fraction"),
            positive=("proposed_notional",),
            nonnegative=("capital_at_risk", "daily_loss", "drawdown_fraction"),
        )
        if risk_values["drawdown_fraction"] > 1:
            raise PaperStoreError("drawdown_fraction must be at most one")
        if (
            not isinstance(payload["open_positions"], int)
            or isinstance(payload["open_positions"], bool)
            or payload["open_positions"] < 0
        ):
            raise PaperStoreError("open_positions must be a nonnegative integer")
    elif event_type is PaperEventType.FILL:
        required = {
            "signal_id",
            "fill_id",
            "symbol",
            "timeframe",
            "side",
            "price",
            "quantity",
            "notional",
            "fee",
            "cash_after",
            "position_quantity_after",
            "position_cost_after",
            "realized_pnl_after",
            "fees_after",
        }
        _keys(payload, required)
        _text_fields(
            payload,
            ("signal_id", "fill_id", "symbol", "timeframe", "side"),
        )
        if payload["side"] not in {"BUY", "SELL"}:
            raise PaperStoreError("fill side is invalid")
        _decimal_text(
            payload,
            tuple(required - {"signal_id", "fill_id", "symbol", "timeframe", "side"}),
            positive=("price", "quantity", "notional"),
            nonnegative=(
                "fee",
                "cash_after",
                "position_quantity_after",
                "position_cost_after",
                "fees_after",
            ),
        )
    elif event_type is PaperEventType.HEARTBEAT:
        if set(payload) == {"ok"}:
            if not isinstance(payload["ok"], bool):
                raise PaperStoreError("heartbeat ok must be boolean")
        else:
            _keys(payload, {"status", "source", "mark_price"})
            _text_fields(payload, ("status", "source"))
            if payload["status"] != "OK":
                raise PaperStoreError("heartbeat status is invalid")
            _decimal_text(payload, ("mark_price",), positive=("mark_price",))
    elif event_type is PaperEventType.INCIDENT:
        _keys(payload, {"summary", "source"}, {"code"})
        _text_fields(payload, ("summary", "source"))
        if "code" in payload:
            _text_fields(payload, ("code",))


def _payload(
    value: Mapping[str, object], event_type: PaperEventType | None = None
) -> tuple[str, str]:
    try:
        normalized = jsonable(dict(value))
    except PaperRuntimeError as error:
        raise PaperStoreError(str(error)) from error
    if not isinstance(normalized, dict):
        raise PaperStoreError("paper payload must be a mapping")
    _validate_json(normalized)
    if event_type is not None:
        _validate_event_payload(event_type, normalized)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode()) > MAX_PAYLOAD_BYTES:
        raise PaperStoreError("paper payload exceeds its size limit")
    return encoded, hashlib.sha256(encoded.encode()).hexdigest()


class PaperStore:
    """Three append-only ledgers; every use refuses changed or symlinked storage."""

    _locks_guard = threading.Lock()
    _locks: dict[str, threading.RLock] = {}

    def __init__(self, path: Path | None = None, *, root: Path) -> None:
        self.root = Path(os.path.realpath(root))
        self.path = confined_database(path or default_database(root), self.root)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.runner_lock_path = self.path.with_suffix(self.path.suffix + ".runner.lock")
        root_stat = os.stat(self.root, follow_symlinks=False)
        self._root_identity = (root_stat.st_dev, root_stat.st_ino)
        key = str(self.path)
        with self._locks_guard:
            self._process_lock = self._locks.setdefault(key, threading.RLock())

    def __enter__(self) -> PaperStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Compatibility no-op: SQLite connections are scoped and closed per call."""

    def _assert_safe(self, *, create: bool) -> tuple[int, int] | None:
        root_stat = os.stat(self.root, follow_symlinks=False)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or (
                root_stat.st_dev,
                root_stat.st_ino,
            )
            != self._root_identity
        ):
            raise PaperStoreError("paper storage root identity changed")
        current = self.root
        relative_parent = self.path.parent.relative_to(self.root)
        for component in relative_parent.parts:
            current /= component
            if create:
                try:
                    current.mkdir(mode=0o700)
                except FileExistsError:
                    pass
            linked = os.lstat(current)
            if stat.S_ISLNK(linked.st_mode) or not stat.S_ISDIR(linked.st_mode):
                raise PaperStoreError("paper storage path cannot contain symlinks")
        try:
            linked = os.lstat(self.path)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(linked.st_mode) or not stat.S_ISREG(linked.st_mode):
            raise PaperStoreError("paper database cannot be a symlink")
        if linked.st_nlink != 1:
            raise PaperStoreError("paper database cannot have hardlinks")
        return linked.st_dev, linked.st_ino

    @contextmanager
    def _file_lock(self, path: Path, *, nonblocking: bool = False) -> Iterator[None]:
        self._assert_safe(create=True)
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW,
            0o600,
        )
        locked = False
        try:
            opened, linked = os.fstat(descriptor), os.lstat(path)
            if opened.st_nlink != 1 or linked.st_nlink != 1:
                raise PaperStoreError("paper lock cannot have hardlinks")
            if not stat.S_ISREG(linked.st_mode) or (opened.st_dev, opened.st_ino) != (
                linked.st_dev,
                linked.st_ino,
            ):
                raise PaperStoreError("paper lock identity changed")
            try:
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0),
                )
                locked = True
            except BlockingIOError:
                raise PaperStoreError("another paper runner holds the lease") from None
            yield
            current, linked = os.fstat(descriptor), os.lstat(path)
            if current.st_nlink != 1 or linked.st_nlink != 1:
                raise PaperStoreError("paper lock cannot have hardlinks")
            if (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
                raise PaperStoreError("paper lock identity changed")
        finally:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def _connect(self, *, create: bool, write: bool) -> Iterator[sqlite3.Connection]:
        with self._process_lock, self._file_lock(self.lock_path):
            before = self._assert_safe(create=create)
            connection = sqlite3.connect(self.path, timeout=30)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA synchronous = FULL")
                after_open = self._assert_safe(create=False)
                if before is not None and before != after_open:
                    raise PaperStoreError("paper database identity changed while opening")
                try:
                    yield connection
                    if write:
                        connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
            finally:
                connection.close()
                if self._assert_safe(create=False) != after_open:
                    raise PaperStoreError("paper database identity changed during use")

    @contextmanager
    def runner_lease(self) -> Iterator[None]:
        """Admit one runner per store so a bar cannot be filled twice concurrently."""
        with self._file_lock(self.runner_lock_path, nonblocking=True):
            yield

    @staticmethod
    def _schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL CHECK (version = 1)
            );
            INSERT INTO schema_version(version)
            SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
            CREATE TABLE IF NOT EXISTS paper_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL CHECK (
                    event_type IN ('BOT','SIGNAL','RISK','FILL','HEARTBEAT','INCIDENT')
                ),
                subject_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                action TEXT NOT NULL CHECK (
                    action IN ('ACKNOWLEDGE','PAUSE_ENTRIES','RESUME_ENTRIES')
                ),
                subject_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio_points (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                observed_at TEXT NOT NULL,
                equity TEXT NOT NULL,
                cash TEXT NOT NULL,
                exposure TEXT NOT NULL,
                realized_pnl TEXT NOT NULL,
                unrealized_pnl TEXT NOT NULL,
                fees TEXT NOT NULL,
                external_cash_flow TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS paper_events_query
                ON paper_events(event_type, subject_id, occurred_at, sequence);
            CREATE INDEX IF NOT EXISTS portfolio_points_time
                ON portfolio_points(observed_at, sequence);
            CREATE TRIGGER IF NOT EXISTS paper_events_no_update BEFORE UPDATE ON paper_events
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_events_no_delete BEFORE DELETE ON paper_events
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_audit_no_update BEFORE UPDATE ON paper_audit
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS paper_audit_no_delete BEFORE DELETE ON paper_audit
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS portfolio_points_no_update
            BEFORE UPDATE ON portfolio_points
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS portfolio_points_no_delete
            BEFORE DELETE ON portfolio_points
                BEGIN SELECT RAISE(ABORT, 'paper state is append-only'); END;
            """
        )
        rows = connection.execute("SELECT version FROM schema_version").fetchall()
        if len(rows) != 1 or rows[0][0] != SCHEMA_VERSION:
            raise PaperStoreError("unsupported paper database schema")

    def initialize(self) -> None:
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        draft: PaperEventWrite,
        *,
        recorded_at: datetime,
    ) -> StoredPaperEvent:
        event_type = PaperEventType(draft.event_type)
        _identifier(draft.idempotency_key, "event idempotency_key")
        _identifier(draft.subject_id, "event subject_id")
        payload_json, digest = _payload(draft.payload, event_type)
        occurred = _stamp(draft.occurred_at, "occurred_at")
        recorded = _stamp(recorded_at, "recorded_at")
        try:
            connection.execute(
                """INSERT INTO paper_events(
                    idempotency_key,event_type,subject_id,occurred_at,recorded_at,
                    payload_json,payload_sha256
                ) VALUES (?,?,?,?,?,?,?)""",
                (
                    draft.idempotency_key,
                    event_type.value,
                    draft.subject_id,
                    occurred,
                    recorded,
                    payload_json,
                    digest,
                ),
            )
        except sqlite3.IntegrityError:
            row = connection.execute(
                "SELECT * FROM paper_events WHERE idempotency_key = ?",
                (draft.idempotency_key,),
            ).fetchone()
            if row is None or (
                row["event_type"],
                row["subject_id"],
                row["occurred_at"],
                row["payload_sha256"],
            ) != (event_type.value, draft.subject_id, occurred, digest):
                raise PaperStoreError(
                    "event idempotency key conflicts with retained content"
                ) from None
            return _event(row)
        row = connection.execute(
            "SELECT * FROM paper_events WHERE idempotency_key = ?",
            (draft.idempotency_key,),
        ).fetchone()
        assert row is not None
        return _event(row)

    def append_event(
        self,
        event_type: PaperEventType,
        subject_id: str,
        payload: Mapping[str, object],
        *,
        idempotency_key: str,
        occurred_at: datetime,
        recorded_at: datetime | None = None,
    ) -> StoredPaperEvent:
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            return self._insert_event(
                connection,
                PaperEventWrite(event_type, subject_id, payload, idempotency_key, occurred_at),
                recorded_at=recorded_at or datetime.now(tz=UTC),
            )

    def append_audit(
        self,
        action: PaperAuditAction,
        subject_id: str,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime,
        payload: Mapping[str, object] | None = None,
    ) -> StoredPaperAudit:
        action = PaperAuditAction(action)
        for value, name in (
            (subject_id, "audit subject_id"),
            (actor, "audit actor"),
            (idempotency_key, "audit idempotency_key"),
        ):
            _identifier(value, name)
        payload_json, digest = _payload(payload or {})
        occurred = _stamp(occurred_at, "occurred_at")
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            try:
                connection.execute(
                    """INSERT INTO paper_audit(
                        idempotency_key,action,subject_id,actor,occurred_at,payload_json,payload_sha256
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (
                        idempotency_key,
                        action.value,
                        subject_id,
                        actor,
                        occurred,
                        payload_json,
                        digest,
                    ),
                )
            except sqlite3.IntegrityError:
                row = connection.execute(
                    "SELECT * FROM paper_audit WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if row is None or (
                    row["action"],
                    row["subject_id"],
                    row["actor"],
                    row["occurred_at"],
                    row["payload_sha256"],
                ) != (action.value, subject_id, actor, occurred, digest):
                    raise PaperStoreError(
                        "audit idempotency key conflicts with retained content"
                    ) from None
                return _audit(row)
            row = connection.execute(
                "SELECT * FROM paper_audit WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            assert row is not None
            return _audit(row)

    def acknowledge_attention(
        self,
        item_id: str,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> StoredPaperAudit:
        return self.append_audit(
            PaperAuditAction.ACKNOWLEDGE,
            item_id,
            actor=actor,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )

    def set_entries_paused(
        self,
        paused: bool,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> StoredPaperAudit:
        if not isinstance(paused, bool):
            raise PaperStoreError("paused must be boolean")
        return self.append_audit(
            PaperAuditAction.PAUSE_ENTRIES if paused else PaperAuditAction.RESUME_ENTRIES,
            "paper-entries",
            actor=actor,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _prepare_point(draft: PortfolioPointWrite) -> tuple[str, str, tuple[str, ...]]:
        _identifier(draft.idempotency_key, "portfolio idempotency_key")
        values = (
            draft.equity,
            draft.cash,
            draft.exposure,
            draft.realized_pnl,
            draft.unrealized_pnl,
            draft.fees,
            draft.external_cash_flow,
        )
        if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
            raise PaperStoreError("portfolio values must be finite Decimals")
        if any(value.copy_abs() > MAX_DECIMAL_ABS for value in values):
            raise PaperStoreError("portfolio value exceeds the retained magnitude limit")
        if any(value < 0 for value in (draft.equity, draft.cash, draft.exposure, draft.fees)):
            raise PaperStoreError("portfolio equity, cash, exposure, and fees cannot be negative")
        stamp = _stamp(draft.observed_at, "observed_at")
        canonical = tuple(Decimal(_decimal_identity(value)) for value in values)
        _, digest = _payload(
            {
                "observed_at": stamp,
                "equity": canonical[0],
                "cash": canonical[1],
                "exposure": canonical[2],
                "realized_pnl": canonical[3],
                "unrealized_pnl": canonical[4],
                "fees": canonical[5],
                "external_cash_flow": canonical[6],
            }
        )
        return stamp, digest, tuple(_decimal_identity(value) for value in canonical)

    @classmethod
    def _insert_point(
        cls, connection: sqlite3.Connection, draft: PortfolioPointWrite
    ) -> StoredPortfolioPoint:
        stamp, digest, values = cls._prepare_point(draft)
        existing = connection.execute(
            "SELECT * FROM portfolio_points WHERE idempotency_key = ?",
            (draft.idempotency_key,),
        ).fetchone()
        if existing is not None:
            if existing["payload_sha256"] != digest:
                raise PaperStoreError("portfolio idempotency key conflicts with retained content")
            return _point(existing)
        latest = connection.execute(
            "SELECT observed_at FROM portfolio_points ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        if latest is not None and datetime.fromisoformat(str(latest[0])) > draft.observed_at:
            raise PaperStoreError("portfolio observed_at must be monotonic")
        try:
            connection.execute(
                """INSERT INTO portfolio_points(
                    idempotency_key,observed_at,equity,cash,exposure,realized_pnl,
                    unrealized_pnl,fees,external_cash_flow,payload_sha256
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (draft.idempotency_key, stamp, *values, digest),
            )
        except sqlite3.IntegrityError as error:
            raise PaperStoreError("portfolio point could not be retained") from error
        row = connection.execute(
            "SELECT * FROM portfolio_points WHERE idempotency_key = ?",
            (draft.idempotency_key,),
        ).fetchone()
        assert row is not None
        return _point(row)

    def append_portfolio_point(
        self,
        *,
        idempotency_key: str,
        observed_at: datetime,
        equity: Decimal,
        cash: Decimal,
        exposure: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        fees: Decimal,
        external_cash_flow: Decimal = Decimal(0),
    ) -> StoredPortfolioPoint:
        draft = PortfolioPointWrite(
            idempotency_key,
            observed_at,
            equity,
            cash,
            exposure,
            realized_pnl,
            unrealized_pnl,
            fees,
            external_cash_flow,
        )
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            return self._insert_point(connection, draft)

    def commit_cycle(
        self,
        events: tuple[PaperEventWrite, ...],
        points: tuple[PortfolioPointWrite, ...] = (),
        *,
        recorded_at: datetime,
        require_entries_unpaused: bool = False,
    ) -> bool:
        """Publish one evaluated bar and all of its synthetic accounting atomically."""
        if len({event.idempotency_key for event in events}) != len(events) or len(
            {point.idempotency_key for point in points}
        ) != len(points):
            raise PaperStoreError("cycle idempotency keys must be unique")
        require_entries_unpaused = require_entries_unpaused or any(
            event.event_type is PaperEventType.FILL and event.payload.get("side") == "BUY"
            for event in events
        )
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            if require_entries_unpaused:
                control = connection.execute(
                    """SELECT action FROM paper_audit
                       WHERE action IN ('PAUSE_ENTRIES','RESUME_ENTRIES')
                       ORDER BY sequence DESC LIMIT 1"""
                ).fetchone()
                if control is not None and control[0] == PaperAuditAction.PAUSE_ENTRIES.value:
                    return False
            for event in events:
                self._insert_event(connection, event, recorded_at=recorded_at)
            for point in points:
                self._insert_point(connection, point)
        return True

    def current_projection(self) -> PaperStoreProjection:
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            events = tuple(
                _event(row)
                for row in connection.execute(
                    "SELECT * FROM paper_events ORDER BY sequence"
                ).fetchall()
            )
            points = tuple(
                _point(row)
                for row in connection.execute(
                    "SELECT * FROM portfolio_points ORDER BY sequence"
                ).fetchall()
            )
            audits = tuple(
                _audit(row)
                for row in connection.execute(
                    "SELECT * FROM paper_audit ORDER BY sequence"
                ).fetchall()
            )
        return _projection(events, points, audits)

    def refresh_projection(self, previous: PaperStoreProjection) -> PaperStoreProjection:
        """Read only rows appended after a known projection using primary-key indexes."""
        event_sequence = previous.events[-1].sequence if previous.events else 0
        point_sequence = previous.portfolio_points[-1].sequence if previous.portfolio_points else 0
        audit_sequence = previous.audits[-1].sequence if previous.audits else 0
        with self._connect(create=True, write=True) as connection:
            self._schema(connection)
            events = previous.events + tuple(
                _event(row)
                for row in connection.execute(
                    "SELECT * FROM paper_events WHERE sequence > ? ORDER BY sequence",
                    (event_sequence,),
                ).fetchall()
            )
            points = previous.portfolio_points + tuple(
                _point(row)
                for row in connection.execute(
                    "SELECT * FROM portfolio_points WHERE sequence > ? ORDER BY sequence",
                    (point_sequence,),
                ).fetchall()
            )
            audits = previous.audits + tuple(
                _audit(row)
                for row in connection.execute(
                    "SELECT * FROM paper_audit WHERE sequence > ? ORDER BY sequence",
                    (audit_sequence,),
                ).fetchall()
            )
        return _projection(events, points, audits)

    def integrity_check(self) -> bool:
        try:
            with self._connect(create=True, write=True) as connection:
                self._schema(connection)
                if str(connection.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                    return False
                for row in connection.execute("SELECT * FROM paper_events"):
                    _event(row)
                for row in connection.execute("SELECT * FROM paper_audit"):
                    _audit(row)
                for row in connection.execute("SELECT * FROM portfolio_points"):
                    _point(row)
            return True
        except (PaperStoreError, sqlite3.DatabaseError, ValueError):
            return False


def _projection(
    events: tuple[StoredPaperEvent, ...],
    points: tuple[StoredPortfolioPoint, ...],
    audits: tuple[StoredPaperAudit, ...],
) -> PaperStoreProjection:
    control = next(
        (
            audit
            for audit in reversed(audits)
            if audit.action
            in {
                PaperAuditAction.PAUSE_ENTRIES,
                PaperAuditAction.RESUME_ENTRIES,
            }
        ),
        None,
    )
    heartbeat = max(
        (event.occurred_at for event in events if event.event_type is PaperEventType.HEARTBEAT),
        default=None,
    )
    return PaperStoreProjection(
        bool(control and control.action is PaperAuditAction.PAUSE_ENTRIES),
        heartbeat,
        events,
        points,
        audits,
        frozenset(
            audit.subject_id for audit in audits if audit.action is PaperAuditAction.ACKNOWLEDGE
        ),
    )


def _event(row: sqlite3.Row) -> StoredPaperEvent:
    event_type = PaperEventType(str(row["event_type"]))
    payload = json.loads(str(row["payload_json"]))
    if not isinstance(payload, dict):
        raise PaperStoreError("retained event payload is not a mapping")
    _validate_json(payload)
    _validate_event_payload(event_type, payload)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    if digest != str(row["payload_sha256"]):
        raise PaperStoreError("retained event payload hash does not match")
    return StoredPaperEvent(
        int(row["sequence"]),
        str(row["idempotency_key"]),
        event_type,
        str(row["subject_id"]),
        datetime.fromisoformat(str(row["occurred_at"])),
        datetime.fromisoformat(str(row["recorded_at"])),
        payload,
        digest,
    )


def _audit(row: sqlite3.Row) -> StoredPaperAudit:
    payload = json.loads(str(row["payload_json"]))
    if not isinstance(payload, dict):
        raise PaperStoreError("retained audit payload is not a mapping")
    _validate_json(payload)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    if digest != str(row["payload_sha256"]):
        raise PaperStoreError("retained audit payload hash does not match")
    return StoredPaperAudit(
        int(row["sequence"]),
        str(row["idempotency_key"]),
        PaperAuditAction(str(row["action"])),
        str(row["subject_id"]),
        str(row["actor"]),
        datetime.fromisoformat(str(row["occurred_at"])),
        payload,
        digest,
    )


def _point(row: sqlite3.Row) -> StoredPortfolioPoint:
    observed_at = str(row["observed_at"])
    equity = Decimal(str(row["equity"]))
    cash = Decimal(str(row["cash"]))
    exposure = Decimal(str(row["exposure"]))
    realized_pnl = Decimal(str(row["realized_pnl"]))
    unrealized_pnl = Decimal(str(row["unrealized_pnl"]))
    fees = Decimal(str(row["fees"]))
    external_cash_flow = Decimal(str(row["external_cash_flow"]))
    _, digest = _payload(
        {
            "observed_at": observed_at,
            "equity": equity,
            "cash": cash,
            "exposure": exposure,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "fees": fees,
            "external_cash_flow": external_cash_flow,
        }
    )
    if digest != str(row["payload_sha256"]):
        raise PaperStoreError("retained portfolio payload hash does not match")
    return StoredPortfolioPoint(
        int(row["sequence"]),
        str(row["idempotency_key"]),
        datetime.fromisoformat(observed_at),
        equity,
        cash,
        exposure,
        realized_pnl,
        unrealized_pnl,
        fees,
        external_cash_flow,
        digest,
    )
