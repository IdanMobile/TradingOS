"""Deterministic, read-only evidence bridge for operator-copied demo-lane snapshots.

This module has no venue, credential, transport, order, or active-lane capability.  Stage A
imports three files copied by an operator into a separate location and emits conservative,
private evidence.  Legacy observations never become realised outcomes.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import cast

from tios.evidence.store import SyntheticEvidenceStore
from tios.trading_domain import Stage

SCHEMA = "tios.demo_decision_evidence.v1"
ACTIVE_DEMO_LANE = Path("artifacts/trading_domain/demo_lane")
PRIVATE_EVIDENCE_ROOT = Path("artifacts/evidence/private_demo")
DEFAULT_STAGE_A_OUTPUT = PRIVATE_EVIDENCE_ROOT / "stage_a"
RECORD_TYPE = "DemoDecisionEvidenceEvent"
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_ORDERS_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = 16
MAX_JSON_NODES = 2_000
MAX_PROJECTION_JSON_NODES = 4_000_000
MAX_STRING_LENGTH = 4_096
MAX_JSONL_ROWS = 100_000
MAX_DECIMAL_TEXT = 128
MAX_PRIVATE_BYTES = 128 * 1024 * 1024
_EXPECTED_STORE_SCHEMA_ROWS: tuple[dict[str, object], ...] = (
    {
        "type": "index",
        "name": "evidence_query_idx",
        "table_name": "evidence_events",
        "sql": (
            "CREATE INDEX evidence_query_idx ON evidence_events"
            "(record_type, stage, occurred_at, sequence)"
        ),
    },
    {
        "type": "index",
        "name": "sqlite_autoindex_evidence_events_1",
        "table_name": "evidence_events",
        "sql": None,
    },
    {
        "type": "index",
        "name": "sqlite_autoindex_evidence_events_2",
        "table_name": "evidence_events",
        "sql": None,
    },
    {
        "type": "table",
        "name": "evidence_events",
        "table_name": "evidence_events",
        "sql": (
            "CREATE TABLE evidence_events ( sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
            "idempotency_key TEXT NOT NULL UNIQUE, record_id TEXT NOT NULL, "
            "record_type TEXT NOT NULL, stage TEXT NOT NULL CHECK "
            "(stage IN ('S3_PAPER_DEMO', 'S4_LIVE')), occurred_at TEXT NOT NULL, "
            "recorded_at TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "payload_sha256 TEXT NOT NULL, "
            "UNIQUE(record_type, record_id, payload_sha256) )"
        ),
    },
    {
        "type": "table",
        "name": "schema_version",
        "table_name": "schema_version",
        "sql": ("CREATE TABLE schema_version ( version INTEGER NOT NULL CHECK (version = 1) )"),
    },
    {
        "type": "table",
        "name": "sqlite_sequence",
        "table_name": "sqlite_sequence",
        "sql": "CREATE TABLE sqlite_sequence(name,seq)",
    },
    {
        "type": "trigger",
        "name": "evidence_no_delete",
        "table_name": "evidence_events",
        "sql": (
            "CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence_events "
            "BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END"
        ),
    },
    {
        "type": "trigger",
        "name": "evidence_no_update",
        "table_name": "evidence_events",
        "sql": (
            "CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence_events "
            "BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END"
        ),
    },
)
_FINAL_GENERATION_FILES = frozenset(
    {
        "baseline.json",
        "events.jsonl",
        "projection.json",
        "export.jsonl",
        "manifest.json",
    }
)
_PENDING_GENERATION_PHASES: tuple[frozenset[str], ...] = (
    frozenset(),
    frozenset({"baseline.json"}),
    frozenset({"baseline.json", "events.jsonl"}),
    frozenset({"baseline.json", "events.jsonl", "projection.json"}),
    frozenset(
        {
            "baseline.json",
            "events.jsonl",
            "projection.json",
            "export.jsonl",
        }
    ),
    _FINAL_GENERATION_FILES,
)
_ATOMIC_TEMP = re.compile(r"^\.(?P<target>[A-Za-z0-9_.-]{1,128})\.tmp-(?P<pid>[1-9][0-9]*)$")


class DemoDecisionBridgeError(ValueError):
    """Evidence cannot be produced without violating a Stage A invariant."""


class EvidenceConflictError(DemoDecisionBridgeError):
    """A retained logical key was presented with different content."""

    def __init__(self, event: Mapping[str, object]) -> None:
        self.event = dict(event)
        super().__init__("EVIDENCE_CONFLICT: retained logical key has different content")


class SourceIncidentError(DemoDecisionBridgeError):
    """A copied source changed or was truncated across one evidence history."""

    def __init__(self, incident_type: str, event: Mapping[str, object]) -> None:
        self.incident_type = incident_type
        self.event = dict(event)
        super().__init__(f"{incident_type}: copied source history is not append-only")


class DecimalFidelity(StrEnum):
    VENUE_DECIMAL_TEXT = "VENUE_DECIMAL_TEXT"
    CANONICAL_DECIMAL_EXACT = "CANONICAL_DECIMAL_EXACT"
    LEGACY_ROUNDED_8DP = "LEGACY_ROUNDED_8DP"
    LEGACY_ROUNDED_4DP = "LEGACY_ROUNDED_4DP"
    UNKNOWN_PRECISION = "UNKNOWN_PRECISION"


class BarDisposition(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    ENTRY_SIGNAL = "ENTRY_SIGNAL"
    EXIT_SIGNAL = "EXIT_SIGNAL"
    HOLD_POSITION = "HOLD_POSITION"
    ENTRY_SUPPRESSED_ALREADY_OPEN = "ENTRY_SUPPRESSED_ALREADY_OPEN"
    EXIT_SUPPRESSED_FLAT = "EXIT_SUPPRESSED_FLAT"
    BLOCKED_DATA_QUALITY = "BLOCKED_DATA_QUALITY"
    BLOCKED_STALE_DATA = "BLOCKED_STALE_DATA"
    BLOCKED_RISK = "BLOCKED_RISK"
    BLOCKED_OPERATIONS = "BLOCKED_OPERATIONS"
    ERROR = "ERROR"


BAR_DISPOSITIONS = tuple(item.value for item in BarDisposition)
EXECUTION_ELIGIBLE_DISPOSITIONS = frozenset(
    {BarDisposition.ENTRY_SIGNAL.value, BarDisposition.EXIT_SIGNAL.value}
)
LEGACY_LIMITATIONS = (
    "Legacy files do not retain one complete decision event per evaluated bar.",
    "Multi-file copies are best-effort and are not an atomic lane snapshot.",
    "Legacy orders have no retained client idempotency key.",
    "Rounded legacy deltas are never exact realised-PnL evidence.",
)


class EventType(StrEnum):
    BAR_EVALUATED = "BAR_EVALUATED"
    ORDER_ATTEMPTED = "ORDER_ATTEMPTED"
    ORDER_ACKNOWLEDGED = "ORDER_ACKNOWLEDGED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
    RECONCILIATION_CONFIRMED = "RECONCILIATION_CONFIRMED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOP_ACTIVE = "STOP_ACTIVE"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    STOP_CANCELLED = "STOP_CANCELLED"
    STOP_FAILED = "STOP_FAILED"
    LEGACY_ORDER_OBSERVED = "LEGACY_ORDER_OBSERVED"
    LEGACY_SNAPSHOT_IMPORTED = "LEGACY_SNAPSHOT_IMPORTED"
    SOURCE_MUTATION = "SOURCE_MUTATION"
    SOURCE_TRUNCATION = "SOURCE_TRUNCATION"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"


class NumericLexeme(str):
    """A JSON number retained exactly as written, distinct from a JSON string."""


@dataclass(frozen=True, slots=True)
class SourceCopy:
    kind: str
    label: str
    data: bytes
    sha256: str
    byte_count: int

    def reference(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True, slots=True)
class BridgeResult:
    projection: dict[str, object]
    events: tuple[dict[str, object], ...]
    export_path: Path
    export_sha256: str
    appended_event_count: int


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    rows: tuple[dict[str, object], ...]
    schema_sha256: str
    schema_version: int
    last_sequence: int


_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_ID = re.compile(r"[A-Z]{3,8}-[A-Za-z0-9_.:-]{1,96}")
_SHA256 = re.compile(r"[a-f0-9]{64}")
_VENUE_ORDER_REF = re.compile(r"VOH-[a-f0-9]{32}")
_CANONICAL_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_FORBIDDEN_KEYS = (
    "apikey",
    "secret",
    "password",
    "passphrase",
    "privatekey",
    "credential",
    "authorization",
    "accesstoken",
    "refreshtoken",
    "token",
    "bearer",
    "session",
    "sessionid",
    "csrf",
    "jwt",
    "oauth",
    "clientsecret",
    "signature",
    "signedurl",
    "rawauth",
    "cookie",
    "requestheader",
    "responseheader",
    "requestbody",
    "requestparams",
    "endpoint",
    "recvwindow",
    "nonce",
    "transportcall",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+", re.IGNORECASE),
    re.compile(
        r"[?&](?:api[_-]?key|signature|token|secret|password|session|x-amz-[^=]+)=",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:access[_-]?token|refresh[_-]?token|password|passphrase|"
        r"session[_-]?id|x-api-key)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"\b(?:sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|"
        r"github_pat_[A-Za-z0-9_]{8,}|xoxb-[A-Za-z0-9-]{8,}|"
        r"xoxp-[A-Za-z0-9-]{8,}|sk_live_[A-Za-z0-9]{8,}|"
        r"glpat-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,})\b"
    ),
)


def _jsonable(value: object) -> object:
    if isinstance(value, NumericLexeme):
        return {"numeric_lexeme": str(value)}
    if isinstance(value, Decimal):
        return canonical_decimal_string(value)
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        raise DemoDecisionBridgeError("binary floats are forbidden in decision evidence")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise DemoDecisionBridgeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return one stable JSON representation; NaN and Infinity are forbidden."""

    node_limit = (
        MAX_PROJECTION_JSON_NODES
        if isinstance(value, Mapping) and value.get("kind") == "PROJECTION"
        else MAX_JSON_NODES
    )
    _validate_structure_bounds(value, node_limit=node_limit)
    try:
        return json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except DemoDecisionBridgeError:
        raise
    except (TypeError, ValueError) as exc:
        raise DemoDecisionBridgeError("value is not canonical JSON") from exc


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, payload: object) -> str:
    if not re.fullmatch(r"[A-Z]{3,8}", prefix):
        raise DemoDecisionBridgeError("stable id prefix is invalid")
    separated = {"domain": f"{SCHEMA}:{prefix}", "payload": payload}
    return f"{prefix}-{canonical_digest(separated)[:32]}"


def canonical_decimal_string(value: Decimal) -> str:
    if not value.is_finite():
        raise DemoDecisionBridgeError("decimal must be finite")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or abs(exponent) > 100 or len(value.as_tuple().digits) > 100:
        raise DemoDecisionBridgeError("decimal exceeds retained precision bounds")
    if value.is_zero():
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def decimal_evidence(
    value: str | NumericLexeme | Decimal | int,
    fidelity: DecimalFidelity,
) -> dict[str, str]:
    if isinstance(value, bool):
        raise DemoDecisionBridgeError("boolean is not a decimal")
    source_text = str(value)
    parsed = _bounded_decimal(source_text)
    return {
        "canonical": canonical_decimal_string(parsed),
        "source_text": source_text,
        "fidelity": fidelity.value,
    }


def canonical_timestamp(value: str | datetime) -> str:
    source = value.isoformat() if isinstance(value, datetime) else value
    if not isinstance(source, str) or not source.strip():
        raise DemoDecisionBridgeError("timestamp must be non-empty")
    try:
        parsed = datetime.fromisoformat(source.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise DemoDecisionBridgeError("timestamp is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DemoDecisionBridgeError("timestamp must be timezone-aware")
    utc = parsed.astimezone(UTC)
    rendered = utc.isoformat(timespec="microseconds")
    if utc.microsecond == 0:
        rendered = utc.isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def timestamp_evidence(value: str | datetime | None) -> dict[str, object]:
    if value is None:
        return {
            "status": "SOURCE_UNKNOWN",
            "canonical": None,
            "source_text": None,
            "storage_timestamp": "1970-01-01T00:00:00Z",
        }
    source_text = value.isoformat() if isinstance(value, datetime) else value
    canonical = canonical_timestamp(value)
    return {
        "status": "SOURCE_REPORTED",
        "canonical": canonical,
        "source_text": source_text,
        "storage_timestamp": canonical,
    }


def parse_json_bytes(data: bytes, *, label: str) -> dict[str, object]:
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise DemoDecisionBridgeError(f"{label} exceeds the snapshot byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DemoDecisionBridgeError(f"{label} is not UTF-8") from exc
    parsed = _json_loads_exact(text, label=label, preserve_numeric_lexemes=True)
    if not isinstance(parsed, dict):
        raise DemoDecisionBridgeError(f"{label} must contain one JSON object")
    _validate_structure_bounds(parsed)
    return cast(dict[str, object], parsed)


def parse_jsonl_bytes(data: bytes, *, label: str) -> tuple[dict[str, object], ...]:
    if len(data) > MAX_ORDERS_BYTES:
        raise DemoDecisionBridgeError(f"{label} exceeds the ledger byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DemoDecisionBridgeError(f"{label} is not UTF-8") from exc
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(rows) >= MAX_JSONL_ROWS:
            raise DemoDecisionBridgeError(f"{label} exceeds the row limit")
        if len(line) > MAX_SNAPSHOT_BYTES:
            raise DemoDecisionBridgeError(f"{label}:{line_number} exceeds the row byte limit")
        parsed = _json_loads_exact(
            line,
            label=f"{label}:{line_number}",
            preserve_numeric_lexemes=True,
        )
        if not isinstance(parsed, dict):
            raise DemoDecisionBridgeError(f"{label}:{line_number} must be a JSON object")
        _validate_structure_bounds(parsed)
        rows.append(cast(dict[str, object], parsed))
    return tuple(rows)


def _json_loads_exact(
    text: str,
    *,
    label: str,
    preserve_numeric_lexemes: bool,
) -> object:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DemoDecisionBridgeError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            text,
            parse_float=(
                NumericLexeme
                if preserve_numeric_lexemes
                else lambda value: _reject_json_constant(value, label)
            ),
            parse_int=NumericLexeme if preserve_numeric_lexemes else int,
            parse_constant=lambda value: _reject_json_constant(value, label),
            object_pairs_hook=pairs_hook,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise DemoDecisionBridgeError(f"{label} is invalid JSON") from exc


def _reject_json_constant(value: str, label: str) -> object:
    raise DemoDecisionBridgeError(f"{label} contains forbidden numeric constant {value}")


def validate_no_secrets(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if any(fragment in normalized for fragment in _FORBIDDEN_KEYS):
                raise DemoDecisionBridgeError(f"forbidden secret-bearing key at {path}.{key}")
            validate_no_secrets(item, path=f"{path}.{key}")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            validate_no_secrets(item, path=f"{path}[{index}]")
        return
    if isinstance(value, float):
        raise DemoDecisionBridgeError(f"binary float at {path}")
    if isinstance(value, str) and any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise DemoDecisionBridgeError(f"secret-like value at {path}")


def _validate_structure_bounds(
    value: object,
    *,
    path: str = "$",
    depth: int = 0,
    counter: list[int] | None = None,
    node_limit: int = MAX_JSON_NODES,
) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > node_limit:
        raise DemoDecisionBridgeError("JSON node limit exceeded")
    if depth > MAX_JSON_DEPTH:
        raise DemoDecisionBridgeError("JSON depth limit exceeded")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if len(str(key)) > 128:
                raise DemoDecisionBridgeError(f"JSON key is too long at {path}")
            _validate_structure_bounds(
                item,
                path=f"{path}.{key}",
                depth=depth + 1,
                counter=counter,
                node_limit=node_limit,
            )
        return
    if isinstance(value, (tuple, list)):
        if len(value) > node_limit:
            raise DemoDecisionBridgeError(f"JSON array is too large at {path}")
        for index, item in enumerate(value):
            _validate_structure_bounds(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                counter=counter,
                node_limit=node_limit,
            )
        return
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        raise DemoDecisionBridgeError(f"JSON string is too long at {path}")


def _validate_id(value: object, name: str) -> str:
    text = str(value)
    if not _ID.fullmatch(text):
        raise DemoDecisionBridgeError(f"{name} is invalid")
    return text


def _validate_timestamp_evidence(value: object, *, allow_unknown: bool) -> None:
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("timestamp evidence must be an object")
    if set(value) != {"status", "canonical", "source_text", "storage_timestamp"}:
        raise DemoDecisionBridgeError("timestamp evidence fields are invalid")
    status_value = value.get("status")
    if status_value == "SOURCE_REPORTED":
        canonical = canonical_timestamp(str(value.get("canonical", "")))
        if canonical_timestamp(str(value.get("source_text", ""))) != canonical:
            raise DemoDecisionBridgeError("timestamp source text disagrees")
        if value.get("storage_timestamp") != canonical:
            raise DemoDecisionBridgeError("timestamp storage value disagrees")
    elif status_value == "SOURCE_UNKNOWN" and allow_unknown:
        if value.get("canonical") is not None or value.get("source_text") is not None:
            raise DemoDecisionBridgeError("unknown timestamp claims a source time")
        if value.get("storage_timestamp") != "1970-01-01T00:00:00Z":
            raise DemoDecisionBridgeError("unknown timestamp storage value is invalid")
    else:
        raise DemoDecisionBridgeError("timestamp status is invalid")


def _validate_source_ref(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("source_ref must be an object")
    if set(value) != {"kind", "label", "sha256", "byte_count"}:
        raise DemoDecisionBridgeError("source_ref fields are invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(value["kind"])):
        raise DemoDecisionBridgeError("source kind is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(value["label"])):
        raise DemoDecisionBridgeError("source label is invalid")
    if not _SHA256.fullmatch(str(value["sha256"])):
        raise DemoDecisionBridgeError("source digest is invalid")
    byte_count = value["byte_count"]
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        raise DemoDecisionBridgeError("source byte count is invalid")
    return value


def _canonical_source_refs(
    source_refs: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    refs = tuple(
        sorted(
            (dict(_validate_source_ref(ref)) for ref in source_refs),
            key=lambda item: str(item["kind"]),
        )
    )
    if len(refs) != 3 or {str(ref["kind"]) for ref in refs} != {
        "lane_state",
        "heartbeat",
        "orders",
    }:
        raise DemoDecisionBridgeError(
            "exactly one lane_state, heartbeat, and orders source is required"
        )
    return refs


def _validate_decimal_evidence(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("decimal evidence must be an object")
    if set(value) != {"canonical", "source_text", "fidelity"}:
        raise DemoDecisionBridgeError("decimal evidence fields are invalid")
    canonical = str(value["canonical"])
    source = str(value["source_text"])
    if (
        len(canonical) > MAX_DECIMAL_TEXT
        or len(source) > MAX_DECIMAL_TEXT
        or not _CANONICAL_DECIMAL.fullmatch(canonical)
    ):
        raise DemoDecisionBridgeError("decimal evidence text is invalid or too large")
    DecimalFidelity(str(value["fidelity"]))
    parsed_source = _bounded_decimal(source)
    if canonical_decimal_string(parsed_source) != canonical:
        raise DemoDecisionBridgeError("decimal source and canonical value disagree")
    return value


def _bounded_decimal(source: str) -> Decimal:
    if len(source) > MAX_DECIMAL_TEXT:
        raise DemoDecisionBridgeError("decimal source text is too long")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", source):
        raise DemoDecisionBridgeError("decimal source text is invalid")
    try:
        parsed = Decimal(source)
    except InvalidOperation as exc:
        raise DemoDecisionBridgeError("invalid decimal source text") from exc
    exponent = parsed.as_tuple().exponent
    if not parsed.is_finite() or not isinstance(exponent, int) or abs(exponent) > 100:
        raise DemoDecisionBridgeError("decimal exponent is outside the retained bound")
    if len(parsed.as_tuple().digits) > 100:
        raise DemoDecisionBridgeError("decimal precision is outside the retained bound")
    return parsed


def opaque_venue_order_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digest = hashlib.sha256(f"venue-order:{text}".encode()).hexdigest()
    return f"VOH-{digest[:32]}"


_NO_VENUE_ORDER_STAGES = frozenset({"kill_switch", "price_unavailable", "qty_below_step", "place"})


def _venue_order_identity_required(source: Mapping[str, object]) -> bool:
    return not (
        source.get("ok") is False
        and isinstance(source.get("stage"), str)
        and source["stage"] in _NO_VENUE_ORDER_STAGES
    )


def _retained_venue_order_ref(
    source: Mapping[str, object],
    *,
    required: bool,
) -> str | None:
    has_raw = "order_id" in source and source.get("order_id") is not None
    has_ref = "venue_order_ref" in source and source.get("venue_order_ref") is not None
    if has_raw and has_ref:
        raise DemoDecisionBridgeError(
            "observed order identity cannot contain both order_id and venue_order_ref"
        )
    if not has_raw and not has_ref:
        if required:
            raise DemoDecisionBridgeError(
                "successful or created venue order requires order_id or venue_order_ref"
            )
        return None
    if has_ref:
        retained = source["venue_order_ref"]
        if not isinstance(retained, str) or not _VENUE_ORDER_REF.fullmatch(retained):
            raise DemoDecisionBridgeError("venue_order_ref is not a valid opaque order reference")
        return retained
    hashed = opaque_venue_order_id(source["order_id"])
    if hashed is None:
        raise DemoDecisionBridgeError("order_id must be non-empty")
    return hashed


def _retained_signal_ref_sha256(source: Mapping[str, object]) -> str | None:
    has_raw = "signal_ref" in source and source.get("signal_ref") is not None
    has_hash = "signal_ref_sha256" in source and source.get("signal_ref_sha256") is not None
    if has_raw and has_hash:
        raise DemoDecisionBridgeError(
            "observed signal identity cannot contain both signal_ref and signal_ref_sha256"
        )
    if has_hash:
        retained = source["signal_ref_sha256"]
        if not isinstance(retained, str) or not _SHA256.fullmatch(retained):
            raise DemoDecisionBridgeError("signal_ref_sha256 is not a valid opaque hash")
        return retained
    if has_raw:
        return hashlib.sha256(str(source["signal_ref"]).encode()).hexdigest()
    return None


def make_event(
    event_type: EventType | str,
    *,
    logical_key: str,
    occurred_at: str | datetime | None,
    source_ref: Mapping[str, object],
    payload: Mapping[str, object],
    decision_id: str | None = None,
    attempt_id: str | None = None,
) -> dict[str, object]:
    kind = EventType(str(event_type))
    if not logical_key.strip():
        raise DemoDecisionBridgeError("event logical key must be non-empty")
    body: dict[str, object] = {
        "schema": SCHEMA,
        "kind": "EVENT",
        "record_type": RECORD_TYPE,
        "stage": Stage.S3_PAPER_DEMO.value,
        "event_type": kind.value,
        "logical_key": logical_key,
        "occurred_at": timestamp_evidence(occurred_at),
        "source_ref": dict(source_ref),
        "payload": dict(payload),
        "execution_authority": "NONE",
    }
    if decision_id is not None:
        body["decision_id"] = decision_id
    if attempt_id is not None:
        body["attempt_id"] = attempt_id
    validate_no_secrets(body)
    body["event_id"] = stable_id("EVT", body)
    return body


def _require_payload_fields(
    payload: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    if not required.issubset(payload) or set(payload) - allowed:
        raise DemoDecisionBridgeError("event payload fields are invalid")


def _validate_event_payload(
    event_type: EventType,
    payload: Mapping[str, object],
) -> None:
    empty_payloads = {
        EventType.ORDER_ATTEMPTED,
        EventType.ORDER_ACKNOWLEDGED,
        EventType.ORDER_REJECTED,
        EventType.ORDER_CANCELLED,
        EventType.RECONCILIATION_STARTED,
        EventType.RECONCILIATION_CONFIRMED,
        EventType.RECONCILIATION_FAILED,
    }
    if event_type in empty_payloads:
        _require_payload_fields(payload, required=set())
    elif event_type is EventType.BAR_EVALUATED:
        _require_payload_fields(payload, required={"disposition"})
        BarDisposition(str(payload["disposition"]))
    elif event_type is EventType.ORDER_PARTIALLY_FILLED:
        _require_payload_fields(payload, required={"cumulative_quantity"})
        _validate_decimal_evidence(payload["cumulative_quantity"])
    elif event_type is EventType.ORDER_FILLED:
        _require_payload_fields(payload, required={"cumulative_quantity"})
        _validate_decimal_evidence(payload["cumulative_quantity"])
    elif event_type in {
        EventType.POSITION_OPENED,
        EventType.POSITION_REDUCED,
        EventType.POSITION_CLOSED,
    }:
        _require_payload_fields(
            payload,
            required={"position_id", "before_quantity", "after_quantity"},
        )
        _validate_id(payload["position_id"], "position_id")
        _validate_decimal_evidence(payload["before_quantity"])
        _validate_decimal_evidence(payload["after_quantity"])
    elif event_type in {
        EventType.STOP_REQUESTED,
        EventType.STOP_ACTIVE,
        EventType.STOP_TRIGGERED,
        EventType.STOP_CANCELLED,
        EventType.STOP_FAILED,
    }:
        _require_payload_fields(payload, required={"position_id", "stop_id"})
        _validate_id(payload["position_id"], "position_id")
        _validate_id(payload["stop_id"], "stop_id")
    elif event_type is EventType.LEGACY_ORDER_OBSERVED:
        _validate_legacy_attempt(payload)
    elif event_type is EventType.LEGACY_SNAPSHOT_IMPORTED:
        _require_payload_fields(
            payload,
            required={
                "projection_id",
                "projection_status",
                "episode_id",
                "realized_outcome_count",
                "source_label_sha256",
            },
        )
        _validate_id(payload["projection_id"], "projection_id")
        _validate_id(payload["episode_id"], "episode_id")
        if (
            payload["projection_status"] != "OPEN_LEGACY_LIMITED"
            or payload["realized_outcome_count"] != 0
            or not _SHA256.fullmatch(str(payload["source_label_sha256"]))
        ):
            raise DemoDecisionBridgeError("legacy snapshot payload is invalid")
    elif event_type in {EventType.SOURCE_MUTATION, EventType.SOURCE_TRUNCATION}:
        _require_payload_fields(
            payload,
            required={
                "source_kind",
                "prior_sha256",
                "prior_byte_count",
                "current_sha256",
                "current_byte_count",
                "projection_halted",
            },
        )
        if (
            not _SHA256.fullmatch(str(payload["prior_sha256"]))
            or not _SHA256.fullmatch(str(payload["current_sha256"]))
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(payload["source_kind"]))
            or payload["projection_halted"] is not True
        ):
            raise DemoDecisionBridgeError("source incident payload is invalid")
        for key in ("prior_byte_count", "current_byte_count"):
            count = payload[key]
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise DemoDecisionBridgeError("source incident byte count is invalid")
    elif event_type is EventType.EVIDENCE_CONFLICT:
        _require_payload_fields(
            payload,
            required={
                "conflicted_logical_key_sha256",
                "retained_event_sha256",
                "presented_event_sha256",
                "projection_halted",
            },
        )
        if (
            not all(
                _SHA256.fullmatch(str(payload[key]))
                for key in (
                    "conflicted_logical_key_sha256",
                    "retained_event_sha256",
                    "presented_event_sha256",
                )
            )
            or payload["projection_halted"] is not True
        ):
            raise DemoDecisionBridgeError("evidence conflict payload is invalid")


def _validate_legacy_attempt(payload: Mapping[str, object]) -> None:
    required = {
        "decision_id",
        "attempt_id",
        "observation_status",
        "side",
        "recorded_at",
        "venue_order_ref",
        "signal_ref_sha256",
    }
    decimal_fields = {"avg_price", "cum_exec_qty", "fee", "qty", "price"}
    optional = decimal_fields | {"legacy_reconciliation_deltas", "pnl_eligibility"}
    _require_payload_fields(payload, required=required, optional=optional)
    _validate_id(payload["decision_id"], "decision_id")
    _validate_id(payload["attempt_id"], "attempt_id")
    if payload["observation_status"] != "LEGACY_OBSERVED_ONLY":
        raise DemoDecisionBridgeError("legacy attempt observation status is invalid")
    if not re.fullmatch(r"[A-Z_]{1,32}", str(payload["side"])):
        raise DemoDecisionBridgeError("legacy attempt side is invalid")
    _validate_timestamp_evidence(payload["recorded_at"], allow_unknown=True)
    venue_ref = payload["venue_order_ref"]
    if venue_ref is not None and not re.fullmatch(r"VOH-[a-f0-9]{32}", str(venue_ref)):
        raise DemoDecisionBridgeError("opaque venue order reference is invalid")
    signal_ref = payload["signal_ref_sha256"]
    if signal_ref is not None and not _SHA256.fullmatch(str(signal_ref)):
        raise DemoDecisionBridgeError("signal reference digest is invalid")
    for field in decimal_fields & set(payload):
        _validate_decimal_evidence(payload[field])
    deltas = payload.get("legacy_reconciliation_deltas")
    if deltas is None:
        if "pnl_eligibility" in payload:
            raise DemoDecisionBridgeError("PnL eligibility requires retained legacy deltas")
    else:
        if not isinstance(deltas, Mapping) or not deltas:
            raise DemoDecisionBridgeError("legacy reconciliation deltas are invalid")
        for key, value in deltas.items():
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", str(key)):
                raise DemoDecisionBridgeError("legacy reconciliation delta key is invalid")
            _validate_decimal_evidence(value)
        if payload.get("pnl_eligibility") != "INELIGIBLE_ROUNDED_LEGACY_DELTAS":
            raise DemoDecisionBridgeError("legacy deltas cannot be exact PnL evidence")


def _validate_event_identity_fields(
    event_type: EventType,
    event: Mapping[str, object],
) -> None:
    order_events = {
        EventType.ORDER_ATTEMPTED,
        EventType.ORDER_ACKNOWLEDGED,
        EventType.ORDER_REJECTED,
        EventType.ORDER_PARTIALLY_FILLED,
        EventType.ORDER_FILLED,
        EventType.ORDER_CANCELLED,
        EventType.LEGACY_ORDER_OBSERVED,
    }
    attempt_only_events = {
        EventType.RECONCILIATION_STARTED,
        EventType.RECONCILIATION_CONFIRMED,
        EventType.RECONCILIATION_FAILED,
        EventType.POSITION_OPENED,
        EventType.POSITION_REDUCED,
        EventType.POSITION_CLOSED,
    }
    has_decision = "decision_id" in event
    has_attempt = "attempt_id" in event
    if event_type is EventType.BAR_EVALUATED:
        valid = has_decision and not has_attempt
    elif event_type in order_events:
        valid = has_decision and has_attempt
    elif event_type in attempt_only_events:
        valid = has_attempt and not has_decision
    else:
        valid = not has_decision and not has_attempt
    if not valid:
        raise DemoDecisionBridgeError("event identity fields do not match its event type")


def validate_event(event: Mapping[str, object]) -> None:
    required = {
        "schema",
        "kind",
        "event_type",
        "event_id",
        "logical_key",
        "record_type",
        "stage",
        "occurred_at",
        "source_ref",
        "payload",
        "execution_authority",
    }
    optional = {"decision_id", "attempt_id"}
    if not required.issubset(event):
        raise DemoDecisionBridgeError("event envelope is incomplete")
    if set(event) - required - optional:
        raise DemoDecisionBridgeError("event envelope has unsupported fields")
    if event["schema"] != SCHEMA or event["kind"] != "EVENT":
        raise DemoDecisionBridgeError("event schema envelope is invalid")
    if event["record_type"] != RECORD_TYPE or event["stage"] != Stage.S3_PAPER_DEMO.value:
        raise DemoDecisionBridgeError("event store identity is invalid")
    if event["execution_authority"] != "NONE":
        raise DemoDecisionBridgeError("evidence event cannot carry execution authority")
    event_type = EventType(str(event["event_type"]))
    _validate_timestamp_evidence(
        event["occurred_at"],
        allow_unknown=event_type in {EventType.LEGACY_ORDER_OBSERVED, EventType.EVIDENCE_CONFLICT},
    )
    _validate_source_ref(event["source_ref"])
    if not isinstance(event["payload"], Mapping):
        raise DemoDecisionBridgeError("event payload must be an object")
    if not isinstance(event["logical_key"], str) or not event["logical_key"].strip():
        raise DemoDecisionBridgeError("event logical key is invalid")
    if len(event["logical_key"]) > 256:
        raise DemoDecisionBridgeError("event logical key is too long")
    _validate_id(event["event_id"], "event_id")
    if "decision_id" in event:
        _validate_id(event["decision_id"], "decision_id")
    if "attempt_id" in event:
        _validate_id(event["attempt_id"], "attempt_id")
    _validate_event_identity_fields(event_type, event)
    payload = cast(Mapping[str, object], event["payload"])
    _validate_event_payload(event_type, payload)
    if event_type is EventType.LEGACY_ORDER_OBSERVED and (
        payload["decision_id"] != event["decision_id"]
        or payload["attempt_id"] != event["attempt_id"]
    ):
        raise DemoDecisionBridgeError("legacy payload identity does not match the event envelope")
    if event_type in {EventType.SOURCE_MUTATION, EventType.SOURCE_TRUNCATION}:
        source_ref = cast(Mapping[str, object], event["source_ref"])
        if (
            payload["source_kind"] != source_ref["kind"]
            or payload["current_sha256"] != source_ref["sha256"]
            or payload["current_byte_count"] != source_ref["byte_count"]
        ):
            raise DemoDecisionBridgeError(
                "source incident current identity does not match source_ref"
            )
    without_id = dict(event)
    actual_id = str(without_id.pop("event_id"))
    if stable_id("EVT", without_id) != actual_id:
        raise DemoDecisionBridgeError("event id does not match canonical envelope")
    validate_no_secrets(event)
    _validate_structure_bounds(event)


def validate_projection(projection: Mapping[str, object]) -> None:
    required = {
        "schema",
        "kind",
        "projection_id",
        "projection_status",
        "snapshot_consistency",
        "client_idempotency",
        "captured_at",
        "source_refs",
        "episodes",
        "realized_outcomes",
        "realized_outcome_count",
        "wallet_balance_exported",
        "execution_authority",
        "order_capability",
        "limitations",
    }
    if set(projection) != required:
        raise DemoDecisionBridgeError("projection envelope fields are invalid")
    if projection["schema"] != SCHEMA or projection["kind"] != "PROJECTION":
        raise DemoDecisionBridgeError("projection schema envelope is invalid")
    if projection["projection_status"] != "OPEN_LEGACY_LIMITED":
        raise DemoDecisionBridgeError("Stage A projection status is invalid")
    if projection["snapshot_consistency"] != "BEST_EFFORT_MULTI_FILE":
        raise DemoDecisionBridgeError("Stage A snapshot consistency is invalid")
    if projection["client_idempotency"] != "LEGACY_NO_CLIENT_IDEMPOTENCY":
        raise DemoDecisionBridgeError("Stage A idempotency label is invalid")
    if projection["realized_outcomes"] != [] or projection["realized_outcome_count"] != 0:
        raise DemoDecisionBridgeError("legacy Stage A cannot contain realised outcomes")
    if projection["wallet_balance_exported"] is not False:
        raise DemoDecisionBridgeError("exact wallet balance export is forbidden")
    if projection["execution_authority"] != "NONE" or projection["order_capability"] != "DISABLED":
        raise DemoDecisionBridgeError("projection cannot carry order capability")
    _validate_id(projection["projection_id"], "projection_id")
    _validate_timestamp_evidence(projection["captured_at"], allow_unknown=False)
    source_refs = projection["source_refs"]
    if not isinstance(source_refs, list) or len(source_refs) != 3:
        raise DemoDecisionBridgeError("projection must bind exactly three copied sources")
    kinds: set[str] = set()
    for source_ref in source_refs:
        retained = _validate_source_ref(source_ref)
        kinds.add(str(retained["kind"]))
    if kinds != {"lane_state", "heartbeat", "orders"}:
        raise DemoDecisionBridgeError("projection copied-source kinds are invalid")
    if source_refs != sorted(source_refs, key=lambda item: str(item["kind"])):
        raise DemoDecisionBridgeError("projection source references are not canonical")
    episodes = projection["episodes"]
    if not isinstance(episodes, list) or len(episodes) != 1:
        raise DemoDecisionBridgeError("Stage A requires exactly one incomplete open episode")
    _validate_legacy_episode(episodes[0])
    episode = cast(Mapping[str, object], episodes[0])
    attempts = cast(list[Mapping[str, object]], episode["attempts"])
    projection_seed = {
        "source_refs": source_refs,
        "captured_at": cast(Mapping[str, object], projection["captured_at"])["canonical"],
        "position_base": episode["position_base"],
        "attempt_ids": [attempt["attempt_id"] for attempt in attempts],
    }
    if projection["projection_id"] != stable_id("PRJ", projection_seed):
        raise DemoDecisionBridgeError("projection id does not match the fixed projection seed")
    if episode["episode_id"] != stable_id("EPIS", projection_seed):
        raise DemoDecisionBridgeError("episode id does not match the fixed projection seed")
    if projection["limitations"] != list(LEGACY_LIMITATIONS):
        raise DemoDecisionBridgeError("Stage A limitation inventory is invalid")
    validate_no_secrets(projection)
    _validate_structure_bounds(projection, node_limit=MAX_PROJECTION_JSON_NODES)


def _validate_legacy_episode(value: object) -> None:
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("legacy episode must be an object")
    required = {
        "episode_id",
        "state",
        "position_base",
        "entry_price",
        "mark_price",
        "stop_observation",
        "attempts",
        "realized_outcomes",
        "realized_outcome_count",
        "outcome_eligibility",
    }
    if set(value) != required:
        raise DemoDecisionBridgeError("legacy episode fields are invalid")
    _validate_id(value["episode_id"], "episode_id")
    if (
        value["state"] != "OPEN_INCOMPLETE"
        or value["realized_outcomes"] != []
        or value["realized_outcome_count"] != 0
        or value["outcome_eligibility"] != "NOT_AVAILABLE_LEGACY_OPEN"
    ):
        raise DemoDecisionBridgeError("legacy episode state or outcome contract is invalid")
    _validate_decimal_evidence(value["position_base"])
    for field in ("entry_price", "mark_price"):
        if value[field] is not None:
            _validate_decimal_evidence(value[field])
    attempts = value["attempts"]
    if not isinstance(attempts, list) or len(attempts) > MAX_JSONL_ROWS:
        raise DemoDecisionBridgeError("legacy attempt inventory is invalid")
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            raise DemoDecisionBridgeError("legacy attempt must be an object")
        _validate_legacy_attempt(attempt)
    _validate_stop_observation(value["stop_observation"])


def _validate_stop_observation(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("stop observation must be an object")
    decimal_fields = {
        "risk_boundary_price",
        "trigger_price",
        "base_qty",
        "position_base_qty",
        "risk_fraction",
        "price_tick",
    }
    if set(value) - decimal_fields - {"state", "venue_order_ref"}:
        raise DemoDecisionBridgeError("stop observation fields are invalid")
    if "state" not in value or "venue_order_ref" not in value:
        raise DemoDecisionBridgeError("stop observation is incomplete")
    if not re.fullmatch(r"[A-Z_]{1,64}", str(value["state"])):
        raise DemoDecisionBridgeError("stop observation state is invalid")
    venue_ref = value["venue_order_ref"]
    if venue_ref is not None and not re.fullmatch(r"VOH-[a-f0-9]{32}", str(venue_ref)):
        raise DemoDecisionBridgeError("stop opaque venue order reference is invalid")
    for field in decimal_fields & set(value):
        _validate_decimal_evidence(value[field])


def canonical_jsonl(events: Iterable[Mapping[str, object]]) -> bytes:
    rows: list[str] = []
    for event in events:
        validate_event(event)
        rows.append(canonical_json(event))
    return (("\n".join(rows) + "\n") if rows else "").encode("utf-8")


def _decimal_fidelity(key: str, value: object) -> DecimalFidelity:
    if isinstance(value, NumericLexeme):
        normalized = key.upper()
        if normalized.startswith(("USDT", "USD", "QUOTE")):
            return DecimalFidelity.LEGACY_ROUNDED_4DP
        if normalized.endswith("_DELTA"):
            return DecimalFidelity.LEGACY_ROUNDED_8DP
        return DecimalFidelity.UNKNOWN_PRECISION
    if isinstance(value, str):
        return DecimalFidelity.UNKNOWN_PRECISION
    return DecimalFidelity.UNKNOWN_PRECISION


def _optional_decimal(source: Mapping[str, object], key: str) -> dict[str, str] | None:
    if key not in source:
        return None
    value = source.get(key)
    if not isinstance(value, (str, NumericLexeme, int, Decimal)) or isinstance(value, bool):
        raise DemoDecisionBridgeError(f"observed decimal {key} has invalid type")
    try:
        return decimal_evidence(value, _decimal_fidelity(key, value))
    except DemoDecisionBridgeError as exc:
        raise DemoDecisionBridgeError(f"observed decimal {key} is invalid: {exc}") from exc


def _sanitize_stop(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError("present resting_stop must be an object")
    state = value.get("state")
    if not isinstance(state, str) or not re.fullmatch(r"[A-Z_]{1,64}", state):
        raise DemoDecisionBridgeError("present resting_stop has an invalid state")
    result: dict[str, object] = {"state": state}
    result["venue_order_ref"] = _retained_venue_order_ref(value, required=True)
    for key in (
        "risk_boundary_price",
        "trigger_price",
        "base_qty",
        "position_base_qty",
        "risk_fraction",
        "price_tick",
    ):
        number = _optional_decimal(value, key)
        if number is not None:
            result[key] = number
    return result


def _sanitize_order(
    order: Mapping[str, object],
    *,
    index: int,
    source_ref: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    if "recorded_at" in order and not isinstance(order["recorded_at"], str):
        raise DemoDecisionBridgeError("present recorded_at must be a timestamp string")
    recorded_raw = order.get("recorded_at")
    recorded_at = cast(str | None, recorded_raw)
    recorded = timestamp_evidence(recorded_at)
    side = str(order.get("side") or "UNKNOWN").upper()
    signal_hash = _retained_signal_ref_sha256(order)
    order_canonical = canonical_json(order)
    order_source_ref = {
        "kind": "order-record",
        "label": str(source_ref["label"]),
        "sha256": hashlib.sha256(order_canonical.encode("utf-8")).hexdigest(),
        "byte_count": len(order_canonical.encode("utf-8")),
    }
    decision_seed = {
        "source_sha256": order_source_ref["sha256"],
        "order_index": index,
        "source_time": recorded,
        "side": side,
        "signal_ref_sha256": signal_hash,
    }
    decision_id = stable_id("DEC", decision_seed)
    venue_order_ref = _retained_venue_order_ref(
        order,
        required=_venue_order_identity_required(order),
    )
    attempt_seed = {
        "decision_id": decision_id,
        "venue_order_ref": venue_order_ref,
        "side": side,
        "source_time": recorded,
    }
    attempt_id = stable_id("ATT", attempt_seed)
    sanitized: dict[str, object] = {
        "decision_id": decision_id,
        "attempt_id": attempt_id,
        "observation_status": "LEGACY_OBSERVED_ONLY",
        "side": side,
        "recorded_at": recorded,
        "venue_order_ref": attempt_seed["venue_order_ref"],
        "signal_ref_sha256": signal_hash,
    }
    for key in ("avg_price", "cum_exec_qty", "fee", "qty", "price"):
        number = _optional_decimal(order, key)
        if number is not None:
            sanitized[key] = number
    reconciliation = order.get("reconcile")
    if "reconcile" in order:
        if not isinstance(reconciliation, Mapping) or not reconciliation:
            raise DemoDecisionBridgeError("present reconcile must be a non-empty object")
        deltas: dict[str, object] = {}
        for key in sorted(str(item) for item in reconciliation):
            number = _optional_decimal(reconciliation, key)
            if number is not None:
                deltas[key] = number
        if not deltas:
            raise DemoDecisionBridgeError("present reconcile retained no decimal deltas")
        sanitized["legacy_reconciliation_deltas"] = deltas
        sanitized["pnl_eligibility"] = "INELIGIBLE_ROUNDED_LEGACY_DELTAS"
    event = make_event(
        EventType.LEGACY_ORDER_OBSERVED,
        logical_key=f"legacy-order:{canonical_digest(decision_seed)}",
        occurred_at=recorded_at,
        source_ref=order_source_ref,
        payload=sanitized,
        decision_id=decision_id,
        attempt_id=attempt_id,
    )
    return sanitized, event


def build_legacy_projection(
    lane_state: Mapping[str, object],
    heartbeat: Mapping[str, object],
    orders: Sequence[Mapping[str, object]],
    *,
    source_refs: Sequence[Mapping[str, object]],
    captured_at: str | datetime,
    source_label: str | None = None,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    captured = timestamp_evidence(captured_at)
    state_base = _optional_decimal(lane_state, "lane_base")
    if state_base is None or Decimal(state_base["canonical"]) <= 0:
        raise DemoDecisionBridgeError(
            "Stage A only supports a copied current snapshot with positive open exposure"
        )
    refs = list(_canonical_source_refs(source_refs))
    orders_ref = next((ref for ref in refs if ref["kind"] == "orders"), None)
    if orders_ref is None:
        raise DemoDecisionBridgeError("orders source reference is missing")
    bound_source_label = source_label or str(orders_ref["label"]).removesuffix(".orders")
    if not _LABEL.fullmatch(bound_source_label):
        raise DemoDecisionBridgeError("source label must be opaque and filesystem-neutral")

    sanitized_orders: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    for index, order in enumerate(orders):
        sanitized, event = _sanitize_order(
            order,
            index=index,
            source_ref=orders_ref,
        )
        sanitized_orders.append(sanitized)
        events.append(event)

    entry_price = _optional_decimal(lane_state, "entry_price")
    mark_price = _optional_decimal(heartbeat, "mark_price")
    stop: dict[str, object] | None = None
    if "resting_stop" in lane_state:
        stop = _sanitize_stop(lane_state["resting_stop"])
    elif "resting_stop" in heartbeat:
        stop = _sanitize_stop(heartbeat["resting_stop"])
    projection_seed = {
        "source_refs": refs,
        "captured_at": captured["canonical"],
        "position_base": state_base,
        "attempt_ids": [item["attempt_id"] for item in sanitized_orders],
    }
    projection_id = stable_id("PRJ", projection_seed)
    episode_id = stable_id("EPIS", projection_seed)
    episode: dict[str, object] = {
        "episode_id": episode_id,
        "state": "OPEN_INCOMPLETE",
        "position_base": state_base,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "stop_observation": stop,
        "attempts": sanitized_orders,
        "realized_outcomes": [],
        "realized_outcome_count": 0,
        "outcome_eligibility": "NOT_AVAILABLE_LEGACY_OPEN",
    }
    projection: dict[str, object] = {
        "schema": SCHEMA,
        "kind": "PROJECTION",
        "projection_id": projection_id,
        "projection_status": "OPEN_LEGACY_LIMITED",
        "snapshot_consistency": "BEST_EFFORT_MULTI_FILE",
        "client_idempotency": "LEGACY_NO_CLIENT_IDEMPOTENCY",
        "captured_at": captured,
        "source_refs": refs,
        "episodes": [episode],
        "realized_outcomes": [],
        "realized_outcome_count": 0,
        "wallet_balance_exported": False,
        "execution_authority": "NONE",
        "order_capability": "DISABLED",
        "limitations": list(LEGACY_LIMITATIONS),
    }
    snapshot_event = make_event(
        EventType.LEGACY_SNAPSHOT_IMPORTED,
        logical_key=f"legacy-snapshot:{canonical_digest(projection_seed)}",
        occurred_at=str(captured["canonical"]),
        source_ref={
            "kind": "capture",
            "label": stable_id("SRC", refs),
            "sha256": canonical_digest(refs),
            "byte_count": sum(int(str(ref["byte_count"])) for ref in refs),
        },
        payload={
            "projection_id": projection_id,
            "projection_status": "OPEN_LEGACY_LIMITED",
            "episode_id": episode_id,
            "realized_outcome_count": 0,
            "source_label_sha256": hashlib.sha256(bound_source_label.encode()).hexdigest(),
        },
    )
    events.append(snapshot_event)
    validate_projection(projection)
    return projection, tuple(events)


def reduce_events(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Validate future event ordering and reduce attempts, positions, reconciliation, and stops."""

    retained_by_id: dict[str, str] = {}
    retained_by_key: dict[str, str] = {}
    decisions: dict[str, str] = {}
    attempts: dict[str, str] = {}
    reconciliation: dict[str, str] = {}
    positions: dict[str, str] = {}
    stops: dict[str, str] = {}
    partials: dict[str, Decimal] = {}
    executed_quantities: dict[str, Decimal] = {}
    position_quantities: dict[str, Decimal] = {}
    attempt_decisions: dict[str, str] = {}
    attempt_positions: dict[str, str] = {}
    stop_positions: dict[str, str] = {}
    consumed_position_attempts: set[str] = set()
    previous_time: datetime | None = None

    for raw in events:
        event = dict(raw)
        validate_event(event)
        event_type = EventType(str(event["event_type"]))
        digest = canonical_digest(event)
        event_id = str(event["event_id"])
        logical_key = str(event["logical_key"])
        if event_id in retained_by_id:
            if retained_by_id[event_id] == digest:
                continue
            raise DemoDecisionBridgeError("repeated event id has conflicting content")
        if logical_key in retained_by_key and retained_by_key[logical_key] != digest:
            raise EvidenceConflictError(
                _conflict_event(
                    logical_key,
                    retained_by_key[logical_key],
                    digest,
                    cast(Mapping[str, object], event["occurred_at"]).get("canonical"),
                )
            )
        retained_by_id[event_id] = digest
        retained_by_key[logical_key] = digest
        occurred_raw = cast(Mapping[str, object], event["occurred_at"]).get("canonical")
        if occurred_raw is None:
            if event_type not in {
                EventType.LEGACY_ORDER_OBSERVED,
                EventType.EVIDENCE_CONFLICT,
            }:
                raise DemoDecisionBridgeError(
                    f"{event_type.value} requires a source-reported occurred_at"
                )
        else:
            occurred = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00"))
            if previous_time is not None and occurred < previous_time:
                raise DemoDecisionBridgeError("events are reordered by occurred_at")
            previous_time = occurred
        payload = cast(Mapping[str, object], event["payload"])
        decision_id = str(event.get("decision_id") or "")
        attempt_id = str(event.get("attempt_id") or "")

        if event_type is EventType.BAR_EVALUATED:
            if not decision_id:
                raise DemoDecisionBridgeError("BAR_EVALUATED requires decision_id")
            disposition = BarDisposition(str(payload.get("disposition")))
            if decision_id in decisions:
                raise DemoDecisionBridgeError("decision_id cannot be evaluated more than once")
            decisions[decision_id] = disposition.value
        elif event_type is EventType.ORDER_ATTEMPTED:
            if not decision_id or decision_id not in decisions or not attempt_id:
                raise DemoDecisionBridgeError("ORDER_ATTEMPTED is missing its evaluated decision")
            if decisions[decision_id] not in EXECUTION_ELIGIBLE_DISPOSITIONS:
                raise DemoDecisionBridgeError(
                    "ORDER_ATTEMPTED cannot follow a non-executable bar disposition"
                )
            if attempt_id in attempts or attempt_id in attempt_decisions:
                raise DemoDecisionBridgeError("attempt_id cannot be reused")
            attempts[attempt_id] = "ATTEMPTED"
            attempt_decisions[attempt_id] = decision_id
        elif event_type is EventType.ORDER_ACKNOWLEDGED:
            _require_attempt_identity(attempt_decisions, attempt_id, decision_id, event_type.value)
            _require_state(attempts, attempt_id, {"ATTEMPTED"}, event_type.value)
            attempts[attempt_id] = "ACKNOWLEDGED"
        elif event_type is EventType.ORDER_REJECTED:
            _require_attempt_identity(attempt_decisions, attempt_id, decision_id, event_type.value)
            _require_state(attempts, attempt_id, {"ATTEMPTED", "ACKNOWLEDGED"}, event_type.value)
            attempts[attempt_id] = "REJECTED"
        elif event_type is EventType.ORDER_PARTIALLY_FILLED:
            _require_attempt_identity(attempt_decisions, attempt_id, decision_id, event_type.value)
            _require_state(
                attempts, attempt_id, {"ACKNOWLEDGED", "PARTIALLY_FILLED"}, event_type.value
            )
            quantity = _payload_decimal(payload, "cumulative_quantity")
            if quantity <= partials.get(attempt_id, Decimal(0)):
                raise DemoDecisionBridgeError("partial-fill cumulative quantity must increase")
            partials[attempt_id] = quantity
            attempts[attempt_id] = "PARTIALLY_FILLED"
        elif event_type is EventType.ORDER_FILLED:
            _require_attempt_identity(attempt_decisions, attempt_id, decision_id, event_type.value)
            _require_state(
                attempts, attempt_id, {"ACKNOWLEDGED", "PARTIALLY_FILLED"}, event_type.value
            )
            quantity = _payload_decimal(payload, "cumulative_quantity")
            if quantity < partials.get(attempt_id, Decimal(0)):
                raise DemoDecisionBridgeError(
                    "filled cumulative quantity cannot be below the retained partial fill"
                )
            executed_quantities[attempt_id] = quantity
            attempts[attempt_id] = "FILLED"
        elif event_type is EventType.ORDER_CANCELLED:
            _require_attempt_identity(attempt_decisions, attempt_id, decision_id, event_type.value)
            _require_state(
                attempts, attempt_id, {"ACKNOWLEDGED", "PARTIALLY_FILLED"}, event_type.value
            )
            partial_quantity = partials.get(attempt_id, Decimal(0))
            if partial_quantity > 0:
                executed_quantities[attempt_id] = partial_quantity
                attempts[attempt_id] = "CANCELLED_WITH_FILL_PENDING_RECONCILIATION"
            else:
                attempts[attempt_id] = "CANCELLED"
        elif event_type is EventType.RECONCILIATION_STARTED:
            _require_state(
                attempts,
                attempt_id,
                {"FILLED", "CANCELLED_WITH_FILL_PENDING_RECONCILIATION"},
                event_type.value,
            )
            if attempt_id in reconciliation:
                raise DemoDecisionBridgeError("reconciliation cannot be restarted or overwritten")
            reconciliation[attempt_id] = "PENDING"
        elif event_type is EventType.RECONCILIATION_CONFIRMED:
            _require_state(reconciliation, attempt_id, {"PENDING"}, event_type.value)
            reconciliation[attempt_id] = "CONFIRMED"
        elif event_type is EventType.RECONCILIATION_FAILED:
            _require_state(reconciliation, attempt_id, {"PENDING"}, event_type.value)
            reconciliation[attempt_id] = "FAILED"
        elif event_type in {
            EventType.POSITION_OPENED,
            EventType.POSITION_REDUCED,
            EventType.POSITION_CLOSED,
        }:
            position_id = str(payload.get("position_id") or "")
            if not position_id:
                raise DemoDecisionBridgeError(f"{event_type.value} requires position_id")
            _require_state(reconciliation, attempt_id, {"CONFIRMED"}, event_type.value)
            executed_quantity = executed_quantities.get(attempt_id)
            if executed_quantity is None:
                raise DemoDecisionBridgeError(
                    f"{event_type.value} requires a retained executed quantity"
                )
            before_quantity = _payload_nonnegative_decimal(payload, "before_quantity")
            after_quantity = _payload_nonnegative_decimal(payload, "after_quantity")
            decision_for_attempt = attempt_decisions.get(attempt_id)
            if decision_for_attempt is None:
                raise DemoDecisionBridgeError(f"{event_type.value} requires a known attempt")
            if attempt_id in consumed_position_attempts:
                raise DemoDecisionBridgeError(
                    "a reconciled attempt can support only one position transition"
                )
            attempt_disposition = decisions[decision_for_attempt]
            if event_type is EventType.POSITION_OPENED:
                if attempt_disposition != BarDisposition.ENTRY_SIGNAL.value:
                    raise DemoDecisionBridgeError("POSITION_OPENED requires an entry decision")
                if position_id in positions:
                    raise DemoDecisionBridgeError("position was opened more than once")
                if attempt_id in attempt_positions:
                    raise DemoDecisionBridgeError("attempt is already associated with a position")
                if before_quantity != 0 or after_quantity != executed_quantity:
                    raise DemoDecisionBridgeError(
                        "POSITION_OPENED before/after delta disagrees with the executed quantity"
                    )
                positions[position_id] = "OPEN"
                position_quantities[position_id] = after_quantity
                attempt_positions[attempt_id] = position_id
            else:
                if attempt_disposition != BarDisposition.EXIT_SIGNAL.value:
                    raise DemoDecisionBridgeError(f"{event_type.value} requires an exit decision")
                _require_state(positions, position_id, {"OPEN"}, event_type.value)
                prior_position = attempt_positions.get(attempt_id)
                if prior_position is not None and prior_position != position_id:
                    raise DemoDecisionBridgeError(
                        "attempt cannot be associated with multiple positions"
                    )
                attempt_positions[attempt_id] = position_id
                if position_quantities.get(position_id) != before_quantity:
                    raise DemoDecisionBridgeError(
                        f"{event_type.value} before quantity disagrees with retained position"
                    )
                if event_type is EventType.POSITION_REDUCED:
                    if (
                        after_quantity <= 0
                        or after_quantity >= before_quantity
                        or before_quantity - after_quantity != executed_quantity
                    ):
                        raise DemoDecisionBridgeError(
                            "POSITION_REDUCED delta disagrees with the executed quantity"
                        )
                    positions[position_id] = "OPEN"
                    position_quantities[position_id] = after_quantity
                else:
                    if after_quantity != 0 or before_quantity != executed_quantity:
                        raise DemoDecisionBridgeError(
                            "POSITION_CLOSED delta disagrees with the executed quantity"
                        )
                    pending_stop = any(
                        stop_positions[stop_id] == position_id
                        and stop_state in {"REQUESTED", "ACTIVE"}
                        for stop_id, stop_state in stops.items()
                    )
                    positions[position_id] = (
                        "CLOSED_PENDING_STOP_TERMINATION" if pending_stop else "CLOSED"
                    )
                    position_quantities[position_id] = Decimal(0)
            consumed_position_attempts.add(attempt_id)
        elif event_type in {
            EventType.STOP_REQUESTED,
            EventType.STOP_ACTIVE,
            EventType.STOP_TRIGGERED,
            EventType.STOP_CANCELLED,
            EventType.STOP_FAILED,
        }:
            stop_id = str(payload.get("stop_id") or "")
            position_id = str(payload.get("position_id") or "")
            if not stop_id or not position_id:
                raise DemoDecisionBridgeError(
                    f"{event_type.value} requires stop_id and position_id"
                )
            if event_type is EventType.STOP_REQUESTED:
                _require_state(positions, position_id, {"OPEN"}, event_type.value)
                if stop_id in stops or stop_id in stop_positions:
                    raise DemoDecisionBridgeError("stop was requested more than once")
                stops[stop_id] = "REQUESTED"
                stop_positions[stop_id] = position_id
            elif event_type is EventType.STOP_ACTIVE:
                _require_stop_position(
                    stop_positions, stops, stop_id, position_id, {"REQUESTED"}, event_type.value
                )
                _require_state(positions, position_id, {"OPEN"}, event_type.value)
                _require_state(stops, stop_id, {"REQUESTED"}, event_type.value)
                stops[stop_id] = "ACTIVE"
            else:
                allowed = (
                    {"ACTIVE"}
                    if event_type in {EventType.STOP_TRIGGERED, EventType.STOP_CANCELLED}
                    else {"REQUESTED", "ACTIVE"}
                )
                _require_stop_position(
                    stop_positions, stops, stop_id, position_id, allowed, event_type.value
                )
                allowed_position_states = {"OPEN"}
                if event_type in {EventType.STOP_CANCELLED, EventType.STOP_FAILED}:
                    allowed_position_states.add("CLOSED_PENDING_STOP_TERMINATION")
                _require_state(
                    positions,
                    position_id,
                    allowed_position_states,
                    event_type.value,
                )
                stops[stop_id] = event_type.value.removeprefix("STOP_")
                if positions[position_id] == "CLOSED_PENDING_STOP_TERMINATION" and not any(
                    stop_positions[retained_stop_id] == position_id
                    and retained_state in {"REQUESTED", "ACTIVE"}
                    for retained_stop_id, retained_state in stops.items()
                ):
                    positions[position_id] = "CLOSED"
        elif event_type is EventType.EVIDENCE_CONFLICT:
            raise EvidenceConflictError(event)
        elif event_type in {EventType.SOURCE_MUTATION, EventType.SOURCE_TRUNCATION}:
            raise DemoDecisionBridgeError(f"{event_type.value} halts the projection")

    return {
        "schema": SCHEMA,
        "kind": "REDUCED_STATE",
        "decisions": dict(sorted(decisions.items())),
        "attempts": dict(sorted(attempts.items())),
        "reconciliation": dict(sorted(reconciliation.items())),
        "positions": dict(sorted(positions.items())),
        "stops": dict(sorted(stops.items())),
        "attempt_decisions": dict(sorted(attempt_decisions.items())),
        "attempt_positions": dict(sorted(attempt_positions.items())),
        "stop_positions": dict(sorted(stop_positions.items())),
        "executed_quantities": {
            key: canonical_decimal_string(value)
            for key, value in sorted(executed_quantities.items())
        },
        "position_quantities": {
            key: canonical_decimal_string(value)
            for key, value in sorted(position_quantities.items())
        },
        "event_count": len(retained_by_id),
        "execution_authority": "NONE",
    }


def _require_state(
    states: Mapping[str, str],
    key: str,
    allowed: set[str],
    event_type: str,
) -> None:
    if not key or states.get(key) not in allowed:
        raise DemoDecisionBridgeError(f"{event_type} is missing or violates its predecessor")


def _require_attempt_identity(
    attempt_decisions: Mapping[str, str],
    attempt_id: str,
    decision_id: str,
    event_type: str,
) -> None:
    if not attempt_id or not decision_id or attempt_decisions.get(attempt_id) != decision_id:
        raise DemoDecisionBridgeError(
            f"{event_type} attempt_id and decision_id do not match the retained attempt"
        )


def _require_stop_position(
    stop_positions: Mapping[str, str],
    stops: Mapping[str, str],
    stop_id: str,
    position_id: str,
    allowed: set[str],
    event_type: str,
) -> None:
    if stop_positions.get(stop_id) != position_id or stops.get(stop_id) not in allowed:
        raise DemoDecisionBridgeError(
            f"{event_type} stop_id and position_id do not match the retained stop"
        )


def _payload_decimal(payload: Mapping[str, object], key: str) -> Decimal:
    value = payload.get(key)
    if not isinstance(value, Mapping) or "canonical" not in value:
        raise DemoDecisionBridgeError(f"{key} decimal evidence is missing")
    try:
        parsed = Decimal(str(value["canonical"]))
    except InvalidOperation as exc:
        raise DemoDecisionBridgeError(f"{key} decimal evidence is invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise DemoDecisionBridgeError(f"{key} must be positive and finite")
    return parsed


def _payload_nonnegative_decimal(
    payload: Mapping[str, object],
    key: str,
) -> Decimal:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise DemoDecisionBridgeError(f"{key} decimal evidence is missing")
    _validate_decimal_evidence(value)
    parsed = Decimal(str(value["canonical"]))
    if not parsed.is_finite() or parsed < 0:
        raise DemoDecisionBridgeError(f"{key} must be non-negative and finite")
    return parsed


def _conflict_event(
    logical_key: str,
    retained_digest: str,
    presented_digest: str,
    occurred_at: object,
) -> dict[str, object]:
    payload = {
        "conflicted_logical_key_sha256": hashlib.sha256(logical_key.encode()).hexdigest(),
        "retained_event_sha256": retained_digest,
        "presented_event_sha256": presented_digest,
        "projection_halted": True,
    }
    return make_event(
        EventType.EVIDENCE_CONFLICT,
        logical_key=f"conflict:{canonical_digest(payload)}",
        occurred_at=str(occurred_at) if occurred_at is not None else None,
        source_ref={
            "kind": "retained-ledger",
            "label": "private-evidence-ledger",
            "sha256": retained_digest,
            "byte_count": 0,
        },
        payload=payload,
    )


def validate_source_progress(
    previous_orders: Mapping[str, object],
    current_orders_bytes: bytes,
) -> str | None:
    previous_size = int(str(previous_orders["byte_count"]))
    previous_digest = str(previous_orders["sha256"])
    if len(current_orders_bytes) < previous_size:
        return EventType.SOURCE_TRUNCATION.value
    prefix_digest = hashlib.sha256(current_orders_bytes[:previous_size]).hexdigest()
    if prefix_digest != previous_digest:
        return EventType.SOURCE_MUTATION.value
    return None


def _source_incident_event(
    incident_type: str,
    *,
    prior: Mapping[str, object],
    current: Mapping[str, object],
    captured_at: str,
) -> dict[str, object]:
    payload = {
        "source_kind": str(current["kind"]),
        "prior_sha256": str(prior["sha256"]),
        "prior_byte_count": int(str(prior["byte_count"])),
        "current_sha256": str(current["sha256"]),
        "current_byte_count": int(str(current["byte_count"])),
        "projection_halted": True,
    }
    return make_event(
        EventType(incident_type),
        logical_key=f"source-incident:{canonical_digest(payload)}",
        occurred_at=captured_at,
        source_ref=current,
        payload=payload,
    )


def _active_root(repo_root: Path) -> Path:
    return (repo_root.resolve() / ACTIVE_DEMO_LANE).resolve(strict=False)


def _reject_symlink_ancestors(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    chain = [absolute, *absolute.parents]
    for component in reversed(chain):
        if component.is_symlink():
            raise DemoDecisionBridgeError(f"{label} cannot contain symlink ancestors")


def _reject_active_path(path: Path, repo_root: Path) -> None:
    resolved = path.resolve(strict=False)
    active = _active_root(repo_root)
    if resolved == active or resolved.is_relative_to(active):
        raise DemoDecisionBridgeError("active demo-lane paths are forbidden")


def read_source_copy(path: Path, *, kind: str, source_label: str, repo_root: Path) -> SourceCopy:
    if not _LABEL.fullmatch(source_label):
        raise DemoDecisionBridgeError("source label must be opaque and filesystem-neutral")
    _reject_symlink_ancestors(path, label="source copy path")
    _reject_active_path(path, repo_root)
    if path.is_symlink():
        raise DemoDecisionBridgeError("source copy cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DemoDecisionBridgeError(f"{kind} source copy cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DemoDecisionBridgeError("source copy must be a single-link regular file")
        byte_limit = MAX_ORDERS_BYTES if kind == "orders" else MAX_SNAPSHOT_BYTES
        if before.st_size > byte_limit:
            raise DemoDecisionBridgeError(f"{kind} source copy exceeds its byte limit")
        first = _read_descriptor(descriptor, max_bytes=byte_limit)
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = _read_descriptor(descriptor, max_bytes=byte_limit)
        after = os.fstat(descriptor)
        path_after = path.stat(follow_symlinks=False)
        if before.st_dev != path_after.st_dev or before.st_ino != path_after.st_ino:
            raise DemoDecisionBridgeError(
                "SOURCE_MUTATION: source path identity changed during read"
            )
        if first != second or (before.st_size, before.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            incident = "SOURCE_TRUNCATION" if len(second) < len(first) else "SOURCE_MUTATION"
            raise DemoDecisionBridgeError(f"{incident}: source changed during read")
    finally:
        os.close(descriptor)
    return SourceCopy(
        kind=kind,
        label=f"{source_label}.{kind}",
        data=first,
        sha256=hashlib.sha256(first).hexdigest(),
        byte_count=len(first),
    )


def _read_descriptor(descriptor: int, *, max_bytes: int | None = None) -> bytes:
    chunks: list[bytes] = []
    retained = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        retained += len(chunk)
        if max_bytes is not None and retained > max_bytes:
            raise DemoDecisionBridgeError("file exceeds retained byte limit")
        chunks.append(chunk)


def prepare_private_output_dir(path: Path, *, repo_root: Path) -> Path:
    _reject_active_path(path, repo_root)
    root = repo_root.resolve()
    raw_allowed = root / PRIVATE_EVIDENCE_ROOT
    _reject_symlink_ancestors(raw_allowed, label="private evidence root")
    current_parent = root
    for part in PRIVATE_EVIDENCE_ROOT.parts:
        current_parent = current_parent / part
        if current_parent.exists() and current_parent.is_symlink():
            raise DemoDecisionBridgeError("private evidence root cannot contain symlinks")
    if raw_allowed.exists():
        if not raw_allowed.is_dir() or stat.S_IMODE(raw_allowed.stat().st_mode) != 0o700:
            raise DemoDecisionBridgeError(
                "private artifacts/evidence/private_demo root must be a real 0700 directory"
            )
    else:
        artifacts_parent = raw_allowed.parent
        if not artifacts_parent.exists():
            artifacts_parent.mkdir(parents=True)
            _fsync_directory(artifacts_parent.parent)
        raw_allowed.mkdir(mode=0o700)
        os.chmod(raw_allowed, 0o700)
        if stat.S_IMODE(raw_allowed.stat(follow_symlinks=False).st_mode) != 0o700:
            raise DemoDecisionBridgeError("new private evidence root is not exactly 0700")
        _fsync_directory(raw_allowed.parent)
    allowed = raw_allowed.resolve()
    if not allowed.is_relative_to(root):
        raise DemoDecisionBridgeError("private evidence root escapes the repository")
    candidate = path if path.is_absolute() else root / path
    _reject_symlink_ancestors(candidate, label="private output path")
    resolved = candidate.resolve(strict=False)
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise DemoDecisionBridgeError(
            "private output must be below artifacts/evidence/private_demo"
        )
    if candidate.exists() and candidate.is_symlink():
        raise DemoDecisionBridgeError("private output cannot be a symlink")
    relative = resolved.relative_to(allowed)
    current = allowed
    for part in relative.parts:
        current = current / part
        if current.exists():
            if current.is_symlink() or not current.is_dir():
                raise DemoDecisionBridgeError("private output path is not a real directory")
            if stat.S_IMODE(current.stat().st_mode) != 0o700:
                raise DemoDecisionBridgeError("existing private output directories must be 0700")
        else:
            current.mkdir(mode=0o700)
            os.chmod(current, 0o700)
            if stat.S_IMODE(current.stat(follow_symlinks=False).st_mode) != 0o700:
                raise DemoDecisionBridgeError("new private output directory is not exactly 0700")
            _fsync_directory(current.parent)
    return resolved


@contextmanager
def _private_lock(output_dir: Path) -> Iterator[None]:
    lock_path = output_dir / ".bridge.lock"
    existed = lock_path.exists()
    _assert_private_file(lock_path)
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise DemoDecisionBridgeError("bridge lock cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise DemoDecisionBridgeError("bridge lock must be a single-link regular file")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise DemoDecisionBridgeError("bridge lock must have 0600 permissions")
        if not existed:
            os.fsync(descriptor)
            _fsync_directory(output_dir)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _assert_private_file(path: Path, *, may_not_exist: bool = True) -> None:
    if path.is_symlink():
        raise DemoDecisionBridgeError("private evidence file cannot be a symlink")
    if not path.exists():
        if may_not_exist:
            return
        raise DemoDecisionBridgeError("private evidence file is missing")
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DemoDecisionBridgeError("private evidence file must be a single-link regular file")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise DemoDecisionBridgeError("private evidence files must have 0600 permissions")


def _fsync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _safe_write_atomic(path: Path, payload: bytes, *, create_only: bool = False) -> None:
    _assert_private_file(path)
    if create_only and path.exists():
        if _read_private(path) != payload:
            raise DemoDecisionBridgeError("content-addressed export conflicts with retained bytes")
        return
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if temporary.exists():
        raise DemoDecisionBridgeError("private temporary path already exists")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    _fsync_directory(path.parent)


def _read_private(path: Path) -> bytes:
    _assert_private_file(path, may_not_exist=False)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if info.st_size > MAX_PRIVATE_BYTES:
            raise DemoDecisionBridgeError("private evidence file exceeds byte limit")
        return _read_descriptor(descriptor, max_bytes=MAX_PRIVATE_BYTES)
    finally:
        os.close(descriptor)


def _load_ledger(path: Path) -> dict[str, tuple[str, dict[str, object]]]:
    if not path.exists():
        return {}
    try:
        text = _read_private(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DemoDecisionBridgeError("private event ledger is not UTF-8") from exc
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(rows) >= MAX_JSONL_ROWS:
            raise DemoDecisionBridgeError("private event ledger exceeds row limit")
        if len(line) > MAX_SNAPSHOT_BYTES:
            raise DemoDecisionBridgeError("private event ledger row exceeds byte limit")
        parsed = _json_loads_exact(
            line,
            label=f"private event ledger:{line_number}",
            preserve_numeric_lexemes=False,
        )
        if not isinstance(parsed, dict):
            raise DemoDecisionBridgeError("private event ledger row must be an object")
        rows.append(cast(dict[str, object], parsed))
    result: dict[str, tuple[str, dict[str, object]]] = {}
    for row in rows:
        validate_event(row)
        key = str(row["logical_key"])
        digest = canonical_digest(row)
        prior = result.get(key)
        if prior is not None:
            if prior[0] != digest:
                raise DemoDecisionBridgeError("retained ledger contains a logical-key conflict")
            raise DemoDecisionBridgeError("retained ledger contains a duplicate row")
        result[key] = (digest, row)
    return result


def _append_store(
    store: SyntheticEvidenceStore,
    event: Mapping[str, object],
    recorded_at: str,
) -> None:
    store_existed = store.path.exists()
    _assert_private_file(store.path)
    _assert_private_file(store.lock_path)
    occurred = cast(Mapping[str, object], event["occurred_at"])
    store.append(
        dict(event),
        idempotency_key=str(event["logical_key"]),
        record_id=str(event["event_id"]),
        record_type=RECORD_TYPE,
        stage=Stage.S3_PAPER_DEMO,
        occurred_at=datetime.fromisoformat(
            str(occurred["storage_timestamp"]).replace("Z", "+00:00")
        ),
        recorded_at=datetime.fromisoformat(recorded_at.replace("Z", "+00:00")),
    )
    os.chmod(store.path, 0o600)
    _assert_private_file(store.path, may_not_exist=False)
    if store.lock_path.exists():
        os.chmod(store.lock_path, 0o600)
        _assert_private_file(store.lock_path, may_not_exist=False)
    if not store_existed:
        _fsync_directory(store.path.parent)


def _baseline_record(
    *,
    source_label: str,
    captured_at: str,
    source_refs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": SCHEMA,
        "kind": "SOURCE_BASELINE",
        "source_label": source_label,
        "captured_at": timestamp_evidence(captured_at),
        "source_refs": [dict(ref) for ref in source_refs],
        "execution_authority": "NONE",
    }
    body["baseline_id"] = stable_id("BASE", body)
    _validate_baseline_record(body)
    return body


def _validate_baseline_record(record: Mapping[str, object]) -> None:
    required = {
        "schema",
        "kind",
        "baseline_id",
        "source_label",
        "captured_at",
        "source_refs",
        "execution_authority",
    }
    if set(record) != required:
        raise DemoDecisionBridgeError("source baseline fields are invalid")
    if (
        record["schema"] != SCHEMA
        or record["kind"] != "SOURCE_BASELINE"
        or record["execution_authority"] != "NONE"
        or not _LABEL.fullmatch(str(record["source_label"]))
    ):
        raise DemoDecisionBridgeError("source baseline identity is invalid")
    _validate_id(record["baseline_id"], "baseline_id")
    _validate_timestamp_evidence(record["captured_at"], allow_unknown=False)
    refs = record["source_refs"]
    if not isinstance(refs, list) or len(refs) != 3:
        raise DemoDecisionBridgeError("source baseline references are invalid")
    if {str(_validate_source_ref(ref)["kind"]) for ref in refs} != {
        "lane_state",
        "heartbeat",
        "orders",
    }:
        raise DemoDecisionBridgeError("source baseline kinds are invalid")
    if refs != list(_canonical_source_refs(cast(list[Mapping[str, object]], refs))):
        raise DemoDecisionBridgeError("source baseline references are not canonical")
    without_id = dict(record)
    actual = str(without_id.pop("baseline_id"))
    if stable_id("BASE", without_id) != actual:
        raise DemoDecisionBridgeError("source baseline id does not match retained content")
    validate_no_secrets(record)
    _validate_structure_bounds(record)


def _load_source_baseline(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        text = _read_private(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DemoDecisionBridgeError("source baseline is not UTF-8") from exc
    parsed = _json_loads_exact(
        text,
        label="source baseline",
        preserve_numeric_lexemes=False,
    )
    if not isinstance(parsed, dict):
        raise DemoDecisionBridgeError("source baseline must be an object")
    record = cast(dict[str, object], parsed)
    _validate_baseline_record(record)
    return record


def _baseline_refs(record: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    refs = cast(list[object], record["source_refs"])
    return {
        str(cast(Mapping[str, object], ref)["kind"]): cast(Mapping[str, object], ref)
        for ref in refs
    }


def _detect_baseline_incident(
    prior: Mapping[str, object],
    *,
    source_label: str,
    captured_at: str,
    copies: Sequence[SourceCopy],
) -> tuple[str, Mapping[str, object], Mapping[str, object]] | None:
    if prior["source_label"] != source_label:
        raise DemoDecisionBridgeError("private output history is bound to a different source label")
    prior_refs = _baseline_refs(prior)
    current_refs = {copy.kind: copy.reference() for copy in copies}
    orders_incident = validate_source_progress(prior_refs["orders"], copies[2].data)
    if orders_incident is not None:
        return orders_incident, prior_refs["orders"], current_refs["orders"]
    prior_captured = cast(Mapping[str, object], prior["captured_at"])["canonical"]
    if prior_captured == captured_at:
        for kind in ("lane_state", "heartbeat", "orders"):
            if prior_refs[kind]["sha256"] != current_refs[kind]["sha256"]:
                return (
                    EventType.SOURCE_MUTATION.value,
                    prior_refs[kind],
                    current_refs[kind],
                )
    return None


def _load_store_snapshot(store: SyntheticEvidenceStore) -> StoreSnapshot | None:
    if not store.path.exists():
        if store.lock_path.exists():
            _assert_private_file(store.lock_path)
        return None
    _assert_private_file(store.path, may_not_exist=False)
    if store.lock_path.exists():
        _assert_private_file(store.lock_path, may_not_exist=False)
    connection = sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if str(integrity) != "ok":
            raise DemoDecisionBridgeError("private evidence store integrity check failed")
        raw_rows = connection.execute(
            """SELECT sequence, idempotency_key, record_id, record_type, stage,
                      occurred_at, recorded_at, payload_json, payload_sha256
               FROM evidence_events ORDER BY sequence"""
        ).fetchall()
        schema_rows = connection.execute(
            """SELECT type, name, tbl_name, sql
               FROM sqlite_master
               ORDER BY type, name, tbl_name"""
        ).fetchall()
        version_rows = connection.execute(
            "SELECT version FROM schema_version ORDER BY rowid"
        ).fetchall()
        sequence_row = connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'evidence_events'"
        ).fetchone()
    except sqlite3.Error as exc:
        raise DemoDecisionBridgeError("private evidence store schema is invalid") from exc
    finally:
        connection.close()
    if len(raw_rows) > MAX_JSONL_ROWS:
        raise DemoDecisionBridgeError("private evidence store exceeds row limit")
    rows: list[dict[str, object]] = []
    for expected_sequence, row in enumerate(raw_rows, start=1):
        if int(row["sequence"]) != expected_sequence:
            raise DemoDecisionBridgeError("private evidence store sequence is not contiguous")
        parsed = _json_loads_exact(
            str(row["payload_json"]),
            label=f"private evidence store row:{expected_sequence}",
            preserve_numeric_lexemes=False,
        )
        if not isinstance(parsed, dict):
            raise DemoDecisionBridgeError("private evidence store payload must be an object")
        event = cast(dict[str, object], parsed)
        validate_event(event)
        payload_json = canonical_json(event)
        payload_sha256 = hashlib.sha256(payload_json.encode()).hexdigest()
        occurred = cast(Mapping[str, object], event["occurred_at"])
        if (
            row["idempotency_key"] != event["logical_key"]
            or row["record_id"] != event["event_id"]
            or row["record_type"] != RECORD_TYPE
            or row["stage"] != Stage.S3_PAPER_DEMO.value
            or row["payload_json"] != payload_json
            or row["payload_sha256"] != payload_sha256
            or canonical_timestamp(str(row["occurred_at"])) != occurred["storage_timestamp"]
        ):
            raise DemoDecisionBridgeError("private evidence store row identity is corrupt")
        canonical_timestamp(str(row["recorded_at"]))
        rows.append(
            {
                "sequence": expected_sequence,
                "idempotency_key": str(row["idempotency_key"]),
                "record_id": str(row["record_id"]),
                "record_type": str(row["record_type"]),
                "stage": str(row["stage"]),
                "occurred_at": canonical_timestamp(str(row["occurred_at"])),
                "recorded_at": canonical_timestamp(str(row["recorded_at"])),
                "payload": event,
                "payload_sha256": payload_sha256,
            }
        )
    if [int(row["version"]) for row in version_rows] != [1]:
        raise DemoDecisionBridgeError("private evidence store schema version is invalid")
    schema_inventory = tuple(
        {
            "type": str(row["type"]),
            "name": str(row["name"]),
            "table_name": str(row["tbl_name"]),
            "sql": (
                None
                if row["sql"] is None
                else " ".join(str(row["sql"]).split()).replace(
                    " IF NOT EXISTS ",
                    " ",
                    1,
                )
            ),
        }
        for row in schema_rows
    )
    if schema_inventory != _EXPECTED_STORE_SCHEMA_ROWS:
        raise DemoDecisionBridgeError(
            "private evidence store schema differs from the fixed contract"
        )
    last_sequence = 0 if sequence_row is None else int(sequence_row["seq"])
    if last_sequence != len(rows):
        raise DemoDecisionBridgeError(
            "private evidence store last sequence disagrees with row inventory"
        )
    return StoreSnapshot(
        rows=tuple(rows),
        schema_sha256=canonical_digest(
            {
                "sqlite_master": _EXPECTED_STORE_SCHEMA_ROWS,
                "schema_version": [1],
            }
        ),
        schema_version=1,
        last_sequence=last_sequence,
    )


def _store_inventory_sha256(rows: Sequence[Mapping[str, object]]) -> str:
    return _bounded_ordered_array_sha256(rows)


def _bounded_ordered_array_sha256(rows: Sequence[Mapping[str, object]]) -> str:
    """Digest a bounded ordered object array without weakening per-object JSON limits."""

    if len(rows) > MAX_JSONL_ROWS:
        raise DemoDecisionBridgeError("ordered digest inventory exceeds the row limit")
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, row in enumerate(rows):
        if index:
            digest.update(b",")
        digest.update(canonical_json(row).encode())
    digest.update(b"]")
    return digest.hexdigest()


def _fixed_store_schema_sha256() -> str:
    return canonical_digest(
        {
            "sqlite_master": _EXPECTED_STORE_SCHEMA_ROWS,
            "schema_version": [1],
        }
    )


def _missing_store_events(
    rows: Sequence[Mapping[str, object]],
    ledger: Mapping[str, tuple[str, Mapping[str, object]]],
) -> list[Mapping[str, object]]:
    ledger_events = [event for _, event in ledger.values()]
    if len(rows) > len(ledger_events):
        raise DemoDecisionBridgeError("private evidence store has extra historical rows")
    for index, row in enumerate(rows):
        event = ledger_events[index]
        if row["idempotency_key"] != event["logical_key"] or row[
            "payload_sha256"
        ] != canonical_digest(event):
            raise DemoDecisionBridgeError("private ledger/store historical parity failed")
    return ledger_events[len(rows) :]


def _reconcile_store_with_ledger(
    store: SyntheticEvidenceStore,
    ledger: Mapping[str, tuple[str, Mapping[str, object]]],
    *,
    recorded_at: str,
) -> list[dict[str, object]]:
    snapshot = _load_store_snapshot(store)
    rows = [] if snapshot is None else list(snapshot.rows)
    missing = _missing_store_events(rows, ledger)
    for event in missing:
        _append_store(store, event, recorded_at)
    reconciled_snapshot = _load_store_snapshot(store)
    if reconciled_snapshot is None:
        raise DemoDecisionBridgeError("private evidence store recovery did not create a store")
    reconciled = list(reconciled_snapshot.rows)
    if _missing_store_events(reconciled, ledger):
        raise DemoDecisionBridgeError("private ledger/store recovery remained incomplete")
    return reconciled


def _load_private_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        text = _read_private(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DemoDecisionBridgeError(f"{label} is not UTF-8") from exc
    raw = _json_loads_exact(
        text,
        label=label,
        preserve_numeric_lexemes=False,
    )
    if not isinstance(raw, dict):
        raise DemoDecisionBridgeError(f"{label} must be an object")
    return cast(dict[str, object], raw)


def _load_current(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = _load_private_json(path, label="private CURRENT pointer")
    required = {
        "schema",
        "kind",
        "generation_id",
        "manifest_sha256",
        "execution_authority",
    }
    if set(parsed) != required:
        raise DemoDecisionBridgeError("private CURRENT pointer fields are invalid")
    if (
        parsed.get("schema") != SCHEMA
        or parsed.get("kind") != "CURRENT"
        or parsed["execution_authority"] != "NONE"
        or not re.fullmatch(r"GEN-[a-f0-9]{32}", str(parsed["generation_id"]))
        or not _SHA256.fullmatch(str(parsed["manifest_sha256"]))
    ):
        raise DemoDecisionBridgeError("private CURRENT pointer identity is invalid")
    validate_no_secrets(parsed)
    _validate_structure_bounds(parsed)
    return parsed


def _load_generation_manifest(path: Path) -> tuple[dict[str, object], str]:
    raw_bytes = _read_private(path)
    manifest_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    manifest = _load_private_json(path, label="private generation manifest")
    required = {
        "schema",
        "kind",
        "generation_id",
        "previous_generation_id",
        "previous_manifest_sha256",
        "source_label",
        "baseline",
        "captured_at",
        "source_refs",
        "files",
        "store",
        "execution_authority",
    }
    if set(manifest) != required:
        raise DemoDecisionBridgeError("private generation manifest fields are invalid")
    if (
        manifest["schema"] != SCHEMA
        or manifest["kind"] != "GENERATION_MANIFEST"
        or manifest["execution_authority"] != "NONE"
        or not re.fullmatch(r"GEN-[a-f0-9]{32}", str(manifest["generation_id"]))
        or not _LABEL.fullmatch(str(manifest["source_label"]))
    ):
        raise DemoDecisionBridgeError("private generation manifest identity is invalid")
    previous_generation = manifest["previous_generation_id"]
    previous_manifest = manifest["previous_manifest_sha256"]
    if (previous_generation is None) != (previous_manifest is None):
        raise DemoDecisionBridgeError("generation predecessor binding is incomplete")
    if previous_generation is not None and (
        not re.fullmatch(r"GEN-[a-f0-9]{32}", str(previous_generation))
        or not _SHA256.fullmatch(str(previous_manifest))
    ):
        raise DemoDecisionBridgeError("generation predecessor binding is invalid")
    baseline = manifest["baseline"]
    if not isinstance(baseline, Mapping) or set(baseline) != {
        "baseline_id",
        "name",
        "sha256",
        "byte_count",
    }:
        raise DemoDecisionBridgeError("generation baseline binding is invalid")
    _validate_id(baseline["baseline_id"], "baseline_id")
    if baseline["name"] != "baseline.json" or not _SHA256.fullmatch(str(baseline["sha256"])):
        raise DemoDecisionBridgeError("generation baseline digest is invalid")
    byte_count = baseline["byte_count"]
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 1:
        raise DemoDecisionBridgeError("generation baseline byte count is invalid")
    _validate_timestamp_evidence(manifest["captured_at"], allow_unknown=False)
    refs = manifest["source_refs"]
    if not isinstance(refs, list) or len(refs) != 3:
        raise DemoDecisionBridgeError("generation source references are invalid")
    if {str(_validate_source_ref(ref)["kind"]) for ref in refs} != {
        "lane_state",
        "heartbeat",
        "orders",
    }:
        raise DemoDecisionBridgeError("generation source kinds are invalid")
    if refs != list(_canonical_source_refs(cast(list[Mapping[str, object]], refs))):
        raise DemoDecisionBridgeError("generation source references are not canonical")
    files = manifest["files"]
    if not isinstance(files, Mapping) or set(files) != {
        "events",
        "projection",
        "export",
    }:
        raise DemoDecisionBridgeError("generation file inventory is invalid")
    for file_kind, expected_name in (
        ("events", "events.jsonl"),
        ("projection", "projection.json"),
        ("export", "export.jsonl"),
    ):
        binding = files[file_kind]
        expected = {"name", "sha256", "byte_count"}
        if file_kind in {"events", "export"}:
            expected.add("event_count")
        if not isinstance(binding, Mapping) or set(binding) != expected:
            raise DemoDecisionBridgeError("generation file binding fields are invalid")
        if binding["name"] != expected_name or not _SHA256.fullmatch(str(binding["sha256"])):
            raise DemoDecisionBridgeError("generation file binding identity is invalid")
        for key in expected & {"byte_count", "event_count"}:
            value = binding[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DemoDecisionBridgeError("generation file binding count is invalid")
    store = manifest["store"]
    if not isinstance(store, Mapping) or set(store) != {
        "schema_sha256",
        "schema_version",
        "row_count",
        "last_sequence",
        "inventory_sha256",
        "ledger_parity_sha256",
    }:
        raise DemoDecisionBridgeError("generation store binding is invalid")
    for key in ("schema_sha256", "inventory_sha256", "ledger_parity_sha256"):
        if not _SHA256.fullmatch(str(store[key])):
            raise DemoDecisionBridgeError("generation store digest is invalid")
    if store["schema_sha256"] != _fixed_store_schema_sha256():
        raise DemoDecisionBridgeError("generation store schema does not match the fixed contract")
    for key in ("schema_version", "row_count", "last_sequence"):
        value = store[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise DemoDecisionBridgeError("generation store count is invalid")
    if store["schema_version"] != 1 or store["row_count"] != store["last_sequence"]:
        raise DemoDecisionBridgeError("generation store sequence binding is invalid")
    expected_generation = stable_id(
        "GEN",
        {
            "previous_manifest_sha256": previous_manifest or "GENESIS",
            "baseline_id": baseline["baseline_id"],
        },
    )
    if manifest["generation_id"] != expected_generation:
        raise DemoDecisionBridgeError("generation id does not match its fixed seed")
    validate_no_secrets(manifest)
    _validate_structure_bounds(manifest)
    return manifest, manifest_sha256


def _ledger_parity_sha256(
    rows: Sequence[Mapping[str, object]],
    ledger: Mapping[str, tuple[str, Mapping[str, object]]],
) -> str:
    events = [event for _, event in ledger.values()]
    if len(rows) != len(events):
        raise DemoDecisionBridgeError("private ledger/store row counts disagree")
    parity: list[dict[str, object]] = []
    for sequence, (row, event) in enumerate(zip(rows, events, strict=True), start=1):
        event_digest = canonical_digest(event)
        if (
            row["sequence"] != sequence
            or row["idempotency_key"] != event["logical_key"]
            or row["record_id"] != event["event_id"]
            or row["payload_sha256"] != event_digest
        ):
            raise DemoDecisionBridgeError("private ledger/store historical parity failed")
        parity.append(
            {
                "sequence": sequence,
                "logical_key": event["logical_key"],
                "event_id": event["event_id"],
                "event_sha256": event_digest,
            }
        )
    return _bounded_ordered_array_sha256(parity)


def _verify_generation_manifest(
    manifest: Mapping[str, object],
    private: Path,
    store_snapshot: StoreSnapshot,
    *,
    allow_store_tail: bool,
) -> tuple[
    dict[str, tuple[str, dict[str, object]]],
    dict[str, object],
    Path,
]:
    generation_id = str(manifest["generation_id"])
    generation_dir = private / "generations" / generation_id
    if (
        not generation_dir.is_dir()
        or generation_dir.is_symlink()
        or stat.S_IMODE(generation_dir.stat().st_mode) != 0o700
    ):
        raise DemoDecisionBridgeError("committed generation directory is not private")
    _assert_generation_entries(generation_dir, final=True)
    files = cast(Mapping[str, Mapping[str, object]], manifest["files"])
    retained: dict[str, bytes] = {}
    for kind in ("events", "projection", "export"):
        binding = files[kind]
        file_path = generation_dir / str(binding["name"])
        file_bytes = _read_private(file_path)
        if (
            len(file_bytes) != binding["byte_count"]
            or hashlib.sha256(file_bytes).hexdigest() != binding["sha256"]
        ):
            raise DemoDecisionBridgeError("immutable generation retained-byte binding failed")
        retained[kind] = file_bytes
    ledger = _load_ledger(generation_dir / "events.jsonl")
    if (
        len(ledger) != files["events"]["event_count"]
        or retained["events"] != retained["export"]
        or files["events"]["event_count"] != files["export"]["event_count"]
    ):
        raise DemoDecisionBridgeError("generation event inventory is inconsistent")
    projection_raw = _json_loads_exact(
        retained["projection"].decode("utf-8"),
        label="generation projection",
        preserve_numeric_lexemes=False,
    )
    if not isinstance(projection_raw, dict):
        raise DemoDecisionBridgeError("generation projection must be an object")
    projection = cast(dict[str, object], projection_raw)
    validate_projection(projection)
    if (
        projection["captured_at"] != manifest["captured_at"]
        or projection["source_refs"] != manifest["source_refs"]
    ):
        raise DemoDecisionBridgeError("generation projection source binding failed")
    matching_snapshots = [
        cast(Mapping[str, object], event["payload"])
        for _, event in ledger.values()
        if event["event_type"] == EventType.LEGACY_SNAPSHOT_IMPORTED.value
        and cast(Mapping[str, object], event["payload"])["projection_id"]
        == projection["projection_id"]
    ]
    episode = cast(list[Mapping[str, object]], projection["episodes"])[0]
    if len(matching_snapshots) != 1 or (
        matching_snapshots[0]["episode_id"] != episode["episode_id"]
        or matching_snapshots[0]["projection_status"] != projection["projection_status"]
    ):
        raise DemoDecisionBridgeError(
            "generation snapshot event identity does not match its projection"
        )
    baseline = cast(Mapping[str, object], manifest["baseline"])
    baseline_path = generation_dir / "baseline.json"
    baseline_bytes = _read_private(baseline_path)
    baseline_byte_count = cast(int, baseline["byte_count"])
    if (
        len(baseline_bytes) != baseline_byte_count
        or hashlib.sha256(baseline_bytes).hexdigest() != baseline["sha256"]
    ):
        raise DemoDecisionBridgeError("generation baseline retained-byte binding failed")
    retained_baseline = _load_source_baseline(baseline_path)
    if retained_baseline is None:
        raise DemoDecisionBridgeError("generation baseline is missing")
    if (
        retained_baseline["baseline_id"] != baseline["baseline_id"]
        or retained_baseline["source_label"] != manifest["source_label"]
        or retained_baseline["captured_at"] != manifest["captured_at"]
        or retained_baseline["source_refs"] != manifest["source_refs"]
    ):
        raise DemoDecisionBridgeError("generation baseline identity binding failed")
    store = cast(Mapping[str, object], manifest["store"])
    row_count = int(cast(int, store["row_count"]))
    if (
        store_snapshot.schema_sha256 != store["schema_sha256"]
        or store_snapshot.schema_version != store["schema_version"]
        or len(store_snapshot.rows) < row_count
    ):
        raise DemoDecisionBridgeError("generation store schema or row binding failed")
    prefix = store_snapshot.rows[:row_count]
    if (
        _store_inventory_sha256(prefix) != store["inventory_sha256"]
        or _ledger_parity_sha256(prefix, ledger) != store["ledger_parity_sha256"]
    ):
        raise DemoDecisionBridgeError("generation store inventory binding failed")
    if not allow_store_tail and (
        len(store_snapshot.rows) != row_count
        or store_snapshot.last_sequence != store["last_sequence"]
    ):
        raise DemoDecisionBridgeError("private evidence store has unexplained rows")
    return ledger, projection, generation_dir / "export.jsonl"


def _load_committed_chain(
    private: Path,
    current: Mapping[str, object] | None,
) -> list[tuple[dict[str, object], str]]:
    if current is None:
        return []
    chain: list[tuple[dict[str, object], str]] = []
    expected_id: object = current["generation_id"]
    expected_sha: object = current["manifest_sha256"]
    seen: set[str] = set()
    while expected_id is not None:
        generation_id = str(expected_id)
        if generation_id in seen or len(chain) >= MAX_JSONL_ROWS:
            raise DemoDecisionBridgeError("committed generation chain is cyclic or too long")
        seen.add(generation_id)
        manifest_path = private / "generations" / generation_id / "manifest.json"
        manifest, manifest_sha256 = _load_generation_manifest(manifest_path)
        if manifest["generation_id"] != generation_id or manifest_sha256 != expected_sha:
            raise DemoDecisionBridgeError("CURRENT generation manifest binding failed")
        chain.append((manifest, manifest_sha256))
        expected_id = manifest["previous_generation_id"]
        expected_sha = manifest["previous_manifest_sha256"]
    return chain


def _generation_directories(path: Path) -> set[str]:
    if not path.exists():
        return set()
    if path.is_symlink() or not path.is_dir() or stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise DemoDecisionBridgeError("generation root must be a real 0700 directory")
    result: set[str] = set()
    for child in path.iterdir():
        if (
            child.is_symlink()
            or not child.is_dir()
            or stat.S_IMODE(child.stat().st_mode) != 0o700
            or not re.fullmatch(r"GEN-[a-f0-9]{32}", child.name)
        ):
            raise DemoDecisionBridgeError("generation root contains an unexplained entry")
        result.add(child.name)
    return result


def _assert_generation_entries(path: Path, *, final: bool) -> None:
    entries: set[str] = set()
    for child in path.iterdir():
        if child.is_symlink() or not child.is_file():
            raise DemoDecisionBridgeError("generation directory contains a non-regular entry")
        _assert_private_file(child, may_not_exist=False)
        entries.add(child.name)
    allowed = {_FINAL_GENERATION_FILES} if final else set(_PENDING_GENERATION_PHASES)
    if frozenset(entries) not in allowed:
        raise DemoDecisionBridgeError(
            "generation directory contains extra, temporary, or out-of-phase files"
        )


def _recover_uncommitted_atomic_temps(
    path: Path,
    *,
    allowed_targets: frozenset[str],
) -> None:
    """Remove only validated atomic-write temps from a provably uncommitted location."""

    removed = False
    for child in path.iterdir():
        match = _ATOMIC_TEMP.fullmatch(child.name)
        if match is None:
            continue
        if match.group("target") not in allowed_targets:
            raise DemoDecisionBridgeError("unrecognized private atomic temporary file is forbidden")
        _assert_private_file(child, may_not_exist=False)
        os.unlink(child)
        removed = True
    if removed:
        _fsync_directory(path)


def _merge_events(
    committed: Mapping[str, tuple[str, dict[str, object]]],
    presented: Sequence[Mapping[str, object]],
) -> tuple[dict[str, tuple[str, dict[str, object]]], int]:
    merged = dict(committed)
    appended = 0
    for raw in presented:
        event = dict(raw)
        validate_event(event)
        key = str(event["logical_key"])
        digest = canonical_digest(event)
        prior = merged.get(key)
        if prior is not None:
            if prior[0] == digest:
                continue
            raise EvidenceConflictError(
                _conflict_event(
                    key,
                    prior[0],
                    digest,
                    cast(Mapping[str, object], event["occurred_at"]).get("canonical"),
                )
            )
        merged[key] = (digest, event)
        appended += 1
    return merged, appended


def _assert_ledger_source_label(
    ledger: Mapping[str, tuple[str, Mapping[str, object]]],
    source_label: str,
) -> None:
    if not ledger:
        return
    expected_hash = hashlib.sha256(source_label.encode()).hexdigest()
    found_binding = False
    for _, event in ledger.values():
        event_type = EventType(str(event["event_type"]))
        payload = cast(Mapping[str, object], event["payload"])
        if event_type is EventType.LEGACY_SNAPSHOT_IMPORTED:
            found_binding = True
            if payload.get("source_label_sha256") != expected_hash:
                raise DemoDecisionBridgeError(
                    "private output history is bound to a different source label"
                )
        source_ref = cast(Mapping[str, object], event["source_ref"])
        kind = str(source_ref["kind"])
        if kind in {"lane_state", "heartbeat", "orders", "order-record"}:
            found_binding = True
            expected_label = (
                f"{source_label}.orders" if kind == "order-record" else (f"{source_label}.{kind}")
            )
            if source_ref["label"] != expected_label:
                raise DemoDecisionBridgeError(
                    "private output history is bound to a different source label"
                )
    if not found_binding:
        raise DemoDecisionBridgeError("private output history has no source-label binding")


def run_bridge(
    *,
    lane_state_path: Path,
    heartbeat_path: Path,
    orders_path: Path,
    output_dir: Path,
    source_label: str,
    captured_at: str,
    repo_root: Path,
    before_checkpoint: Callable[[], None] | None = None,
    after_generation_verified: Callable[[], None] | None = None,
    before_current_replace: Callable[[], None] | None = None,
) -> BridgeResult:
    """Import copied legacy files and atomically commit one immutable evidence generation."""

    captured = canonical_timestamp(captured_at)
    copies = (
        read_source_copy(
            lane_state_path,
            kind="lane_state",
            source_label=source_label,
            repo_root=repo_root,
        ),
        read_source_copy(
            heartbeat_path,
            kind="heartbeat",
            source_label=source_label,
            repo_root=repo_root,
        ),
        read_source_copy(
            orders_path,
            kind="orders",
            source_label=source_label,
            repo_root=repo_root,
        ),
    )
    private = prepare_private_output_dir(output_dir, repo_root=repo_root)
    with _private_lock(private):
        _recover_uncommitted_atomic_temps(
            private,
            allowed_targets=frozenset(
                {
                    "CURRENT.json",
                    "evidence.sqlite3",
                    "evidence.sqlite3.lock",
                }
            ),
        )
        refs = _canonical_source_refs(tuple(copy.reference() for copy in copies))
        baseline_record = _baseline_record(
            source_label=source_label,
            captured_at=captured,
            source_refs=refs,
        )
        store_path = private / "evidence.sqlite3"
        _assert_private_file(store_path)
        _assert_private_file(store_path.with_suffix(".sqlite3.lock"))
        store = SyntheticEvidenceStore(store_path, root=repo_root)
        current_path = private / "CURRENT.json"
        current = _load_current(current_path)
        chain = _load_committed_chain(private, current)
        committed_ids = {str(manifest["generation_id"]) for manifest, _ in chain}
        generation_root_path = private / "generations"
        generation_ids = _generation_directories(generation_root_path)
        pending_ids = generation_ids - committed_ids
        if len(pending_ids) > 1:
            raise DemoDecisionBridgeError("multiple pending evidence generations are forbidden")
        if committed_ids - generation_ids:
            raise DemoDecisionBridgeError("a committed generation directory is missing")

        pending_dir = None if not pending_ids else generation_root_path / next(iter(pending_ids))
        pending_baseline: dict[str, object] | None = None
        pending_is_final = False
        if pending_dir is not None:
            _recover_uncommitted_atomic_temps(
                pending_dir,
                allowed_targets=_FINAL_GENERATION_FILES,
            )
            _assert_generation_entries(pending_dir, final=False)
            pending_is_final = (
                frozenset(child.name for child in pending_dir.iterdir()) == _FINAL_GENERATION_FILES
            )
            pending_baseline = _load_source_baseline(pending_dir / "baseline.json")
            if pending_baseline is not None:
                pending_incident = _detect_baseline_incident(
                    pending_baseline,
                    source_label=source_label,
                    captured_at=captured,
                    copies=copies,
                )
                if pending_incident is not None:
                    incident_type, prior_ref, current_ref = pending_incident
                    incident = _source_incident_event(
                        incident_type,
                        prior=prior_ref,
                        current=current_ref,
                        captured_at=captured,
                    )
                    raise SourceIncidentError(incident_type, incident)
                if (
                    pending_baseline["captured_at"] != timestamp_evidence(captured)
                    or pending_baseline["source_refs"] != list(refs)
                    or pending_baseline["baseline_id"] != baseline_record["baseline_id"]
                ):
                    raise DemoDecisionBridgeError(
                        "current source does not exactly match the pending baseline"
                    )

        previous_manifest_sha256 = None if current is None else current["manifest_sha256"]
        generation_id = stable_id(
            "GEN",
            {
                "previous_manifest_sha256": previous_manifest_sha256 or "GENESIS",
                "baseline_id": baseline_record["baseline_id"],
            },
        )
        if pending_ids and pending_ids != {generation_id}:
            raise DemoDecisionBridgeError(
                "pending generation id does not match its durable baseline seed"
            )

        committed_ledger: dict[str, tuple[str, dict[str, object]]] = {}
        committed_projection: dict[str, object] | None = None
        committed_export_path: Path | None = None
        store_snapshot: StoreSnapshot | None = None
        if chain:
            store_snapshot = _load_store_snapshot(store)
            if store_snapshot is None:
                raise DemoDecisionBridgeError("committed generation store is missing")
            for index, (manifest, _) in enumerate(chain):
                verified_ledger, verified_projection, verified_export = _verify_generation_manifest(
                    manifest,
                    private,
                    store_snapshot,
                    allow_store_tail=index > 0 or bool(pending_ids),
                )
                if index == 0:
                    committed_ledger = verified_ledger
                    committed_projection = verified_projection
                    committed_export_path = verified_export
            current_manifest = chain[0][0]
            if current_manifest["source_label"] != source_label:
                raise DemoDecisionBridgeError(
                    "private output history is bound to a different source label"
                )
        else:
            current_manifest = None
            if store_path.exists() and pending_dir is None:
                raise DemoDecisionBridgeError(
                    "an evidence store without a committed or pending generation is forbidden"
                )

        if pending_dir is not None and pending_is_final:
            pending_manifest, pending_manifest_sha256 = _load_generation_manifest(
                pending_dir / "manifest.json"
            )
            expected_previous_generation = (
                None if current_manifest is None else current_manifest["generation_id"]
            )
            if (
                pending_manifest["generation_id"] != generation_id
                or pending_manifest["previous_generation_id"] != expected_previous_generation
                or pending_manifest["previous_manifest_sha256"] != previous_manifest_sha256
            ):
                raise DemoDecisionBridgeError(
                    "unreferenced final generation predecessor binding failed"
                )
            if store_snapshot is None:
                store_snapshot = _load_store_snapshot(store)
            if store_snapshot is None:
                raise DemoDecisionBridgeError("unreferenced final generation store is missing")
            adopted_ledger, adopted_projection, adopted_export_path = _verify_generation_manifest(
                pending_manifest,
                private,
                store_snapshot,
                allow_store_tail=False,
            )
            adopted_current: dict[str, object] = {
                "schema": SCHEMA,
                "kind": "CURRENT",
                "generation_id": generation_id,
                "manifest_sha256": pending_manifest_sha256,
                "execution_authority": "NONE",
            }
            if before_current_replace is not None:
                before_current_replace()
            _safe_write_atomic(
                current_path,
                (canonical_json(adopted_current) + "\n").encode("utf-8"),
            )
            if _load_current(current_path) != adopted_current:
                raise DemoDecisionBridgeError("adopted CURRENT pointer verification failed")
            adopted_export = _read_private(adopted_export_path)
            return BridgeResult(
                projection=adopted_projection,
                events=tuple(event for _, event in adopted_ledger.values()),
                export_path=adopted_export_path,
                export_sha256=hashlib.sha256(adopted_export).hexdigest(),
                appended_event_count=0,
            )

        retained_baseline = pending_baseline
        if retained_baseline is None and current_manifest is not None:
            current_generation_dir = (
                private / "generations" / str(current_manifest["generation_id"])
            )
            retained_baseline = _load_source_baseline(current_generation_dir / "baseline.json")
        if retained_baseline is not None and pending_baseline is None:
            source_incident = _detect_baseline_incident(
                retained_baseline,
                source_label=source_label,
                captured_at=captured,
                copies=copies,
            )
            if source_incident is not None:
                incident_type, prior_ref, current_ref = source_incident
                incident = _source_incident_event(
                    incident_type,
                    prior=prior_ref,
                    current=current_ref,
                    captured_at=captured,
                )
                raise SourceIncidentError(incident_type, incident)

        lane_state = parse_json_bytes(copies[0].data, label="lane_state copy")
        heartbeat = parse_json_bytes(copies[1].data, label="heartbeat copy")
        orders = parse_jsonl_bytes(copies[2].data, label="orders copy")
        validate_no_secrets(lane_state)
        validate_no_secrets(heartbeat)
        validate_no_secrets(orders)
        projection, events = build_legacy_projection(
            lane_state,
            heartbeat,
            orders,
            source_refs=refs,
            captured_at=captured,
            source_label=source_label,
        )
        if (
            pending_dir is None
            and current_manifest is not None
            and (
                cast(Mapping[str, object], current_manifest["baseline"])["baseline_id"]
                == baseline_record["baseline_id"]
            )
        ):
            assert store_snapshot is not None
            committed_ledger, committed_projection, committed_export_path = (
                _verify_generation_manifest(
                    current_manifest,
                    private,
                    store_snapshot,
                    allow_store_tail=False,
                )
            )
            expected_by_key = {
                str(event["logical_key"]): canonical_digest(event) for event in events
            }
            if committed_projection != projection or any(
                key not in committed_ledger or committed_ledger[key][0] != digest
                for key, digest in expected_by_key.items()
            ):
                raise DemoDecisionBridgeError(
                    "exact replay disagrees with committed deterministic generation"
                )
            assert committed_export_path is not None
            export_bytes = _read_private(committed_export_path)
            return BridgeResult(
                projection=projection,
                events=tuple(event for _, event in committed_ledger.values()),
                export_path=committed_export_path,
                export_sha256=hashlib.sha256(export_bytes).hexdigest(),
                appended_event_count=0,
            )

        previous_generation_id = (
            None if current_manifest is None else current_manifest["generation_id"]
        )
        generation_root = prepare_private_output_dir(
            generation_root_path,
            repo_root=repo_root,
        )
        generation_dir = prepare_private_output_dir(
            generation_root / generation_id,
            repo_root=repo_root,
        )
        _assert_generation_entries(generation_dir, final=False)
        baseline_path = generation_dir / "baseline.json"
        baseline_bytes = (canonical_json(baseline_record) + "\n").encode("utf-8")
        _safe_write_atomic(baseline_path, baseline_bytes, create_only=True)
        if _load_source_baseline(baseline_path) != baseline_record:
            raise DemoDecisionBridgeError(
                "durable generation baseline disagrees with current source identity"
            )
        _assert_generation_entries(generation_dir, final=False)
        merged_ledger, _ = _merge_events(committed_ledger, events)
        _assert_ledger_source_label(merged_ledger, source_label)
        merged_events = tuple(event for _, event in merged_ledger.values())
        ledger_bytes = canonical_jsonl(merged_events)
        projection_bytes = (canonical_json(projection) + "\n").encode("utf-8")
        export_bytes = ledger_bytes
        export_sha256 = hashlib.sha256(export_bytes).hexdigest()
        ledger_path = generation_dir / "events.jsonl"
        projection_path = generation_dir / "projection.json"
        export_path = generation_dir / "export.jsonl"
        _safe_write_atomic(ledger_path, ledger_bytes, create_only=True)
        _assert_generation_entries(generation_dir, final=False)
        _safe_write_atomic(projection_path, projection_bytes, create_only=True)
        _assert_generation_entries(generation_dir, final=False)
        _safe_write_atomic(export_path, export_bytes, create_only=True)
        _assert_generation_entries(generation_dir, final=False)

        if current_manifest is None:
            if not store.path.exists():
                _safe_write_atomic(store.path, b"", create_only=True)
            if not store.lock_path.exists():
                _safe_write_atomic(store.lock_path, b"", create_only=True)
            store.initialize()
            os.chmod(store.path, 0o600)
            if store.lock_path.exists():
                os.chmod(store.lock_path, 0o600)
            store_snapshot = _load_store_snapshot(store)
        rows_before_recovery = 0 if store_snapshot is None else len(store_snapshot.rows)
        reconciled_rows = _reconcile_store_with_ledger(
            store,
            merged_ledger,
            recorded_at=captured,
        )
        store_snapshot = _load_store_snapshot(store)
        if store_snapshot is None or len(reconciled_rows) != len(merged_ledger):
            raise DemoDecisionBridgeError("private generation store recovery is incomplete")
        appended = len(store_snapshot.rows) - rows_before_recovery
        if len(store_snapshot.rows) != len(merged_ledger) or store_snapshot.last_sequence != len(
            merged_ledger
        ):
            raise DemoDecisionBridgeError("private evidence store has unexplained rows")
        ledger_parity_sha256 = _ledger_parity_sha256(
            store_snapshot.rows,
            merged_ledger,
        )
        if before_checkpoint is not None:
            before_checkpoint()

        manifest_payload: dict[str, object] = {
            "schema": SCHEMA,
            "kind": "GENERATION_MANIFEST",
            "generation_id": generation_id,
            "previous_generation_id": previous_generation_id,
            "previous_manifest_sha256": previous_manifest_sha256,
            "source_label": source_label,
            "baseline": {
                "baseline_id": baseline_record["baseline_id"],
                "name": "baseline.json",
                "sha256": hashlib.sha256(baseline_bytes).hexdigest(),
                "byte_count": len(baseline_bytes),
            },
            "captured_at": timestamp_evidence(captured),
            "source_refs": list(refs),
            "files": {
                "events": {
                    "name": "events.jsonl",
                    "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
                    "byte_count": len(ledger_bytes),
                    "event_count": len(merged_ledger),
                },
                "projection": {
                    "name": "projection.json",
                    "sha256": hashlib.sha256(projection_bytes).hexdigest(),
                    "byte_count": len(projection_bytes),
                },
                "export": {
                    "name": "export.jsonl",
                    "sha256": export_sha256,
                    "byte_count": len(export_bytes),
                    "event_count": len(merged_ledger),
                },
            },
            "store": {
                "schema_sha256": store_snapshot.schema_sha256,
                "schema_version": store_snapshot.schema_version,
                "row_count": len(store_snapshot.rows),
                "last_sequence": store_snapshot.last_sequence,
                "inventory_sha256": _store_inventory_sha256(store_snapshot.rows),
                "ledger_parity_sha256": ledger_parity_sha256,
            },
            "execution_authority": "NONE",
        }
        manifest_path = generation_dir / "manifest.json"
        _safe_write_atomic(
            manifest_path,
            (canonical_json(manifest_payload) + "\n").encode("utf-8"),
            create_only=True,
        )
        _assert_generation_entries(generation_dir, final=True)
        manifest_sha256 = hashlib.sha256(_read_private(manifest_path)).hexdigest()
        committed_manifest, retained_manifest_sha = _load_generation_manifest(manifest_path)
        if retained_manifest_sha != manifest_sha256:
            raise DemoDecisionBridgeError("committed manifest digest changed")
        _verify_generation_manifest(
            committed_manifest,
            private,
            store_snapshot,
            allow_store_tail=False,
        )
        if after_generation_verified is not None:
            after_generation_verified()
        current_payload: dict[str, object] = {
            "schema": SCHEMA,
            "kind": "CURRENT",
            "generation_id": generation_id,
            "manifest_sha256": manifest_sha256,
            "execution_authority": "NONE",
        }
        if before_current_replace is not None:
            before_current_replace()
        _safe_write_atomic(
            current_path,
            (canonical_json(current_payload) + "\n").encode("utf-8"),
        )
        if _load_current(current_path) != current_payload:
            raise DemoDecisionBridgeError("atomic CURRENT pointer verification failed")
        return BridgeResult(
            projection=projection,
            events=merged_events,
            export_path=export_path,
            export_sha256=export_sha256,
            appended_event_count=appended,
        )
