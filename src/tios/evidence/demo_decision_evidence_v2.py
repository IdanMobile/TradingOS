"""Default-disabled Stage B evidence for the fake-money venue-demo lane.

This module deliberately has no venue, network, credential, wallet, strategy
approval, promotion, or order-authority capability.  It owns a fixed private
evidence path below a caller-supplied repository root, validates the separately
approved activation bundle, and commits sanitized typed events with a
manifest-last protocol.  Absence of the activation root is always
``NOT_ACTIVATED`` and execution authority is always ``NONE``.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, Inexact, InvalidOperation, Rounded, localcontext
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, cast

EVENT_SCHEMA: Final = "tios.demo_decision_evidence.v2"
PRIVATE_ROOT_REL: Final = Path("artifacts/evidence/private_demo/stage_b_v2")
ACTIVATION_RECEIPT_REL: Final = Path("activation/ACTIVATION_RECEIPT.json")
ALIAS_KEY_REL: Final = Path("private/install_alias.key")

COHORT_SIZE: Final = 30
MAX_FRAME_BYTES: Final = 65_536
MAX_EVENTS_PER_GENERATION: Final = 4_096
MAX_EVENTS_BYTES: Final = 268_435_456
MAX_REDUCER_BYTES: Final = 33_554_432
MAX_PUBLIC_PROJECTION_BYTES: Final = 4_194_304
MAX_COHORTS: Final = 4_096
MAX_SERIES: Final = 256
MAX_GENERATIONS: Final = 256
MAX_TOTAL_EVENTS: Final = 1_048_576
MAX_SEQUENCE: Final = 2**63 - 1
RECOVERY_APPROVAL_MAX_AGE: Final = timedelta(minutes=15)
_EXACT_DECIMAL_CONTEXT: Final = Context(prec=128)
_EXACT_DECIMAL_CONTEXT.traps[Inexact] = True
_EXACT_DECIMAL_CONTEXT.traps[Rounded] = True

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_EVENT_ALIAS = re.compile(r"^evt_[a-f0-9]{64}$")
_PRIVATE_ALIAS = re.compile(r"^(ord|exe|fee|strategy|cost|risk)_[a-f0-9]{64}$")
_ACTIVATION_EPOCH = re.compile(r"^act_[a-f0-9]{64}$")
_CLIENT_KEY = re.compile(r"^[A-Za-z0-9_-]{1,36}$")
_DECIMAL = re.compile(r"^-?(0|[1-9][0-9]{0,47})(\.[0-9]{1,18})?$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")
_RESTART_ID = re.compile(r"^restart_[A-Za-z0-9_-]{1,64}$")
_GENERATION = re.compile(r"^G-[a-f0-9]{64}$")
_QUARANTINE_DIR = re.compile(
    r"^U-[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"
)
_WHOLE_LANE_RECONCILIATION_ALIAS: Final = (
    "ord_"
    + hashlib.sha256(b"tios.demo_decision_evidence.v2\0whole-lane-reconciliation").hexdigest()
)


class StageBEvidenceError(ValueError):
    """Stage B evidence cannot be trusted or committed."""


class StageBNotActivatedError(StageBEvidenceError):
    """The fixed Stage B runtime root or valid activation is absent."""


class StageBCommittedHeadError(StageBEvidenceError):
    """A generation committed, but its non-authoritative HEAD update failed."""

    def __init__(self, manifest_sha256: str) -> None:
        self.manifest_sha256 = manifest_sha256
        super().__init__("generation committed but convenience HEAD update failed")


class StageBCommittedDurabilityError(StageBEvidenceError):
    """The manifest committed, but its following directory fsync reported failure."""

    def __init__(self, manifest_sha256: str) -> None:
        self.manifest_sha256 = manifest_sha256
        super().__init__("generation committed with directory durability uncertain")


class EventType(StrEnum):
    ACTIVATION_BOUND = "ACTIVATION_BOUND"
    DECISION_OBSERVED = "DECISION_OBSERVED"
    RISK_VERDICT_OBSERVED = "RISK_VERDICT_OBSERVED"
    IDEMPOTENCY_KEY_RESERVED = "IDEMPOTENCY_KEY_RESERVED"
    SUBMISSION_INTENT_COMMITTED = "SUBMISSION_INTENT_COMMITTED"
    SUBMISSION_ATTEMPTED = "SUBMISSION_ATTEMPTED"
    VENUE_ACKNOWLEDGED = "VENUE_ACKNOWLEDGED"
    VENUE_REJECTED = "VENUE_REJECTED"
    SUBMISSION_RESULT_UNKNOWN = "SUBMISSION_RESULT_UNKNOWN"
    ORDER_UPDATE_OBSERVED = "ORDER_UPDATE_OBSERVED"
    FILL_OBSERVED = "FILL_OBSERVED"
    CANCEL_OBSERVED = "CANCEL_OBSERVED"
    EXIT_UPDATE_OBSERVED = "EXIT_UPDATE_OBSERVED"
    TERMINAL_RECONCILIATION_COMMITTED = "TERMINAL_RECONCILIATION_COMMITTED"
    CLOSED_EPISODE_COMMITTED = "CLOSED_EPISODE_COMMITTED"
    CORRECTION_COMMITTED = "CORRECTION_COMMITTED"
    EVIDENCE_OUTAGE_RECORDED = "EVIDENCE_OUTAGE_RECORDED"
    RECOVERY_COMMITTED = "RECOVERY_COMMITTED"


class ActivationState(StrEnum):
    NOT_ACTIVATED = "NOT_ACTIVATED"
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


_PAYLOAD_FIELDS: Final[dict[EventType, tuple[str, ...]]] = {
    EventType.ACTIVATION_BOUND: (
        "activation_receipt_sha256",
        "config_sha256",
        "independent_review_sha256",
        "flat_reconciliation_sha256",
        "rollback_config_sha256",
        "controlled_restart_id",
        "repo_commit",
    ),
    EventType.DECISION_OBSERVED: (
        "strategy_alias",
        "cost_alias",
        "risk_alias",
        "symbol",
        "timeframe",
        "decision",
        "side",
        "requested_qty",
        "quantity_unit",
    ),
    EventType.RISK_VERDICT_OBSERVED: (
        "decision_event_id",
        "verdict",
        "reason_code",
        "approved_qty",
        "quantity_unit",
        "quote_cap",
    ),
    EventType.IDEMPOTENCY_KEY_RESERVED: (
        "decision_event_id",
        "risk_event_id",
        "order_alias",
        "client_key",
        "client_key_sha256",
    ),
    EventType.SUBMISSION_INTENT_COMMITTED: (
        "key_event_id",
        "order_alias",
        "order_kind",
        "side",
        "order_type",
        "qty",
        "quantity_unit",
        "trigger_price",
        "risk_increasing",
    ),
    EventType.SUBMISSION_ATTEMPTED: (
        "intent_event_id",
        "order_alias",
        "client_key_sha256",
        "endpoint",
        "attempt_ordinal",
    ),
    EventType.VENUE_ACKNOWLEDGED: (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    EventType.VENUE_REJECTED: (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    EventType.SUBMISSION_RESULT_UNKNOWN: (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    EventType.ORDER_UPDATE_OBSERVED: (
        "order_alias",
        "order_status",
        "cum_exec_qty",
        "cum_exec_value",
        "leaves_qty",
        "avg_price",
        "source",
    ),
    EventType.FILL_OBSERVED: (
        "order_alias",
        "execution_alias",
        "fee_alias",
        "side",
        "exec_qty",
        "exec_price",
        "exec_value",
        "fee_amount",
        "fee_currency",
        "source",
    ),
    EventType.CANCEL_OBSERVED: (
        "order_alias",
        "client_key_sha256",
        "cancel_state",
        "venue_code",
        "source",
    ),
    EventType.EXIT_UPDATE_OBSERVED: (
        "episode_open_event_id",
        "order_alias",
        "exit_state",
        "executed_base_qty",
        "received_quote_value",
    ),
    EventType.TERMINAL_RECONCILIATION_COMMITTED: (
        "order_alias",
        "terminal_status",
        "buy_exec_qty",
        "sell_exec_qty",
        "entry_exec_value",
        "exit_exec_value",
        "quote_fee",
        "base_fee",
        "third_fee_present",
        "position_base_qty",
        "protective_stop_state",
        "flat",
        "source",
        "all_pages_complete",
    ),
    EventType.CLOSED_EPISODE_COMMITTED: (
        "series_sha256",
        "episode_ordinal",
        "entry_base_qty",
        "exit_base_qty",
        "entry_exec_value",
        "exit_exec_value",
        "gross_quote",
        "quote_fee",
        "base_fee",
        "third_fee_present",
        "net_quote",
        "terminal_reconciliation_event_id",
        "eligibility",
        "ineligibility_code",
    ),
    EventType.CORRECTION_COMMITTED: (
        "target_event_id",
        "target_event_sha256",
        "correction_code",
        "replacement_event_id",
    ),
    EventType.EVIDENCE_OUTAGE_RECORDED: (
        "incident_sha256",
        "outage_code",
        "first_affected_event_id",
        "risk_reduction_occurred",
    ),
    EventType.RECOVERY_COMMITTED: (
        "incident_sha256",
        "recovery_record_sha256",
        "approval_sha256",
        "reconciliation_event_id",
        "prior_head_sha256",
    ),
}

_ENUM_FIELDS: Final[dict[str, frozenset[str]]] = {
    "decision": frozenset({"ENTRY", "EXIT", "STOP", "CANCEL", "NO_ACTION"}),
    "side": frozenset({"BUY", "SELL", "NONE"}),
    "quantity_unit": frozenset({"BASE", "QUOTE", "NONE"}),
    "verdict": frozenset({"ALLOW_RISK_INCREASE", "BLOCK", "RISK_REDUCING"}),
    "reason_code": frozenset({"POLICY_PASS", "POLICY_BLOCK", "EXIT_ONLY", "KILL_SWITCH"}),
    "order_kind": frozenset(
        {"ENTRY", "EXIT", "STOP_CREATE", "STOP_REPLACE", "STOP_CLEANUP", "CANCEL"}
    ),
    "order_type": frozenset({"MARKET", "STOP_MARKET"}),
    "endpoint": frozenset({"CREATE", "CANCEL"}),
    "result_code": frozenset(
        {
            "ACCEPTED_PENDING",
            "POLICY_REJECTED",
            "VENUE_REJECTED",
            "TIMEOUT",
            "DISCONNECT",
            "MALFORMED",
            "UNKNOWN",
        }
    ),
    "order_status": frozenset(
        {
            "NEW",
            "PARTIALLY_FILLED",
            "FILLED",
            "CANCELLED",
            "REJECTED",
            "PARTIALLY_FILLED_CANCELED",
            "UNTRIGGERED",
            "TRIGGERED",
            "DEACTIVATED",
            "UNKNOWN",
        }
    ),
    "source": frozenset({"REALTIME", "HISTORY", "EXECUTION", "RECONCILIATION"}),
    "cancel_state": frozenset({"ACK_PENDING", "CONFIRMED", "REJECTED", "UNKNOWN"}),
    "exit_state": frozenset({"STARTED", "PARTIAL", "TERMINAL", "UNKNOWN"}),
    "terminal_status": frozenset({"FILLED", "CANCELLED", "REJECTED", "PARTIALLY_FILLED_CANCELED"}),
    "protective_stop_state": frozenset({"CLEAR", "ACTIVE", "FILLED", "CANCELLED", "UNKNOWN"}),
    "fee_currency": frozenset({"USDT", "ETH", "THIRD"}),
    "eligibility": frozenset({"ELIGIBLE", "PERMANENTLY_INELIGIBLE"}),
    "ineligibility_code": frozenset(
        {
            "NONE",
            "LEGACY",
            "OUTAGE",
            "CORRECTION",
            "THIRD_CURRENCY_FEE",
            "CHAIN_GAP",
            "UNRESOLVED",
            "STOP_NOT_CLEAR",
        }
    ),
    "correction_code": frozenset(
        {"SOURCE_CORRECTION", "DUPLICATE_CONFLICT", "RECONCILIATION_CORRECTION"}
    ),
    "outage_code": frozenset(
        {"WRITE", "FSYNC", "PERMISSION", "CAPACITY", "HASH", "SEQUENCE", "SCHEMA", "UNKNOWN_RESULT"}
    ),
}

_DECIMAL_FIELDS: Final = frozenset(
    {
        "requested_qty",
        "approved_qty",
        "quote_cap",
        "qty",
        "trigger_price",
        "cum_exec_qty",
        "cum_exec_value",
        "leaves_qty",
        "avg_price",
        "exec_qty",
        "exec_price",
        "exec_value",
        "fee_amount",
        "executed_base_qty",
        "received_quote_value",
        "buy_exec_qty",
        "sell_exec_qty",
        "entry_exec_value",
        "exit_exec_value",
        "quote_fee",
        "base_fee",
        "position_base_qty",
        "entry_base_qty",
        "exit_base_qty",
        "gross_quote",
        "net_quote",
    }
)
_NULLABLE_DECIMALS: Final = frozenset({"trigger_price", "avg_price", "net_quote"})
_NONNEGATIVE_DECIMALS: Final = _DECIMAL_FIELDS - frozenset(
    {"position_base_qty", "gross_quote", "net_quote"}
)

_EVENT_REF_FIELDS: Final = frozenset(
    {
        "decision_event_id",
        "risk_event_id",
        "key_event_id",
        "intent_event_id",
        "attempt_event_id",
        "episode_open_event_id",
        "terminal_reconciliation_event_id",
        "target_event_id",
        "replacement_event_id",
        "first_affected_event_id",
        "reconciliation_event_id",
    }
)
_SHA_FIELDS: Final = frozenset(
    {
        "activation_receipt_sha256",
        "config_sha256",
        "independent_review_sha256",
        "flat_reconciliation_sha256",
        "rollback_config_sha256",
        "client_key_sha256",
        "series_sha256",
        "target_event_sha256",
        "incident_sha256",
        "recovery_record_sha256",
        "approval_sha256",
        "prior_head_sha256",
    }
)
_PRIVATE_ALIAS_FIELDS: Final = frozenset(
    {"strategy_alias", "cost_alias", "risk_alias", "order_alias", "execution_alias", "fee_alias"}
)
_BOOLEAN_FIELDS: Final = frozenset(
    {
        "risk_increasing",
        "third_fee_present",
        "flat",
        "all_pages_complete",
        "risk_reduction_occurred",
    }
)


def _reject_constant(value: object) -> None:
    raise StageBEvidenceError("typed evidence field is invalid")


def _reject_duplicate_key(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StageBEvidenceError("JSON contains duplicate keys")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, label: str) -> dict[str, object]:
    if not raw or raw.startswith(b"\xef\xbb\xbf"):
        raise StageBEvidenceError(f"{label} is not canonical JSON")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_key,
            parse_float=_reject_constant,
            parse_int=int,
            parse_constant=_reject_constant,
        )
    except StageBEvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StageBEvidenceError(f"{label} is not canonical JSON") from exc
    if not isinstance(parsed, dict):
        raise StageBEvidenceError(f"{label} must be a JSON object")
    if canonical_json_bytes(parsed) != raw:
        raise StageBEvidenceError(f"{label} bytes are not canonical")
    return parsed


def _validate_json_value(value: object) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise StageBEvidenceError("canonical JSON object key is invalid")
        for item in value.values():
            _validate_json_value(item)
        return
    raise StageBEvidenceError("canonical JSON value type is invalid")


def canonical_json_bytes(value: object) -> bytes:
    """Return strict UTF-8 canonical JSON bytes without a trailing newline."""

    _validate_json_value(value)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StageBEvidenceError("canonical JSON serialization failed") from exc


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def canonical_utc(value: datetime | str) -> str:
    """Validate or convert a timestamp to exact six-digit UTC form."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise StageBEvidenceError("UTC timestamp must be timezone-aware")
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise StageBEvidenceError("UTC timestamp is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise StageBEvidenceError("UTC timestamp is invalid") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise StageBEvidenceError("UTC timestamp is invalid")
    return value


def exact_decimal(
    value: object, *, nonnegative: bool = False, nullable: bool = False
) -> Decimal | None:
    """Validate an exact decimal JSON string and return its Decimal value."""

    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise StageBEvidenceError("exact decimal field is invalid")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise StageBEvidenceError("exact decimal field is invalid") from exc
    if not parsed.is_finite() or (parsed.is_zero() and value.startswith("-")):
        raise StageBEvidenceError("exact decimal field is invalid")
    if nonnegative and parsed < 0:
        raise StageBEvidenceError("economic decimal cannot be negative")
    return parsed


def decimal_text(value: Decimal) -> str:
    """Serialize a finite Decimal to the Stage B exact-decimal grammar."""

    if not value.is_finite():
        raise StageBEvidenceError("exact decimal field is invalid")
    if value.is_zero():
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if not _DECIMAL.fullmatch(text):
        raise StageBEvidenceError("exact decimal result exceeds schema bounds")
    return text


def _require_exact_fields(value: Mapping[str, object], expected: Iterable[str], label: str) -> None:
    if set(value) != set(expected):
        raise StageBEvidenceError(f"{label} fields are invalid")


def _strict_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _strict_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


def _require_regex(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise StageBEvidenceError(f"{label} is invalid")
    return value


def _require_enum(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value not in _ENUM_FIELDS[field_name]:
        raise StageBEvidenceError(f"{field_name} enum is invalid")
    return value


def _require_int(value: object, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise StageBEvidenceError(f"{label} integer is invalid")
    return value


def _validate_payload_field(field_name: str, value: object) -> None:
    if field_name in _DECIMAL_FIELDS:
        exact_decimal(
            value,
            nonnegative=field_name in _NONNEGATIVE_DECIMALS,
            nullable=field_name in _NULLABLE_DECIMALS,
        )
    elif field_name in _ENUM_FIELDS:
        if field_name == "ineligibility_code" and value is None:
            return
        _require_enum(value, field_name)
    elif field_name in _EVENT_REF_FIELDS:
        if value is None and field_name in {"replacement_event_id", "first_affected_event_id"}:
            return
        _require_regex(value, _EVENT_ALIAS, field_name)
    elif field_name in _SHA_FIELDS:
        _require_regex(value, _SHA256, field_name)
    elif field_name in _PRIVATE_ALIAS_FIELDS:
        alias = _require_regex(value, _PRIVATE_ALIAS, field_name)
        required_prefix = {
            "strategy_alias": "strategy_",
            "cost_alias": "cost_",
            "risk_alias": "risk_",
            "order_alias": "ord_",
            "execution_alias": "exe_",
            "fee_alias": "fee_",
        }[field_name]
        if not alias.startswith(required_prefix):
            raise StageBEvidenceError(f"{field_name} type is invalid")
    elif field_name in _BOOLEAN_FIELDS:
        if type(value) is not bool:
            raise StageBEvidenceError(f"{field_name} boolean is invalid")
    elif field_name == "client_key":
        _require_regex(value, _CLIENT_KEY, field_name)
    elif field_name == "controlled_restart_id":
        _require_regex(value, _RESTART_ID, field_name)
    elif field_name == "repo_commit":
        _require_regex(value, _COMMIT, field_name)
    elif field_name == "symbol":
        if value != "ETHUSDT":
            raise StageBEvidenceError("symbol is invalid")
    elif field_name == "timeframe":
        if value != "1h":
            raise StageBEvidenceError("timeframe is invalid")
    elif field_name == "attempt_ordinal":
        _require_int(value, field_name, 1, MAX_SEQUENCE)
    elif field_name == "episode_ordinal":
        _require_int(value, field_name, 1, MAX_SEQUENCE)
    elif field_name == "venue_code":
        _require_int(value, field_name, -(2**31), 2**31 - 1)
    else:
        raise StageBEvidenceError("unrecognized typed evidence field")


def _validate_payload_combinations(event_type: EventType, payload: Mapping[str, object]) -> None:
    if event_type is EventType.DECISION_OBSERVED:
        decision = payload["decision"]
        side = payload["side"]
        unit = payload["quantity_unit"]
        requested = cast(Decimal, exact_decimal(payload["requested_qty"], nonnegative=True))
        if decision == "ENTRY" and (
            side != "BUY" or unit not in {"BASE", "QUOTE"} or requested <= 0
        ):
            raise StageBEvidenceError("entry decision combination is invalid")
        if decision == "NO_ACTION" and (side != "NONE" or unit != "NONE" or requested != 0):
            raise StageBEvidenceError("no-action decision combination is invalid")
        if decision in {"EXIT", "STOP"} and side != "SELL":
            raise StageBEvidenceError("risk-reducing decision side is invalid")
    elif event_type is EventType.RISK_VERDICT_OBSERVED:
        verdict = payload["verdict"]
        approved = cast(Decimal, exact_decimal(payload["approved_qty"], nonnegative=True))
        if verdict == "ALLOW_RISK_INCREASE" and (
            payload["reason_code"] != "POLICY_PASS" or approved <= 0
        ):
            raise StageBEvidenceError("allow-risk verdict combination is invalid")
        if verdict == "BLOCK" and approved != 0:
            raise StageBEvidenceError("blocked verdict quantity must be zero")
    elif event_type is EventType.IDEMPOTENCY_KEY_RESERVED:
        key = cast(str, payload["client_key"])
        if payload["client_key_sha256"] != sha256_bytes(key.encode("ascii")):
            raise StageBEvidenceError("client key digest binding is invalid")
    elif event_type is EventType.SUBMISSION_INTENT_COMMITTED:
        kind = payload["order_kind"]
        side = payload["side"]
        risk_increasing = payload["risk_increasing"]
        trigger = payload["trigger_price"]
        if kind == "ENTRY" and (side != "BUY" or risk_increasing is not True):
            raise StageBEvidenceError("entry intent combination is invalid")
        if kind != "ENTRY" and risk_increasing is not False:
            raise StageBEvidenceError("risk-reducing intent combination is invalid")
        if payload["order_type"] == "MARKET" and trigger is not None:
            raise StageBEvidenceError("market intent trigger must be null")
        if payload["order_type"] == "STOP_MARKET" and trigger is None:
            raise StageBEvidenceError("stop intent trigger is required")
    elif event_type is EventType.SUBMISSION_ATTEMPTED:
        if payload["endpoint"] == "CREATE" and payload["attempt_ordinal"] != 1:
            raise StageBEvidenceError("create attempt ordinal must be one")
    elif event_type is EventType.VENUE_ACKNOWLEDGED:
        if payload["result_code"] != "ACCEPTED_PENDING":
            raise StageBEvidenceError("acknowledgement result is invalid")
    elif event_type is EventType.VENUE_REJECTED:
        if payload["result_code"] not in {"POLICY_REJECTED", "VENUE_REJECTED"}:
            raise StageBEvidenceError("rejection result is invalid")
    elif event_type is EventType.SUBMISSION_RESULT_UNKNOWN:
        if payload["result_code"] not in {"TIMEOUT", "DISCONNECT", "MALFORMED", "UNKNOWN"}:
            raise StageBEvidenceError("unknown submission result is invalid")
    elif event_type is EventType.FILL_OBSERVED:
        if payload["side"] not in {"BUY", "SELL"}:
            raise StageBEvidenceError("fill side is invalid")
    elif event_type is EventType.CLOSED_EPISODE_COMMITTED:
        eligible = payload["eligibility"] == "ELIGIBLE"
        third_fee = payload["third_fee_present"] is True
        if eligible and (payload["ineligibility_code"] is not None or payload["net_quote"] is None):
            raise StageBEvidenceError("eligible episode fields are inconsistent")
        if not eligible and payload["ineligibility_code"] in {None, "NONE"}:
            raise StageBEvidenceError("ineligible episode code is required")
        if third_fee and (eligible or payload["net_quote"] is not None):
            raise StageBEvidenceError("third-currency fee episode must be ineligible")
        if not third_fee and payload["net_quote"] is None:
            raise StageBEvidenceError("net quote is required without a third-currency fee")
        with localcontext(_EXACT_DECIMAL_CONTEXT):
            gross = cast(Decimal, exact_decimal(payload["gross_quote"]))
            entry = cast(Decimal, exact_decimal(payload["entry_exec_value"], nonnegative=True))
            exit_value = cast(Decimal, exact_decimal(payload["exit_exec_value"], nonnegative=True))
            quote_fee = cast(Decimal, exact_decimal(payload["quote_fee"], nonnegative=True))
            if gross != exit_value - entry:
                raise StageBEvidenceError("episode gross quote formula is invalid")
            if payload["net_quote"] is not None:
                net = cast(Decimal, exact_decimal(payload["net_quote"]))
                if net != gross - quote_fee:
                    raise StageBEvidenceError("episode net quote formula is invalid")


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    """One deny-unknown, content-addressed Stage B event."""

    event_id: str
    sequence: int
    previous_event_sha256: str | None
    activation_epoch: str
    event_type: EventType
    recorded_at: str
    payload: Mapping[str, object]
    schema: str = EVENT_SCHEMA

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        previous_event_sha256: str | None,
        activation_epoch: str,
        event_type: EventType | str,
        recorded_at: datetime | str,
        payload: Mapping[str, object],
    ) -> EvidenceEvent:
        try:
            parsed_type = EventType(event_type)
        except (ValueError, TypeError) as exc:
            raise StageBEvidenceError("event type is invalid") from exc
        provisional: dict[str, object] = {
            "schema": EVENT_SCHEMA,
            "sequence": sequence,
            "previous_event_sha256": previous_event_sha256,
            "activation_epoch": activation_epoch,
            "event_type": parsed_type.value,
            "recorded_at": canonical_utc(recorded_at),
            "payload": dict(payload),
        }
        event_id = f"evt_{canonical_sha256(provisional)}"
        event = cls(
            event_id=event_id,
            sequence=sequence,
            previous_event_sha256=previous_event_sha256,
            activation_epoch=activation_epoch,
            event_type=parsed_type,
            recorded_at=cast(str, provisional["recorded_at"]),
            payload=dict(payload),
        )
        validate_event(event)
        return event

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> EvidenceEvent:
        _require_exact_fields(
            raw,
            {
                "schema",
                "event_id",
                "sequence",
                "previous_event_sha256",
                "activation_epoch",
                "event_type",
                "recorded_at",
                "payload",
            },
            "event envelope",
        )
        if not isinstance(raw["payload"], Mapping):
            raise StageBEvidenceError("event payload must be an object")
        try:
            parsed_type = EventType(cast(str, raw["event_type"]))
        except (ValueError, TypeError) as exc:
            raise StageBEvidenceError("event type is invalid") from exc
        event = cls(
            schema=cast(str, raw["schema"]),
            event_id=cast(str, raw["event_id"]),
            sequence=cast(int, raw["sequence"]),
            previous_event_sha256=cast(str | None, raw["previous_event_sha256"]),
            activation_epoch=cast(str, raw["activation_epoch"]),
            event_type=parsed_type,
            recorded_at=cast(str, raw["recorded_at"]),
            payload=dict(cast(Mapping[str, object], raw["payload"])),
        )
        validate_event(event)
        return event

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "previous_event_sha256": self.previous_event_sha256,
            "activation_epoch": self.activation_epoch,
            "event_type": self.event_type.value,
            "recorded_at": self.recorded_at,
            "payload": dict(self.payload),
        }

    def frame(self) -> bytes:
        raw = canonical_json_bytes(self.to_dict()) + b"\n"
        if len(raw) > MAX_FRAME_BYTES:
            raise StageBEvidenceError("event frame exceeds 64 KiB")
        return raw

    @property
    def frame_sha256(self) -> str:
        return sha256_bytes(self.frame())


def validate_event(event: EvidenceEvent) -> None:
    if event.schema != EVENT_SCHEMA:
        raise StageBEvidenceError("event schema is invalid")
    _require_regex(event.event_id, _EVENT_ALIAS, "event_id")
    _require_int(event.sequence, "sequence", 1, MAX_SEQUENCE)
    if event.sequence == 1:
        if event.previous_event_sha256 is not None:
            raise StageBEvidenceError("first event parent must be null")
    else:
        _require_regex(event.previous_event_sha256, _SHA256, "previous_event_sha256")
    _require_regex(event.activation_epoch, _ACTIVATION_EPOCH, "activation_epoch")
    canonical_utc(event.recorded_at)
    expected_fields = _PAYLOAD_FIELDS[event.event_type]
    _require_exact_fields(event.payload, expected_fields, f"{event.event_type.value} payload")
    for field_name in expected_fields:
        _validate_payload_field(field_name, event.payload[field_name])
    _validate_payload_combinations(event.event_type, event.payload)
    unsigned = event.to_dict()
    unsigned.pop("event_id")
    if event.event_id != f"evt_{canonical_sha256(unsigned)}":
        raise StageBEvidenceError("event content address is invalid")
    event.frame()


def parse_event_frame(raw: bytes) -> EvidenceEvent:
    if not raw.endswith(b"\n") or len(raw) > MAX_FRAME_BYTES:
        raise StageBEvidenceError("event frame boundary is invalid")
    parsed = _decode_json(raw[:-1], label="event frame")
    event = EvidenceEvent.from_mapping(parsed)
    if event.frame() != raw:
        raise StageBEvidenceError("event frame is not canonical")
    return event


def next_event(
    prior: EvidenceEvent | None,
    *,
    activation_epoch: str,
    event_type: EventType | str,
    payload: Mapping[str, object],
    recorded_at: datetime | str | None = None,
) -> EvidenceEvent:
    """Build the next canonical event without performing any I/O."""

    if prior is not None and prior.activation_epoch != activation_epoch:
        raise StageBEvidenceError("activation epoch changed within a chain")
    return EvidenceEvent.create(
        sequence=1 if prior is None else prior.sequence + 1,
        previous_event_sha256=None if prior is None else prior.frame_sha256,
        activation_epoch=activation_epoch,
        event_type=event_type,
        recorded_at=datetime.now(UTC) if recorded_at is None else recorded_at,
        payload=payload,
    )


@dataclass(frozen=True, slots=True)
class ExecutionEconomics:
    buy_exec_qty: Decimal
    sell_exec_qty: Decimal
    entry_exec_value: Decimal
    exit_exec_value: Decimal
    quote_fee: Decimal
    base_fee: Decimal
    third_fee_present: bool
    position_base_qty: Decimal
    gross_quote: Decimal
    net_quote: Decimal | None

    def as_strings(self) -> dict[str, object]:
        return {
            "buy_exec_qty": decimal_text(self.buy_exec_qty),
            "sell_exec_qty": decimal_text(self.sell_exec_qty),
            "entry_exec_value": decimal_text(self.entry_exec_value),
            "exit_exec_value": decimal_text(self.exit_exec_value),
            "quote_fee": decimal_text(self.quote_fee),
            "base_fee": decimal_text(self.base_fee),
            "third_fee_present": self.third_fee_present,
            "position_base_qty": decimal_text(self.position_base_qty),
            "gross_quote": decimal_text(self.gross_quote),
            "net_quote": None if self.net_quote is None else decimal_text(self.net_quote),
        }


def execution_economics(fills: Iterable[EvidenceEvent]) -> ExecutionEconomics:
    """Compute exact execution-owned cashflow and quantity economics."""

    with localcontext(_EXACT_DECIMAL_CONTEXT):
        seen: dict[str, bytes] = {}
        buy_qty = Decimal(0)
        sell_qty = Decimal(0)
        entry_value = Decimal(0)
        exit_value = Decimal(0)
        quote_fee = Decimal(0)
        base_fee = Decimal(0)
        buy_base_fee = Decimal(0)
        sell_base_fee = Decimal(0)
        third_fee_present = False
        for event in fills:
            if event.event_type is not EventType.FILL_OBSERVED:
                raise StageBEvidenceError("execution accounting received a non-fill event")
            alias = cast(str, event.payload["execution_alias"])
            prior = seen.get(alias)
            current = event.frame()
            if prior is not None:
                if prior != current:
                    raise StageBEvidenceError("conflicting duplicate execution alias")
                continue
            seen[alias] = current
            qty = cast(Decimal, exact_decimal(event.payload["exec_qty"], nonnegative=True))
            value = cast(Decimal, exact_decimal(event.payload["exec_value"], nonnegative=True))
            fee = cast(Decimal, exact_decimal(event.payload["fee_amount"], nonnegative=True))
            side = event.payload["side"]
            currency = event.payload["fee_currency"]
            if side == "BUY":
                buy_qty += qty
                entry_value += value
            elif side == "SELL":
                sell_qty += qty
                exit_value += value
            else:
                raise StageBEvidenceError("fill side cannot be NONE")
            if currency == "USDT":
                quote_fee += fee
            elif currency == "ETH":
                base_fee += fee
                if side == "BUY":
                    buy_base_fee += fee
                else:
                    sell_base_fee += fee
            elif fee != 0:
                third_fee_present = True
        position = (buy_qty - buy_base_fee) - (sell_qty + sell_base_fee)
        gross = exit_value - entry_value
        return ExecutionEconomics(
            buy_exec_qty=buy_qty,
            sell_exec_qty=sell_qty,
            entry_exec_value=entry_value,
            exit_exec_value=exit_value,
            quote_fee=quote_fee,
            base_fee=base_fee,
            third_fee_present=third_fee_present,
            position_base_qty=position,
            gross_quote=gross,
            net_quote=None if third_fee_present else gross - quote_fee,
        )


@dataclass(slots=True)
class _Episode:
    ordinal: int
    open_event_id: str
    entry_order_alias: str
    cohort_number: int
    order_aliases: set[str] = field(default_factory=set)
    fills: list[EvidenceEvent] = field(default_factory=list)
    close_event: EvidenceEvent | None = None
    permanently_ineligible: bool = False


@dataclass(slots=True)
class _Series:
    series_number: int
    series_sha256: str
    strategy_alias: str
    cost_alias: str
    risk_alias: str
    episodes: list[_Episode] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReducedEvidence:
    """Validated chain result used for private state and public projection."""

    reducer_state: dict[str, object]
    public_projection: dict[str, object]
    events: tuple[EvidenceEvent, ...]


def _series_identity(
    activation_epoch: str, strategy_alias: str, cost_alias: str, risk_alias: str
) -> str:
    return canonical_sha256(
        {
            "activation_epoch": activation_epoch,
            "strategy_alias": strategy_alias,
            "cost_alias": cost_alias,
            "risk_alias": risk_alias,
        }
    )


def _zero_aggregate() -> dict[str, object]:
    return {
        "closed_count": 0,
        "positive_count": 0,
        "negative_count": 0,
        "flat_count": 0,
        "entry_exec_value_total": Decimal(0),
        "exit_exec_value_total": Decimal(0),
        "gross_quote_total": Decimal(0),
        "quote_fee_total": Decimal(0),
        "base_fee_total": Decimal(0),
        "net_quote_total": Decimal(0),
    }


def _accumulate_episode(aggregate: dict[str, object], event: EvidenceEvent) -> None:
    payload = event.payload
    net = cast(Decimal, exact_decimal(payload["net_quote"]))
    aggregate["closed_count"] = cast(int, aggregate["closed_count"]) + 1
    if net > 0:
        aggregate["positive_count"] = cast(int, aggregate["positive_count"]) + 1
    elif net < 0:
        aggregate["negative_count"] = cast(int, aggregate["negative_count"]) + 1
    else:
        aggregate["flat_count"] = cast(int, aggregate["flat_count"]) + 1
    with localcontext(_EXACT_DECIMAL_CONTEXT):
        for target, source in (
            ("entry_exec_value_total", "entry_exec_value"),
            ("exit_exec_value_total", "exit_exec_value"),
            ("gross_quote_total", "gross_quote"),
            ("quote_fee_total", "quote_fee"),
            ("base_fee_total", "base_fee"),
            ("net_quote_total", "net_quote"),
        ):
            aggregate[target] = cast(Decimal, aggregate[target]) + cast(
                Decimal, exact_decimal(payload[source])
            )


def _public_aggregate(aggregate: Mapping[str, object]) -> dict[str, object]:
    return {
        "closed_count": aggregate["closed_count"],
        "positive_count": aggregate["positive_count"],
        "negative_count": aggregate["negative_count"],
        "flat_count": aggregate["flat_count"],
        "entry_exec_value_total": decimal_text(cast(Decimal, aggregate["entry_exec_value_total"])),
        "exit_exec_value_total": decimal_text(cast(Decimal, aggregate["exit_exec_value_total"])),
        "gross_quote_total": decimal_text(cast(Decimal, aggregate["gross_quote_total"])),
        "quote_fee_total": decimal_text(cast(Decimal, aggregate["quote_fee_total"])),
        "base_fee_total": decimal_text(cast(Decimal, aggregate["base_fee_total"])),
        "net_quote_total": decimal_text(cast(Decimal, aggregate["net_quote_total"])),
    }


def _cohorts_for_series(series: _Series) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    private_cohorts: list[dict[str, object]] = []
    public_cohorts: list[dict[str, object]] = []
    if not series.episodes:
        return private_cohorts, public_cohorts
    cohort_count = series.episodes[-1].cohort_number
    for cohort_number in range(1, cohort_count + 1):
        episodes = [
            episode for episode in series.episodes if episode.cohort_number == cohort_number
        ]
        assigned = len(episodes)
        eligible = [
            episode
            for episode in episodes
            if episode.close_event is not None
            and not episode.permanently_ineligible
            and episode.close_event.payload["eligibility"] == "ELIGIBLE"
        ]
        ineligible = [
            episode
            for episode in episodes
            if episode.permanently_ineligible
            or (
                episode.close_event is not None
                and episode.close_event.payload["eligibility"] == "PERMANENTLY_INELIGIBLE"
            )
        ]
        open_count = assigned - len(eligible) - len(ineligible)
        aggregate: dict[str, object] | None = None
        readiness = "COLLECTING"
        if ineligible:
            readiness = "PERMANENTLY_INELIGIBLE"
        elif assigned == COHORT_SIZE and len(eligible) == COHORT_SIZE and open_count == 0:
            running = _zero_aggregate()
            for episode in eligible:
                if episode.close_event is None:
                    raise StageBEvidenceError("closed cohort lost its close event")
                _accumulate_episode(running, episode.close_event)
            aggregate = _public_aggregate(running)
            readiness = "COMPLETE"
        common: dict[str, object] = {
            "cohort_number": cohort_number,
            "assigned_count": assigned,
            "eligible_closed_count": len(eligible),
            "ineligible_count": len(ineligible),
            "open_count": open_count,
            "aggregate": aggregate,
        }
        private_cohorts.append(dict(common))
        public_cohorts.append(
            {
                "cohort_number": cohort_number,
                "assigned_count": assigned,
                "eligible_closed_count": len(eligible),
                "ineligible_count": len(ineligible),
                "open_count": open_count,
                "readiness": readiness,
                "aggregate": aggregate,
            }
        )
    return private_cohorts, public_cohorts


def _validate_chain_order(events: Sequence[EvidenceEvent]) -> None:
    prior: EvidenceEvent | None = None
    seen_ids: dict[str, bytes] = {}
    for event in events:
        validate_event(event)
        if event.event_id in seen_ids:
            if seen_ids[event.event_id] != event.frame():
                raise StageBEvidenceError("conflicting duplicate event")
            raise StageBEvidenceError("duplicate event appears inside one chain")
        seen_ids[event.event_id] = event.frame()
        if prior is None:
            if event.sequence != 1 or event.previous_event_sha256 is not None:
                raise StageBEvidenceError("event chain must begin at sequence one")
        elif (
            event.sequence != prior.sequence + 1
            or event.previous_event_sha256 != prior.frame_sha256
            or event.activation_epoch != prior.activation_epoch
        ):
            raise StageBEvidenceError("event sequence or parent binding is invalid")
        prior = event


def _validate_generation_batch(events: Sequence[EvidenceEvent]) -> None:
    """Validate one manifest-local batch; its first parent is checked by the chain reader."""

    if not events:
        raise StageBEvidenceError("generation event batch cannot be empty")
    prior: EvidenceEvent | None = None
    seen_ids: dict[str, bytes] = {}
    for event in events:
        validate_event(event)
        if event.event_id in seen_ids:
            if seen_ids[event.event_id] != event.frame():
                raise StageBEvidenceError("conflicting duplicate event")
            raise StageBEvidenceError("duplicate event appears inside one generation")
        seen_ids[event.event_id] = event.frame()
        if prior is None:
            if event.sequence == 1 and event.previous_event_sha256 is not None:
                raise StageBEvidenceError("genesis event parent must be null")
            if event.sequence > 1 and event.previous_event_sha256 is None:
                raise StageBEvidenceError("non-genesis batch must bind a prior event")
        elif (
            event.sequence != prior.sequence + 1
            or event.previous_event_sha256 != prior.frame_sha256
            or event.activation_epoch != prior.activation_epoch
        ):
            raise StageBEvidenceError("generation-local sequence or parent binding is invalid")
        prior = event


def _matching_reference(
    event_by_id: Mapping[str, EvidenceEvent],
    reference: object,
    expected: EventType | tuple[EventType, ...],
) -> EvidenceEvent:
    target = event_by_id.get(cast(str, reference))
    allowed = (expected,) if isinstance(expected, EventType) else expected
    if target is None or target.event_type not in allowed:
        raise StageBEvidenceError("typed event reference is invalid")
    return target


def _validate_terminal_against_fills(event: EvidenceEvent, fills: Sequence[EvidenceEvent]) -> None:
    payload = event.payload
    economics = execution_economics(fills)
    expected = economics.as_strings()
    for field_name in (
        "buy_exec_qty",
        "sell_exec_qty",
        "entry_exec_value",
        "exit_exec_value",
        "quote_fee",
        "base_fee",
        "position_base_qty",
    ):
        if payload[field_name] != expected[field_name]:
            raise StageBEvidenceError("terminal reconciliation economics disagree with fills")
    if payload["third_fee_present"] is not economics.third_fee_present:
        raise StageBEvidenceError("terminal reconciliation fee state disagrees with fills")
    if payload["flat"] is not (economics.position_base_qty == 0):
        raise StageBEvidenceError("terminal reconciliation flat state is invalid")


def _validate_close_against_terminal(event: EvidenceEvent, terminal: EvidenceEvent) -> None:
    payload = event.payload
    terminal_payload = terminal.payload
    exact_pairs = (
        ("entry_base_qty", "buy_exec_qty"),
        ("exit_base_qty", "sell_exec_qty"),
        ("entry_exec_value", "entry_exec_value"),
        ("exit_exec_value", "exit_exec_value"),
        ("quote_fee", "quote_fee"),
        ("base_fee", "base_fee"),
        ("third_fee_present", "third_fee_present"),
    )
    for episode_name, terminal_name in exact_pairs:
        if payload[episode_name] != terminal_payload[terminal_name]:
            raise StageBEvidenceError("closed episode disagrees with terminal reconciliation")
    eligible_from_terminal = (
        terminal_payload["flat"] is True
        and terminal_payload["protective_stop_state"] == "CLEAR"
        and terminal_payload["all_pages_complete"] is True
        and terminal_payload["third_fee_present"] is False
    )
    if payload["eligibility"] == "ELIGIBLE" and not eligible_from_terminal:
        raise StageBEvidenceError("episode cannot be eligible before exact flat reconciliation")


def reduce_events(events: Sequence[EvidenceEvent]) -> ReducedEvidence:
    """Validate and reduce one complete activation-epoch event chain."""

    if not events:
        raise StageBEvidenceError("an activated chain must contain ACTIVATION_BOUND")
    _validate_chain_order(events)
    first = events[0]
    if first.event_type is not EventType.ACTIVATION_BOUND:
        raise StageBEvidenceError("first event must bind activation")
    if any(event.event_type is EventType.ACTIVATION_BOUND for event in events[1:]):
        raise StageBEvidenceError("activation may be bound only once per epoch")

    event_by_id: dict[str, EvidenceEvent] = {}
    decisions: dict[str, EvidenceEvent] = {}
    risks: dict[str, EvidenceEvent] = {}
    key_events: dict[str, EvidenceEvent] = {}
    intents_by_order: dict[str, EvidenceEvent] = {}
    attempts: dict[str, EvidenceEvent] = {}
    initial_results: dict[str, EvidenceEvent] = {}
    terminal_by_order: dict[str, EvidenceEvent] = {}
    outstanding_order_aliases: set[str] = set()
    fills_by_order: dict[str, list[EvidenceEvent]] = {}
    execution_aliases: dict[str, bytes] = {}
    client_keys: dict[str, tuple[str, str]] = {}
    permanently_ineligible_orders: set[str] = set()
    order_series: dict[str, str] = {}
    order_episode: dict[str, _Episode] = {}
    event_episode: dict[str, _Episode] = {}
    series_by_sha: dict[str, _Series] = {}
    series_order: list[_Series] = []

    evidence_state = "READY"
    incident_sha256: str | None = None
    unresolved_order_alias: str | None = None
    unresolved_client_key: str | None = None
    flat = True
    protective_stop_state = "CLEAR"
    pending_entry_order_alias: str | None = None

    for event in events:
        event_by_id[event.event_id] = event
        payload = event.payload
        event_type = event.event_type
        if event_type is EventType.ACTIVATION_BOUND:
            continue
        if event_type is EventType.DECISION_OBSERVED:
            decisions[event.event_id] = event
        elif event_type is EventType.RISK_VERDICT_OBSERVED:
            decision = _matching_reference(
                event_by_id, payload["decision_event_id"], EventType.DECISION_OBSERVED
            )
            if decision.payload["quantity_unit"] != payload["quantity_unit"]:
                raise StageBEvidenceError("risk verdict quantity unit changed")
            with localcontext(_EXACT_DECIMAL_CONTEXT):
                requested = cast(
                    Decimal, exact_decimal(decision.payload["requested_qty"], nonnegative=True)
                )
                approved = cast(Decimal, exact_decimal(payload["approved_qty"], nonnegative=True))
                if approved > requested:
                    raise StageBEvidenceError("risk verdict exceeds the observed request")
            verdict = payload["verdict"]
            if verdict == "ALLOW_RISK_INCREASE" and (
                decision.payload["decision"] != "ENTRY"
                or decision.payload["side"] != "BUY"
                or payload["reason_code"] != "POLICY_PASS"
            ):
                raise StageBEvidenceError("risk-increase verdict is not bound to an entry")
            if verdict == "BLOCK" and payload["reason_code"] != "POLICY_BLOCK":
                raise StageBEvidenceError("blocked risk verdict reason is invalid")
            if verdict == "RISK_REDUCING" and (
                decision.payload["decision"] not in {"EXIT", "STOP", "CANCEL"}
                or payload["reason_code"] not in {"EXIT_ONLY", "KILL_SWITCH"}
            ):
                raise StageBEvidenceError("risk-reducing verdict is not bound to a reduction")
            risks[event.event_id] = event
        elif event_type is EventType.IDEMPOTENCY_KEY_RESERVED:
            decision = _matching_reference(
                event_by_id, payload["decision_event_id"], EventType.DECISION_OBSERVED
            )
            risk = _matching_reference(
                event_by_id, payload["risk_event_id"], EventType.RISK_VERDICT_OBSERVED
            )
            if risk.payload["decision_event_id"] != decision.event_id:
                raise StageBEvidenceError("idempotency reservation references disagree")
            if risk.payload["verdict"] == "BLOCK":
                raise StageBEvidenceError("blocked verdict cannot reserve a submission key")
            client_key = cast(str, payload["client_key"])
            order_alias = cast(str, payload["order_alias"])
            if risk.payload["verdict"] == "ALLOW_RISK_INCREASE":
                if evidence_state != "READY":
                    raise StageBEvidenceError("risk increase is forbidden during ENTRY_BLOCK")
                if pending_entry_order_alias is not None:
                    raise StageBEvidenceError(
                        "a risk-increasing reservation is already pending reconciliation"
                    )
                pending_entry_order_alias = order_alias
            prior_key = client_keys.get(client_key)
            key_identity = (event.event_id, order_alias)
            if prior_key is not None and prior_key != key_identity:
                raise StageBEvidenceError("client key collision")
            client_keys[client_key] = key_identity
            key_events[event.event_id] = event
            series_sha = _series_identity(
                event.activation_epoch,
                cast(str, decision.payload["strategy_alias"]),
                cast(str, decision.payload["cost_alias"]),
                cast(str, decision.payload["risk_alias"]),
            )
            order_series[order_alias] = series_sha
        elif event_type is EventType.SUBMISSION_INTENT_COMMITTED:
            key_event = _matching_reference(
                event_by_id, payload["key_event_id"], EventType.IDEMPOTENCY_KEY_RESERVED
            )
            order_alias = cast(str, payload["order_alias"])
            if key_event.payload["order_alias"] != order_alias:
                raise StageBEvidenceError("submission intent order alias changed")
            risk_event = _matching_reference(
                event_by_id, key_event.payload["risk_event_id"], EventType.RISK_VERDICT_OBSERVED
            )
            decision_event = _matching_reference(
                event_by_id,
                key_event.payload["decision_event_id"],
                EventType.DECISION_OBSERVED,
            )
            with localcontext(_EXACT_DECIMAL_CONTEXT):
                intent_qty = cast(Decimal, exact_decimal(payload["qty"], nonnegative=True))
                approved_qty = cast(
                    Decimal, exact_decimal(risk_event.payload["approved_qty"], nonnegative=True)
                )
                if intent_qty > approved_qty:
                    raise StageBEvidenceError("submission intent exceeds the approved quantity")
            if payload["quantity_unit"] != risk_event.payload["quantity_unit"]:
                raise StageBEvidenceError("submission intent quantity unit changed")
            if payload["risk_increasing"] is True:
                if (
                    risk_event.payload["verdict"] != "ALLOW_RISK_INCREASE"
                    or decision_event.payload["decision"] != "ENTRY"
                    or payload["order_kind"] != "ENTRY"
                    or payload["side"] != "BUY"
                ):
                    raise StageBEvidenceError(
                        "risk-increasing intent lacks an allowing entry verdict"
                    )
            elif (
                risk_event.payload["verdict"] != "RISK_REDUCING"
                or decision_event.payload["decision"] not in {"EXIT", "STOP", "CANCEL"}
                or payload["order_kind"] == "ENTRY"
            ):
                raise StageBEvidenceError("risk-reducing intent lacks a risk-reducing verdict")
            if order_alias in intents_by_order:
                raise StageBEvidenceError("order alias has multiple submission intents")
            intents_by_order[order_alias] = event
        elif event_type is EventType.SUBMISSION_ATTEMPTED:
            intent = _matching_reference(
                event_by_id, payload["intent_event_id"], EventType.SUBMISSION_INTENT_COMMITTED
            )
            if intent.payload["order_alias"] != payload["order_alias"]:
                raise StageBEvidenceError("submission attempt order alias changed")
            key_event = _matching_reference(
                event_by_id, intent.payload["key_event_id"], EventType.IDEMPOTENCY_KEY_RESERVED
            )
            if key_event.payload["client_key_sha256"] != payload["client_key_sha256"]:
                raise StageBEvidenceError("submission attempt client-key digest changed")
            if intent.event_id in attempts:
                raise StageBEvidenceError("logical submission has more than one create attempt")
            attempts[intent.event_id] = event
            outstanding_order_aliases.add(cast(str, payload["order_alias"]))
        elif event_type in {
            EventType.VENUE_ACKNOWLEDGED,
            EventType.VENUE_REJECTED,
            EventType.SUBMISSION_RESULT_UNKNOWN,
        }:
            attempt = _matching_reference(
                event_by_id, payload["attempt_event_id"], EventType.SUBMISSION_ATTEMPTED
            )
            if attempt.payload["order_alias"] != payload["order_alias"]:
                raise StageBEvidenceError("submission result order alias changed")
            if attempt.event_id in initial_results:
                raise StageBEvidenceError("submission attempt has multiple initial results")
            initial_results[attempt.event_id] = event
            if event_type is EventType.SUBMISSION_RESULT_UNKNOWN:
                unknown_alias = cast(str, payload["order_alias"])
                permanently_ineligible_orders.add(unknown_alias)
                if evidence_state == "READY":
                    evidence_state = "ENTRY_BLOCK"
                    incident_sha256 = event.frame_sha256
                    unresolved_order_alias = unknown_alias
                    intent = _matching_reference(
                        event_by_id,
                        attempt.payload["intent_event_id"],
                        EventType.SUBMISSION_INTENT_COMMITTED,
                    )
                    key_event = _matching_reference(
                        event_by_id,
                        intent.payload["key_event_id"],
                        EventType.IDEMPOTENCY_KEY_RESERVED,
                    )
                    unresolved_client_key = cast(str, key_event.payload["client_key"])
        elif event_type is EventType.ORDER_UPDATE_OBSERVED:
            update_alias = cast(str, payload["order_alias"])
            update_intent = intents_by_order.get(update_alias)
            if update_intent is None:
                raise StageBEvidenceError("order update has no committed intent")
            update_attempt = attempts.get(update_intent.event_id)
            if update_attempt is None or update_attempt.event_id not in initial_results:
                raise StageBEvidenceError("order update precedes a typed initial result")
            if update_alias in terminal_by_order:
                raise StageBEvidenceError("order update follows terminal reconciliation")
        elif event_type is EventType.FILL_OBSERVED:
            order_alias = cast(str, payload["order_alias"])
            fill_intent = intents_by_order.get(order_alias)
            if fill_intent is None:
                raise StageBEvidenceError("fill has no committed intent")
            fill_attempt = attempts.get(fill_intent.event_id)
            if fill_attempt is None or fill_attempt.event_id not in initial_results:
                raise StageBEvidenceError("fill precedes a typed initial submission result")
            if order_alias in terminal_by_order:
                raise StageBEvidenceError("fill follows terminal reconciliation")
            order_kind = cast(str, fill_intent.payload["order_kind"])
            expected_side = "BUY" if order_kind == "ENTRY" else "SELL"
            if order_kind in {"STOP_CLEANUP", "CANCEL"} or payload["side"] != expected_side:
                raise StageBEvidenceError("fill side or order kind contradicts its intent")
            execution_alias = cast(str, payload["execution_alias"])
            prior = execution_aliases.get(execution_alias)
            if prior is not None:
                if prior != event.frame():
                    raise StageBEvidenceError("conflicting duplicate execution alias")
                raise StageBEvidenceError("duplicate execution event in chain")
            execution_aliases[execution_alias] = event.frame()
            fills_by_order.setdefault(order_alias, []).append(event)
            if (
                order_kind == "ENTRY"
                and payload["side"] == "BUY"
                and cast(Decimal, exact_decimal(payload["exec_qty"], nonnegative=True)) > 0
                and order_alias not in order_episode
            ):
                if any(
                    episode.close_event is None
                    for existing_series in series_order
                    for episode in existing_series.episodes
                ):
                    raise StageBEvidenceError("a new episode cannot overlap an open episode")
                fill_series_sha = order_series.get(order_alias)
                if fill_series_sha is None:
                    raise StageBEvidenceError("filled entry has no immutable series identity")
                fill_series = series_by_sha.get(fill_series_sha)
                if fill_series is None:
                    if len(series_order) >= MAX_SERIES:
                        raise StageBEvidenceError("series limit exceeded")
                    key_event = _matching_reference(
                        event_by_id,
                        fill_intent.payload["key_event_id"],
                        EventType.IDEMPOTENCY_KEY_RESERVED,
                    )
                    decision = _matching_reference(
                        event_by_id,
                        key_event.payload["decision_event_id"],
                        EventType.DECISION_OBSERVED,
                    )
                    fill_series = _Series(
                        series_number=len(series_order) + 1,
                        series_sha256=fill_series_sha,
                        strategy_alias=cast(str, decision.payload["strategy_alias"]),
                        cost_alias=cast(str, decision.payload["cost_alias"]),
                        risk_alias=cast(str, decision.payload["risk_alias"]),
                    )
                    series_by_sha[fill_series_sha] = fill_series
                    series_order.append(fill_series)
                ordinal = len(fill_series.episodes) + 1
                new_episode = _Episode(
                    ordinal=ordinal,
                    open_event_id=event.event_id,
                    entry_order_alias=order_alias,
                    cohort_number=((ordinal - 1) // COHORT_SIZE) + 1,
                    order_aliases={order_alias},
                    permanently_ineligible=order_alias in permanently_ineligible_orders,
                )
                fill_series.episodes.append(new_episode)
                order_episode[order_alias] = new_episode
                event_episode[event.event_id] = new_episode
            fill_episode = order_episode.get(order_alias)
            if order_kind != "ENTRY" and fill_episode is None:
                raise StageBEvidenceError(
                    "risk-reducing fill lacks an explicit episode exit association"
                )
            if fill_episode is not None:
                event_episode[event.event_id] = fill_episode
                fill_episode.fills.append(event)
            flat = False
        elif event_type is EventType.CANCEL_OBSERVED:
            cancel_alias = cast(str, payload["order_alias"])
            cancel_intent = intents_by_order.get(cancel_alias)
            if cancel_intent is None:
                raise StageBEvidenceError("cancel observation has no committed intent")
            cancel_attempt = attempts.get(cancel_intent.event_id)
            if cancel_attempt is None or cancel_attempt.event_id not in initial_results:
                raise StageBEvidenceError("cancel observation precedes a typed initial result")
            if cancel_alias in terminal_by_order:
                raise StageBEvidenceError("cancel observation follows terminal reconciliation")
        elif event_type is EventType.EXIT_UPDATE_OBSERVED:
            exit_alias = cast(str, payload["order_alias"])
            exit_intent = intents_by_order.get(exit_alias)
            if exit_intent is None:
                raise StageBEvidenceError("exit update has no committed intent")
            exit_attempt = attempts.get(exit_intent.event_id)
            if exit_attempt is None or exit_attempt.event_id not in initial_results:
                raise StageBEvidenceError("exit update precedes a typed initial result")
            if exit_alias in terminal_by_order:
                raise StageBEvidenceError("exit update follows terminal reconciliation")
            if (
                exit_intent.payload["order_kind"] not in {"EXIT", "STOP_CREATE", "STOP_REPLACE"}
                or exit_intent.payload["side"] != "SELL"
                or exit_intent.payload["risk_increasing"] is not False
            ):
                raise StageBEvidenceError("exit update is not risk-reducing")
            exit_episode = event_episode.get(cast(str, payload["episode_open_event_id"]))
            if exit_episode is None or exit_episode.close_event is not None:
                raise StageBEvidenceError("exit update references no open episode")
            prior_episode = order_episode.get(exit_alias)
            if prior_episode is not None and prior_episode is not exit_episode:
                raise StageBEvidenceError("exit order is associated with multiple episodes")
            order_episode[exit_alias] = exit_episode
            exit_episode.order_aliases.add(exit_alias)
            event_episode[event.event_id] = exit_episode
        elif event_type is EventType.TERMINAL_RECONCILIATION_COMMITTED:
            order_alias = cast(str, payload["order_alias"])
            terminal_intent = intents_by_order.get(order_alias)
            whole_lane_reconciliation = (
                terminal_intent is None
                and evidence_state == "ENTRY_BLOCK"
                and unresolved_order_alias is None
                and order_alias == _WHOLE_LANE_RECONCILIATION_ALIAS
                and payload["flat"] is True
                and payload["protective_stop_state"] == "CLEAR"
                and payload["all_pages_complete"] is True
            )
            if terminal_intent is None and not whole_lane_reconciliation:
                raise StageBEvidenceError("terminal reconciliation has no committed intent")
            if terminal_intent is not None:
                terminal_attempt = attempts.get(terminal_intent.event_id)
                if terminal_attempt is None or terminal_attempt.event_id not in initial_results:
                    raise StageBEvidenceError(
                        "terminal reconciliation precedes a typed initial submission result"
                    )
            if order_alias in terminal_by_order and evidence_state != "ENTRY_BLOCK":
                raise StageBEvidenceError("order has multiple terminal reconciliations")
            terminal_episode = order_episode.get(order_alias)
            terminal_fills = (
                terminal_episode.fills
                if terminal_episode is not None
                else fills_by_order.get(order_alias, [])
            )
            _validate_terminal_against_fills(event, terminal_fills)
            if payload["flat"] is True and any(
                episode.close_event is None and episode is not terminal_episode
                for existing_series in series_order
                for episode in existing_series.episodes
            ):
                raise StageBEvidenceError(
                    "flat reconciliation does not account for the open episode"
                )
            terminal_by_order[order_alias] = event
            outstanding_order_aliases.discard(order_alias)
            if terminal_episode is not None:
                event_episode[event.event_id] = terminal_episode
            if pending_entry_order_alias == order_alias and payload["all_pages_complete"] is True:
                pending_entry_order_alias = None
            flat = payload["flat"] is True
            protective_stop_state = cast(str, payload["protective_stop_state"])
        elif event_type is EventType.CLOSED_EPISODE_COMMITTED:
            terminal = _matching_reference(
                event_by_id,
                payload["terminal_reconciliation_event_id"],
                EventType.TERMINAL_RECONCILIATION_COMMITTED,
            )
            _validate_close_against_terminal(event, terminal)
            close_episode = event_episode.get(terminal.event_id)
            if close_episode is None:
                raise StageBEvidenceError("closed episode has no assigned entry ordinal")
            close_series = series_by_sha.get(cast(str, payload["series_sha256"]))
            if (
                close_series is None
                or close_episode not in close_series.episodes
                or payload["episode_ordinal"] != close_episode.ordinal
                or close_episode.close_event is not None
            ):
                raise StageBEvidenceError("closed episode series or ordinal is invalid")
            if close_episode.permanently_ineligible and payload["eligibility"] == "ELIGIBLE":
                raise StageBEvidenceError("an ineligible ordinal cannot become eligible")
            close_episode.close_event = event
            close_episode.permanently_ineligible = (
                close_episode.permanently_ineligible
                or payload["eligibility"] == "PERMANENTLY_INELIGIBLE"
            )
            event_episode[event.event_id] = close_episode
        elif event_type is EventType.CORRECTION_COMMITTED:
            target = _matching_reference(
                event_by_id,
                payload["target_event_id"],
                tuple(EventType),
            )
            if payload["target_event_sha256"] != target.frame_sha256:
                raise StageBEvidenceError("correction target digest is invalid")
            if payload["replacement_event_id"] is not None:
                _matching_reference(event_by_id, payload["replacement_event_id"], tuple(EventType))
            corrected_episode = event_episode.get(target.event_id)
            if corrected_episode is not None:
                corrected_episode.permanently_ineligible = True
            if evidence_state == "READY":
                evidence_state = "ENTRY_BLOCK"
                incident_sha256 = event.frame_sha256
        elif event_type is EventType.EVIDENCE_OUTAGE_RECORDED:
            if payload["first_affected_event_id"] is not None:
                target = _matching_reference(
                    event_by_id, payload["first_affected_event_id"], tuple(EventType)
                )
                outage_episode = event_episode.get(target.event_id)
                if outage_episode is not None:
                    outage_episode.permanently_ineligible = True
            else:
                for series in series_order:
                    for episode in series.episodes:
                        if episode.close_event is None:
                            episode.permanently_ineligible = True
            if evidence_state == "READY":
                evidence_state = "ENTRY_BLOCK"
                incident_sha256 = cast(str, payload["incident_sha256"])
        elif event_type is EventType.RECOVERY_COMMITTED:
            reconciliation = _matching_reference(
                event_by_id,
                payload["reconciliation_event_id"],
                EventType.TERMINAL_RECONCILIATION_COMMITTED,
            )
            if (
                evidence_state != "ENTRY_BLOCK"
                or incident_sha256 != payload["incident_sha256"]
                or reconciliation.payload["flat"] is not True
                or reconciliation.payload["protective_stop_state"] != "CLEAR"
                or reconciliation.payload["all_pages_complete"] is not True
                or outstanding_order_aliases
            ):
                raise StageBEvidenceError("recovery commit lacks fresh flat reconciliation")
            evidence_state = "READY"
            incident_sha256 = None
            unresolved_order_alias = None
            unresolved_client_key = None
            flat = True
            protective_stop_state = "CLEAR"

    for intent_event_id, attempt in attempts.items():
        if attempt.event_id not in initial_results:
            missing_alias = cast(str, attempt.payload["order_alias"])
            permanently_ineligible_orders.add(missing_alias)
            pending_episode = order_episode.get(missing_alias)
            if pending_episode is not None:
                if (
                    pending_episode.close_event is not None
                    and pending_episode.close_event.payload["eligibility"] == "ELIGIBLE"
                ):
                    raise StageBEvidenceError(
                        "an unresolved submission cannot produce an eligible episode"
                    )
                pending_episode.permanently_ineligible = True
            if evidence_state == "READY":
                evidence_state = "ENTRY_BLOCK"
                incident_sha256 = attempt.frame_sha256
                unresolved_order_alias = missing_alias
                intent = event_by_id[intent_event_id]
                key_event = event_by_id[cast(str, intent.payload["key_event_id"])]
                unresolved_client_key = cast(str, key_event.payload["client_key"])

    total_cohorts = sum(
        0 if not series.episodes else series.episodes[-1].cohort_number for series in series_order
    )
    if total_cohorts > MAX_COHORTS:
        raise StageBEvidenceError("cohort limit exceeded")

    private_series: list[dict[str, object]] = []
    public_series: list[dict[str, object]] = []
    for series in series_order:
        private_cohorts, public_cohorts = _cohorts_for_series(series)
        open_events = [
            episode.open_event_id for episode in series.episodes if episode.close_event is None
        ]
        private_series.append(
            {
                "series_number": series.series_number,
                "series_sha256": series.series_sha256,
                "strategy_alias": series.strategy_alias,
                "cost_alias": series.cost_alias,
                "risk_alias": series.risk_alias,
                "next_episode_ordinal": len(series.episodes) + 1,
                "open_episode_event_id": open_events[-1] if open_events else None,
                "cohorts": private_cohorts,
            }
        )
        public_series.append({"series_number": series.series_number, "cohorts": public_cohorts})

    activation_payload = first.payload
    reducer_state: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.reducer_state.v1",
        "activation_epoch": first.activation_epoch,
        "activation_receipt_sha256": activation_payload["activation_receipt_sha256"],
        "controlled_restart_id": activation_payload["controlled_restart_id"],
        "repo_commit": activation_payload["repo_commit"],
        "config_sha256": activation_payload["config_sha256"],
        "last_sequence": events[-1].sequence,
        "last_event_sha256": events[-1].frame_sha256,
        "evidence_state": evidence_state,
        "incident_sha256": incident_sha256,
        "unresolved_order_alias": unresolved_order_alias,
        "unresolved_client_key": unresolved_client_key,
        "flat": flat,
        "protective_stop_state": protective_stop_state,
        "series": private_series,
    }
    public_projection: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.public_projection.v1",
        "status": "ENTRY_BLOCK" if evidence_state != "READY" else "READY",
        "cohort_size": COHORT_SIZE,
        "series": public_series,
    }
    if len(canonical_json_bytes(reducer_state)) > MAX_REDUCER_BYTES:
        raise StageBEvidenceError("reducer state exceeds fixed bound")
    if len(canonical_json_bytes(public_projection)) > MAX_PUBLIC_PROJECTION_BYTES:
        raise StageBEvidenceError("public projection exceeds fixed bound")
    return ReducedEvidence(
        reducer_state=reducer_state,
        public_projection=public_projection,
        events=tuple(events),
    )


_BOUND_FILES: Final = (
    "src/tios/evidence/demo_decision_evidence_v2.py",
    "tests/test_demo_decision_evidence_v2.py",
    "scripts/demo_eth_lane.py",
    "scripts/demo_roundtrip.py",
    "tests/test_demo_eth_lane.py",
    "tests/test_demo_roundtrip.py",
    "src/tios/services/dashboard_api/demo_lane.py",
    "tests/test_demo_lane_api.py",
    "src/tios/services/dashboard_ui/dashboard.html",
    "tests/test_dashboard.py",
    "PROJECT_STATE.md",
    "DECISION_LOG.md",
    "docs/architecture/AD.md",
    "PACKAGE_CHANGELOG.md",
    "PACKAGE_INTEGRITY_MANIFEST.md",
)

_CONFIG_PATHS: Final[dict[str, object]] = {
    "private_root": "artifacts/evidence/private_demo/stage_b_v2",
    "receipt": "activation/ACTIVATION_RECEIPT.json",
    "config": "activation/CONFIG.json",
    "independent_review": "activation/INDEPENDENT_REVIEW.json",
    "flat_reconciliation": "activation/FLAT_RECONCILIATION.json",
    "rollback_config": "activation/ROLLBACK_CONFIG.json",
    "alias_key": "private/install_alias.key",
    "generations": "store/generations",
    "head": "store/HEAD.json",
    "quarantine": "quarantine",
    "recovery": "recovery",
    "lane_state": "artifacts/trading_domain/demo_lane/lane_state.json",
}
_CONFIG_LIMITS: Final[dict[str, object]] = {
    "frame_bytes": MAX_FRAME_BYTES,
    "events_per_generation": MAX_EVENTS_PER_GENERATION,
    "events_bytes": MAX_EVENTS_BYTES,
    "reducer_bytes": MAX_REDUCER_BYTES,
    "public_projection_bytes": MAX_PUBLIC_PROJECTION_BYTES,
    "cohorts_total": MAX_COHORTS,
    "pages_per_endpoint": 100,
    "rows_per_page_internal": 50,
}
_CONFIG_CONTRACTS: Final[dict[str, object]] = {
    "event_schema": EVENT_SCHEMA,
    "cohort_size": COHORT_SIZE,
    "formula": "EXACT_EXECUTION_CASHFLOW_V1",
    "dashboard_schema": "TIOS_DEMO_LANE_GLOBAL_ALLOWLIST_V2",
    "commit_protocol": "FINAL_DIR_MANIFEST_RENAME_V1",
    "create_attempts_per_logical_submission": 1,
}


def expected_config(module_sha256: str) -> dict[str, object]:
    """Return the fixed activation CONFIG payload for offline preparation."""

    _require_regex(module_sha256, _SHA256, "implementation_module_sha256")
    return {
        "schema": "tios.demo_decision_evidence.config.v1",
        "implementation_module_sha256": module_sha256,
        "paths": dict(_CONFIG_PATHS),
        "limits": dict(_CONFIG_LIMITS),
        "contracts": dict(_CONFIG_CONTRACTS),
    }


@dataclass(frozen=True, slots=True)
class ActivationContext:
    """Validated, procedural activation binding; never identity proof."""

    repo_root: Path
    private_root: Path
    receipt: Mapping[str, object]
    receipt_sha256: str
    config: Mapping[str, object]
    config_sha256: str
    independent_review_sha256: str
    flat_reconciliation_sha256: str
    rollback_config_sha256: str

    @property
    def activation_epoch(self) -> str:
        return cast(str, self.receipt["activation_epoch"])

    @property
    def execution_authority(self) -> str:
        return "NONE"


def _expected_activation_bound_payload(
    activation: ActivationContext,
) -> dict[str, object]:
    return {
        "activation_receipt_sha256": activation.receipt_sha256,
        "config_sha256": activation.config_sha256,
        "independent_review_sha256": activation.independent_review_sha256,
        "flat_reconciliation_sha256": activation.flat_reconciliation_sha256,
        "rollback_config_sha256": activation.rollback_config_sha256,
        "controlled_restart_id": activation.receipt["controlled_restart_id"],
        "repo_commit": activation.receipt["repo_commit"],
    }


def _validate_activation_context_chain(
    events: Sequence[EvidenceEvent],
    activation: ActivationContext,
) -> None:
    if not events:
        raise StageBEvidenceError("activation context chain cannot be empty")
    if any(event.activation_epoch != activation.activation_epoch for event in events):
        raise StageBEvidenceError("event activation epoch disagrees with activation receipt")
    first = events[0]
    if first.event_type is not EventType.ACTIVATION_BOUND or not _strict_equal(
        first.payload,
        _expected_activation_bound_payload(activation),
    ):
        raise StageBEvidenceError("ACTIVATION_BOUND disagrees with activation bundle")


@dataclass(frozen=True, slots=True)
class ActivationCheck:
    state: ActivationState
    execution_authority: str = "NONE"


def _mode_text(mode: int) -> str:
    return f"{stat.S_IMODE(mode):04o}"


def _secure_lstat(path: Path, *, directory: bool) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise StageBEvidenceError("required private path is unavailable") from exc
    if stat.S_ISLNK(info.st_mode):
        raise StageBEvidenceError("private path cannot be a symlink")
    if directory:
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            raise StageBEvidenceError("private directory metadata is invalid")
    elif (
        not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
    ):
        raise StageBEvidenceError("private file metadata is invalid")
    if info.st_uid != os.getuid():
        raise StageBEvidenceError("private path owner is invalid")
    return info


def _assert_beneath(root: Path, path: Path) -> None:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise StageBEvidenceError("private path escapes fixed root") from exc
    try:
        if root.is_symlink():
            raise StageBEvidenceError("repository root cannot be a symlink")
        root_resolved = root.resolve(strict=True)
        path.resolve(strict=False).relative_to(root_resolved)
        current = root
        for component in relative.parts:
            current = current / component
            if current.exists() or current.is_symlink():
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise StageBEvidenceError("private path ancestor cannot be a symlink")
    except (OSError, ValueError) as exc:
        raise StageBEvidenceError("private path escapes fixed root") from exc


def _read_secure_file(path: Path, *, maximum: int = MAX_PUBLIC_PROJECTION_BYTES) -> bytes:
    _secure_lstat(path, directory=False)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StageBEvidenceError("private file cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size < 0
            or before.st_size > maximum
        ):
            raise StageBEvidenceError("private file metadata is invalid")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise StageBEvidenceError("private file was truncated during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise StageBEvidenceError("private file grew during read")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
            before.st_mode,
            before.st_uid,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
            after.st_mode,
            after.st_uid,
        ):
            raise StageBEvidenceError("private file changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _load_secure_json(
    path: Path, *, label: str, maximum: int = MAX_PUBLIC_PROJECTION_BYTES
) -> tuple[dict[str, object], bytes]:
    raw = _read_secure_file(path, maximum=maximum)
    return _decode_json(raw, label=label), raw


def _validate_runtime_inventory(private_root: Path) -> None:
    _secure_lstat(private_root, directory=True)
    expected_root = {"activation", "private", "store", "quarantine", "recovery"}
    try:
        root_names = {entry.name for entry in os.scandir(private_root)}
    except OSError as exc:
        raise StageBEvidenceError("private runtime inventory is unreadable") from exc
    if root_names != expected_root:
        raise StageBEvidenceError("private runtime inventory is invalid")
    for name in expected_root:
        _secure_lstat(private_root / name, directory=True)

    activation = private_root / "activation"
    if {entry.name for entry in os.scandir(activation)} != {
        "ACTIVATION_RECEIPT.json",
        "CONFIG.json",
        "INDEPENDENT_REVIEW.json",
        "FLAT_RECONCILIATION.json",
        "ROLLBACK_CONFIG.json",
    }:
        raise StageBEvidenceError("activation inventory is invalid")
    for entry in os.scandir(activation):
        _secure_lstat(Path(entry.path), directory=False)

    private = private_root / "private"
    if {entry.name for entry in os.scandir(private)} != {"install_alias.key"}:
        raise StageBEvidenceError("private material inventory is invalid")
    _secure_lstat(private / "install_alias.key", directory=False)

    store = private_root / "store"
    store_names = {entry.name for entry in os.scandir(store)}
    if not {"generations"}.issubset(store_names) or not store_names <= {"generations", "HEAD.json"}:
        raise StageBEvidenceError("store inventory is invalid")
    _secure_lstat(store / "generations", directory=True)
    if "HEAD.json" in store_names:
        _secure_lstat(store / "HEAD.json", directory=False)

    generations = private_root / "store/generations"
    for entry in os.scandir(generations):
        if not _GENERATION.fullmatch(entry.name):
            raise StageBEvidenceError("generation inventory is invalid")
        generation = Path(entry.path)
        _secure_lstat(generation, directory=True)
        if {item.name for item in os.scandir(generation)} != {
            "events.jsonl",
            "reducer_state.json",
            "public_projection.json",
            "manifest.json",
        }:
            raise StageBEvidenceError("committed generation inventory is invalid")
        for item in os.scandir(generation):
            _secure_lstat(Path(item.path), directory=False)

    quarantine = private_root / "quarantine"
    for entry in os.scandir(quarantine):
        if not _QUARANTINE_DIR.fullmatch(entry.name):
            raise StageBEvidenceError("quarantine inventory is invalid")
        _secure_lstat(Path(entry.path), directory=True)
    quarantine_inventory(private_root)

    recovery = private_root / "recovery"
    for entry in os.scandir(recovery):
        if not re.fullmatch(r"RECOVERY-[a-f0-9]{64}\.json", entry.name):
            raise StageBEvidenceError("recovery inventory is invalid")
        record_path = Path(entry.path)
        record, raw = _load_secure_json(record_path, label="recovery record")
        _validate_recovery_record(record)
        if entry.name != f"RECOVERY-{sha256_bytes(raw)}.json":
            raise StageBEvidenceError("recovery record content address is invalid")


def _preflight_mutation_inventory(repo_root: Path, private_root: Path) -> None:
    """Validate every mutation-owning path before interrupted material is moved."""

    _assert_beneath(repo_root, private_root)
    _secure_lstat(private_root, directory=True)
    expected_root = {"activation", "private", "store", "quarantine", "recovery"}
    if {entry.name for entry in os.scandir(private_root)} != expected_root:
        raise StageBEvidenceError("private mutation inventory is invalid")
    for name in expected_root:
        _secure_lstat(private_root / name, directory=True)

    activation = private_root / "activation"
    activation_names = {
        "ACTIVATION_RECEIPT.json",
        "CONFIG.json",
        "INDEPENDENT_REVIEW.json",
        "FLAT_RECONCILIATION.json",
        "ROLLBACK_CONFIG.json",
    }
    if {entry.name for entry in os.scandir(activation)} != activation_names:
        raise StageBEvidenceError("activation mutation inventory is invalid")
    for entry in os.scandir(activation):
        _secure_lstat(Path(entry.path), directory=False)
    private = private_root / "private"
    if {entry.name for entry in os.scandir(private)} != {"install_alias.key"}:
        raise StageBEvidenceError("private mutation inventory is invalid")
    _secure_lstat(private / "install_alias.key", directory=False)

    store = private_root / "store"
    store_names = {entry.name for entry in os.scandir(store)}
    if not {"generations"}.issubset(store_names) or not store_names <= {
        "generations",
        "HEAD.json",
        "HEAD.json.tmp",
    }:
        raise StageBEvidenceError("store mutation inventory is invalid")
    _secure_lstat(store / "generations", directory=True)
    for name in store_names - {"generations"}:
        _secure_lstat(store / name, directory=False)

    generations = store / "generations"
    committed_names = {
        "events.jsonl",
        "reducer_state.json",
        "public_projection.json",
        "manifest.json",
    }
    partial_names = {
        "events.jsonl",
        "reducer_state.json",
        "public_projection.json",
        ".manifest.json.tmp",
    }
    for entry in os.scandir(generations):
        if not _GENERATION.fullmatch(entry.name):
            raise StageBEvidenceError("generation mutation inventory is invalid")
        generation = Path(entry.path)
        _secure_lstat(generation, directory=True)
        names = {item.name for item in os.scandir(generation)}
        if "manifest.json" in names:
            if names != committed_names:
                raise StageBEvidenceError("committed generation inventory is invalid")
        elif not names <= partial_names:
            raise StageBEvidenceError("partial generation inventory is invalid")
        for item in os.scandir(generation):
            _secure_lstat(Path(item.path), directory=False)

    quarantine = private_root / "quarantine"
    for entry in os.scandir(quarantine):
        if not _QUARANTINE_DIR.fullmatch(entry.name):
            raise StageBEvidenceError("quarantine mutation inventory is invalid")
        _secure_lstat(Path(entry.path), directory=True)
    quarantine_inventory(private_root)

    recovery = private_root / "recovery"
    for entry in os.scandir(recovery):
        if not re.fullmatch(r"RECOVERY-[a-f0-9]{64}\.json", entry.name):
            raise StageBEvidenceError("recovery mutation inventory is invalid")
        path = Path(entry.path)
        record, raw = _load_secure_json(path, label="recovery record")
        _validate_recovery_record(record)
        if entry.name != f"RECOVERY-{sha256_bytes(raw)}.json":
            raise StageBEvidenceError("recovery record content address is invalid")


def _validate_config(value: Mapping[str, object], module_sha256: str) -> None:
    _require_exact_fields(
        value,
        {"schema", "implementation_module_sha256", "paths", "limits", "contracts"},
        "CONFIG",
    )
    if not _strict_equal(value, expected_config(module_sha256)):
        raise StageBEvidenceError("CONFIG does not match the fixed Stage B contract")


def _validate_bound_file_map(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != set(_BOUND_FILES):
        raise StageBEvidenceError(f"{label} file map is invalid")
    for digest in value.values():
        _require_regex(digest, _SHA256, f"{label} file digest")
    return cast(Mapping[str, object], value)


def _validate_independent_review(
    value: Mapping[str, object],
    *,
    repo_commit: str,
    config_sha256: str,
    file_sha256: Mapping[str, object],
) -> None:
    _require_exact_fields(
        value,
        {"schema", "decision", "reviewed_commit", "file_sha256", "config_sha256", "reviewed_at"},
        "independent review",
    )
    if (
        value["schema"] != "tios.demo_decision_evidence.independent_review.v1"
        or value["decision"] != "GO"
        or value["reviewed_commit"] != repo_commit
        or value["config_sha256"] != config_sha256
        or value["file_sha256"] != file_sha256
    ):
        raise StageBEvidenceError("independent review cross-binding is invalid")
    canonical_utc(cast(str, value["reviewed_at"]))


def _validate_flat_reconciliation(
    value: Mapping[str, object], *, repo_commit: str, config_sha256: str
) -> None:
    _require_exact_fields(
        value,
        {
            "schema",
            "repo_commit",
            "config_sha256",
            "prior_stage_b_head_sha256",
            "observed_at",
            "position_base_qty",
            "open_order_count",
            "unresolved_attempt_count",
            "protective_stop_state",
            "all_pages_complete",
            "source",
        },
        "flat reconciliation",
    )
    prior = value["prior_stage_b_head_sha256"]
    if prior is not None:
        _require_regex(prior, _SHA256, "prior Stage B head")
    if (
        value["schema"] != "tios.demo_decision_evidence.flat_reconciliation.v1"
        or value["repo_commit"] != repo_commit
        or value["config_sha256"] != config_sha256
        or value["position_base_qty"] != "0"
        or value["open_order_count"] != 0
        or value["unresolved_attempt_count"] != 0
        or value["protective_stop_state"] != "CLEAR"
        or value["all_pages_complete"] is not True
        or value["source"] != "REALTIME_HISTORY_EXECUTION"
    ):
        raise StageBEvidenceError("flat reconciliation is not activation-safe")
    _require_int(value["open_order_count"], "open order count", 0, 0)
    _require_int(value["unresolved_attempt_count"], "unresolved attempt count", 0, 0)
    canonical_utc(cast(str, value["observed_at"]))


def _validate_rollback(value: Mapping[str, object]) -> None:
    _require_exact_fields(
        value,
        {
            "schema",
            "rollback_commit",
            "prior_file_sha256",
            "prior_config",
            "make_start_target",
            "make_once_target",
            "recorded_at",
        },
        "rollback config",
    )
    expected_prior_files = {
        "scripts/demo_eth_lane.py",
        "scripts/demo_roundtrip.py",
        "src/tios/services/dashboard_api/demo_lane.py",
        "src/tios/services/dashboard_ui/dashboard.html",
    }
    prior_files = value["prior_file_sha256"]
    if not isinstance(prior_files, Mapping) or set(prior_files) != expected_prior_files:
        raise StageBEvidenceError("rollback prior file map is invalid")
    for digest in prior_files.values():
        _require_regex(digest, _SHA256, "rollback prior file digest")
    prior_config = value["prior_config"]
    if prior_config != {
        "schema": "tios.demo_decision_evidence.rollback_prior_config.v1",
        "stage_b": "ABSENT",
        "execution_authority": "NONE",
    }:
        raise StageBEvidenceError("rollback prior configuration is invalid")
    if (
        value["schema"] != "tios.demo_decision_evidence.rollback_config.v1"
        or value["make_start_target"] != "demo-lane"
        or value["make_once_target"] != "demo-lane-once"
    ):
        raise StageBEvidenceError("rollback configuration is invalid")
    _require_regex(value["rollback_commit"], _COMMIT, "rollback commit")
    canonical_utc(cast(str, value["recorded_at"]))


def _validate_receipt_shape(value: Mapping[str, object]) -> Mapping[str, object]:
    expected = {
        "schema",
        "state",
        "environment",
        "real_money",
        "execution_authority",
        "package_version",
        "repo_commit",
        "file_sha256",
        "config_path",
        "config_sha256",
        "independent_review_path",
        "independent_review_sha256",
        "flat_reconciliation_path",
        "flat_reconciliation_sha256",
        "rollback_config_path",
        "rollback_config_sha256",
        "private_root",
        "receipt_path",
        "alias_key_path",
        "alias_key_sha256",
        "rollback_commit",
        "controlled_restart_id",
        "activation_epoch",
        "approved_at",
    }
    _require_exact_fields(value, expected, "activation receipt")
    file_sha256 = _validate_bound_file_map(value["file_sha256"], label="activation")
    fixed = {
        "schema": "tios.demo_decision_evidence.activation_receipt.v1",
        "state": "ACTIVE",
        "environment": "VENUE_DEMO",
        "real_money": False,
        "execution_authority": "NONE",
        "package_version": "v8.146",
        "config_path": "artifacts/evidence/private_demo/stage_b_v2/activation/CONFIG.json",
        "independent_review_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/INDEPENDENT_REVIEW.json"
        ),
        "flat_reconciliation_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/FLAT_RECONCILIATION.json"
        ),
        "rollback_config_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/ROLLBACK_CONFIG.json"
        ),
        "private_root": "artifacts/evidence/private_demo/stage_b_v2",
        "receipt_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/ACTIVATION_RECEIPT.json"
        ),
        "alias_key_path": "artifacts/evidence/private_demo/stage_b_v2/private/install_alias.key",
    }
    for name, expected_value in fixed.items():
        if not _strict_equal(value[name], expected_value):
            raise StageBEvidenceError("activation receipt fixed boundary is invalid")
    for name in (
        "config_sha256",
        "independent_review_sha256",
        "flat_reconciliation_sha256",
        "rollback_config_sha256",
        "alias_key_sha256",
    ):
        _require_regex(value[name], _SHA256, name)
    _require_regex(value["repo_commit"], _COMMIT, "repo commit")
    _require_regex(value["rollback_commit"], _COMMIT, "rollback commit")
    _require_regex(value["controlled_restart_id"], _RESTART_ID, "controlled restart id")
    _require_regex(value["activation_epoch"], _ACTIVATION_EPOCH, "activation epoch")
    canonical_utc(cast(str, value["approved_at"]))
    return file_sha256


def _validate_repo_bindings(repo_root: Path, file_sha256: Mapping[str, object]) -> None:
    for relative in _BOUND_FILES:
        path = repo_root / relative
        _assert_beneath(repo_root, path)
        try:
            if path.is_symlink() or not path.is_file():
                raise StageBEvidenceError("activation-bound source file is unavailable")
            digest = sha256_bytes(path.read_bytes())
        except OSError as exc:
            raise StageBEvidenceError("activation-bound source file is unavailable") from exc
        if digest != file_sha256[relative]:
            raise StageBEvidenceError("activation-bound source digest mismatch")


def _run_git(repo_root: Path, arguments: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StageBEvidenceError("activation Git state is unavailable") from exc
    if completed.returncode != 0:
        raise StageBEvidenceError("activation Git state is invalid")
    return completed.stdout


def _validate_git_binding(repo_root: Path, expected_commit: object) -> None:
    commit = _run_git(repo_root, ["rev-parse", "--verify", "HEAD"]).strip()
    _require_regex(commit, _COMMIT, "actual Git HEAD")
    if commit != expected_commit:
        raise StageBEvidenceError("activation receipt does not bind actual Git HEAD")
    tracked = _run_git(repo_root, ["ls-files", "--", *_BOUND_FILES]).splitlines()
    if set(tracked) != set(_BOUND_FILES) or len(tracked) != len(_BOUND_FILES):
        raise StageBEvidenceError("activation-bound file inventory is not fully tracked")
    dirty = _run_git(
        repo_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *_BOUND_FILES],
    )
    if dirty:
        raise StageBEvidenceError("activation-bound Git files are dirty")


def _parse_approved_at(value: str) -> datetime:
    canonical_utc(value)
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def load_activation(
    repo_root: Path | str,
    *,
    now: datetime | None = None,
) -> ActivationContext:
    """Validate the fixed Stage B activation bundle or fail closed."""

    root = Path(repo_root).absolute()
    private_root = root / PRIVATE_ROOT_REL
    _assert_beneath(root, private_root)
    if not private_root.exists():
        raise StageBNotActivatedError("Stage B is not activated")
    _validate_runtime_inventory(private_root)

    receipt, receipt_raw = _load_secure_json(
        private_root / ACTIVATION_RECEIPT_REL, label="activation receipt"
    )
    receipt_sha256 = sha256_bytes(receipt_raw)
    file_sha256 = _validate_receipt_shape(receipt)

    module_path = root / "src/tios/evidence/demo_decision_evidence_v2.py"
    try:
        module_sha256 = sha256_bytes(module_path.read_bytes())
    except OSError as exc:
        raise StageBEvidenceError("implementation module is unavailable") from exc
    config, config_raw = _load_secure_json(private_root / "activation/CONFIG.json", label="CONFIG")
    config_sha256 = sha256_bytes(config_raw)
    _validate_config(config, module_sha256)
    if receipt["config_sha256"] != config_sha256:
        raise StageBEvidenceError("CONFIG digest binding is invalid")

    review, review_raw = _load_secure_json(
        private_root / "activation/INDEPENDENT_REVIEW.json", label="independent review"
    )
    review_sha256 = sha256_bytes(review_raw)
    if receipt["independent_review_sha256"] != review_sha256:
        raise StageBEvidenceError("independent review digest binding is invalid")
    _validate_independent_review(
        review,
        repo_commit=cast(str, receipt["repo_commit"]),
        config_sha256=config_sha256,
        file_sha256=file_sha256,
    )

    flat_reconciliation, flat_raw = _load_secure_json(
        private_root / "activation/FLAT_RECONCILIATION.json", label="flat reconciliation"
    )
    flat_sha256 = sha256_bytes(flat_raw)
    if receipt["flat_reconciliation_sha256"] != flat_sha256:
        raise StageBEvidenceError("flat reconciliation digest binding is invalid")
    _validate_flat_reconciliation(
        flat_reconciliation,
        repo_commit=cast(str, receipt["repo_commit"]),
        config_sha256=config_sha256,
    )

    rollback, rollback_raw = _load_secure_json(
        private_root / "activation/ROLLBACK_CONFIG.json", label="rollback config"
    )
    rollback_sha256 = sha256_bytes(rollback_raw)
    if (
        receipt["rollback_config_sha256"] != rollback_sha256
        or receipt["rollback_commit"] != rollback["rollback_commit"]
    ):
        raise StageBEvidenceError("rollback digest binding is invalid")
    _validate_rollback(rollback)

    alias_key = _read_secure_file(private_root / ALIAS_KEY_REL, maximum=32)
    if len(alias_key) != 32 or receipt["alias_key_sha256"] != sha256_bytes(alias_key):
        raise StageBEvidenceError("private alias material binding is invalid")
    del alias_key

    _validate_repo_bindings(root, file_sha256)
    _validate_git_binding(root, receipt["repo_commit"])
    context = ActivationContext(
        repo_root=root,
        private_root=private_root,
        receipt=receipt,
        receipt_sha256=receipt_sha256,
        config=config,
        config_sha256=config_sha256,
        independent_review_sha256=review_sha256,
        flat_reconciliation_sha256=flat_sha256,
        rollback_config_sha256=rollback_sha256,
    )
    checked_at = datetime.now(UTC) if now is None else now.astimezone(UTC)
    approved_at = _parse_approved_at(cast(str, receipt["approved_at"]))
    with os.scandir(private_root / "store/generations") as generation_entries:
        has_generations = next(generation_entries, None) is not None
    if has_generations:
        snapshot = load_snapshot(context)
        if not snapshot.generations:
            raise StageBEvidenceError("activation receipt consumption is incomplete")
    age = checked_at - approved_at
    if not has_generations and (age < timedelta(0) or age > RECOVERY_APPROVAL_MAX_AGE):
        raise StageBEvidenceError("unused activation receipt is stale")
    return context


def activation_check(repo_root: Path | str, *, now: datetime | None = None) -> ActivationCheck:
    """Return only the fail-closed public activation state."""

    private_root = Path(repo_root).absolute() / PRIVATE_ROOT_REL
    if not private_root.exists():
        return ActivationCheck(ActivationState.NOT_ACTIVATED)
    try:
        load_activation(repo_root, now=now)
    except StageBEvidenceError:
        return ActivationCheck(ActivationState.UNAVAILABLE)
    return ActivationCheck(ActivationState.ACTIVE)


def _derive_private_alias_vector(key: bytes, tag: str, value: bytes) -> str:
    """Pure Appendix-D test vector; the owning adapter performs real aliasing."""

    if len(key) != 32 or tag not in {"ord", "exe", "fee", "strategy", "cost", "risk"}:
        raise StageBEvidenceError("private alias input is invalid")
    if not isinstance(value, bytes):
        raise StageBEvidenceError("private alias value is invalid")
    digest = hmac.new(
        key,
        b"tios.demo_decision_evidence.v2\0" + tag.encode("ascii") + b"\0" + value,
        hashlib.sha256,
    ).hexdigest()
    return f"{tag}_{digest}"


def derive_risk_reduction_client_key(
    *,
    activation_epoch: str,
    subject_intent_event_id: str,
    action_kind: str,
    sequence: int,
    payload_sha256: str,
) -> str:
    """Derive the deterministic 36-character key for one lane-owned risk reduction."""

    _require_regex(activation_epoch, _ACTIVATION_EPOCH, "activation epoch")
    _require_regex(subject_intent_event_id, _EVENT_ALIAS, "subject intent event id")
    if action_kind not in {"EXIT_CREATE", "STOP_CREATE", "STOP_REPLACE_CREATE"}:
        raise StageBEvidenceError("risk-reduction action kind is invalid")
    _require_int(sequence, "risk reduction sequence", 1, MAX_SEQUENCE)
    _require_regex(payload_sha256, _SHA256, "risk reduction payload digest")
    preimage = (
        b"tios.demo_decision_evidence.v2\0risk-reduction-create\0"
        + activation_epoch.encode("ascii")
        + b"\0"
        + subject_intent_event_id.encode("ascii")
        + b"\0"
        + action_kind.encode("ascii")
        + b"\0"
        + str(sequence).encode("ascii")
        + b"\0"
        + payload_sha256.encode("ascii")
    )
    return "tios2_r_" + sha256_bytes(preimage)[:28]


@dataclass(frozen=True, slots=True)
class Generation:
    path: Path
    manifest: Mapping[str, object]
    manifest_sha256: str
    events: tuple[EvidenceEvent, ...]
    reducer_state: Mapping[str, object]
    public_projection: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    activation: ActivationContext
    generations: tuple[Generation, ...]
    events: tuple[EvidenceEvent, ...]
    reducer_state: Mapping[str, object] | None
    public_projection: Mapping[str, object] | None
    head_sha256: str | None


_MANIFEST_FIELDS: Final = {
    "schema",
    "activation_epoch",
    "activation_receipt_sha256",
    "controlled_restart_id",
    "repo_commit",
    "config_sha256",
    "previous_manifest_sha256",
    "first_sequence",
    "last_sequence",
    "event_count",
    "events_sha256",
    "events_bytes",
    "reducer_state_sha256",
    "reducer_state_bytes",
    "public_projection_sha256",
    "public_projection_bytes",
    "committed_at",
}


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file(descriptor: int, path: Path) -> None:
    del path
    os.fsync(descriptor)


def _require_size(value: int, maximum: int, label: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise StageBEvidenceError(f"{label} size is invalid")
    return value


def _write_exclusive(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise StageBEvidenceError("private evidence write failed")
            view = view[written:]
        _fsync_file(descriptor, path)
    except BaseException:
        raise
    finally:
        os.close(descriptor)


def _validate_manifest(
    value: Mapping[str, object],
    *,
    digest: str,
    activation: ActivationContext,
) -> None:
    _require_exact_fields(value, _MANIFEST_FIELDS, "generation manifest")
    if (
        value["schema"] != "tios.demo_decision_evidence.generation_manifest.v1"
        or value["activation_epoch"] != activation.activation_epoch
        or value["activation_receipt_sha256"] != activation.receipt_sha256
        or value["controlled_restart_id"] != activation.receipt["controlled_restart_id"]
        or value["repo_commit"] != activation.receipt["repo_commit"]
        or value["config_sha256"] != activation.config_sha256
    ):
        raise StageBEvidenceError("generation manifest activation binding is invalid")
    previous = value["previous_manifest_sha256"]
    if previous is not None:
        _require_regex(previous, _SHA256, "previous manifest digest")
    event_count = _require_int(value["event_count"], "event count", 1, MAX_EVENTS_PER_GENERATION)
    first_sequence = _require_int(value["first_sequence"], "first sequence", 1, MAX_SEQUENCE)
    last_sequence = _require_int(value["last_sequence"], "last sequence", 1, MAX_SEQUENCE)
    if last_sequence - first_sequence + 1 != event_count:
        raise StageBEvidenceError("generation sequence span is invalid")
    _require_size(cast(int, value["events_bytes"]), MAX_EVENTS_BYTES, "events")
    _require_size(cast(int, value["reducer_state_bytes"]), MAX_REDUCER_BYTES, "reducer")
    _require_size(
        cast(int, value["public_projection_bytes"]),
        MAX_PUBLIC_PROJECTION_BYTES,
        "public projection",
    )
    for name in ("events_sha256", "reducer_state_sha256", "public_projection_sha256"):
        _require_regex(value[name], _SHA256, name)
    canonical_utc(cast(str, value["committed_at"]))
    if not _SHA256.fullmatch(digest):
        raise StageBEvidenceError("generation manifest digest is invalid")


def _read_events_bytes(raw: bytes) -> tuple[EvidenceEvent, ...]:
    if not raw or len(raw) > MAX_EVENTS_BYTES:
        raise StageBEvidenceError("generation events size is invalid")
    lines = raw.splitlines(keepends=True)
    if len(lines) > MAX_EVENTS_PER_GENERATION or b"".join(lines) != raw:
        raise StageBEvidenceError("generation event framing is invalid")
    return tuple(parse_event_frame(line) for line in lines)


def _load_generation(path: Path, activation: ActivationContext) -> Generation:
    _secure_lstat(path, directory=True)
    if not _GENERATION.fullmatch(path.name):
        raise StageBEvidenceError("generation directory identity is invalid")
    names = {entry.name for entry in os.scandir(path)}
    if names != {"events.jsonl", "reducer_state.json", "public_projection.json", "manifest.json"}:
        raise StageBEvidenceError("generation inventory is invalid")
    manifest, manifest_raw = _load_secure_json(path / "manifest.json", label="generation manifest")
    manifest_sha256 = sha256_bytes(manifest_raw)
    if path.name != f"G-{manifest_sha256}":
        raise StageBEvidenceError("generation directory is not content-addressed")
    _validate_manifest(manifest, digest=manifest_sha256, activation=activation)

    events_raw = _read_secure_file(path / "events.jsonl", maximum=MAX_EVENTS_BYTES)
    reducer, reducer_raw = _load_secure_json(
        path / "reducer_state.json", label="reducer state", maximum=MAX_REDUCER_BYTES
    )
    projection, projection_raw = _load_secure_json(
        path / "public_projection.json",
        label="public projection",
        maximum=MAX_PUBLIC_PROJECTION_BYTES,
    )
    bindings = (
        ("events_sha256", "events_bytes", events_raw),
        ("reducer_state_sha256", "reducer_state_bytes", reducer_raw),
        ("public_projection_sha256", "public_projection_bytes", projection_raw),
    )
    for sha_name, bytes_name, raw in bindings:
        if manifest[sha_name] != sha256_bytes(raw) or manifest[bytes_name] != len(raw):
            raise StageBEvidenceError("generation data binding is invalid")
    events = _read_events_bytes(events_raw)
    if (
        len(events) != manifest["event_count"]
        or events[0].sequence != manifest["first_sequence"]
        or events[-1].sequence != manifest["last_sequence"]
    ):
        raise StageBEvidenceError("generation event manifest counters are invalid")
    _validate_generation_batch(events)
    return Generation(
        path=path,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        events=events,
        reducer_state=reducer,
        public_projection=projection,
    )


def _order_generations(generations: Sequence[Generation]) -> tuple[Generation, ...]:
    if not generations:
        return ()
    if len(generations) > MAX_GENERATIONS:
        raise StageBEvidenceError("generation count exceeds fixed replay bound")
    by_digest = {generation.manifest_sha256: generation for generation in generations}
    if len(by_digest) != len(generations):
        raise StageBEvidenceError("duplicate generation manifest digest")
    referenced: set[str] = set()
    roots = 0
    for generation in generations:
        previous = generation.manifest["previous_manifest_sha256"]
        if previous is None:
            roots += 1
        else:
            if previous not in by_digest or previous in referenced:
                raise StageBEvidenceError("generation manifest chain is branched or incomplete")
            referenced.add(previous)
    if roots != 1:
        raise StageBEvidenceError("generation chain has no unique genesis")
    heads = [
        generation for generation in generations if generation.manifest_sha256 not in referenced
    ]
    if len(heads) != 1:
        raise StageBEvidenceError("generation chain has no unique head")
    reversed_chain: list[Generation] = []
    cursor: Generation | None = heads[0]
    seen: set[str] = set()
    while cursor is not None:
        if cursor.manifest_sha256 in seen:
            raise StageBEvidenceError("generation chain contains a cycle")
        seen.add(cursor.manifest_sha256)
        reversed_chain.append(cursor)
        previous = cursor.manifest["previous_manifest_sha256"]
        cursor = None if previous is None else by_digest[cast(str, previous)]
    ordered = tuple(reversed(reversed_chain))
    if len(ordered) != len(generations):
        raise StageBEvidenceError("generation chain contains unreachable material")
    return ordered


def _validate_head(private_root: Path, expected: Generation | None) -> None:
    """Validate HEAD when possible; corruption never commits or invalidates a generation."""

    path = private_root / "store/HEAD.json"
    if not path.exists():
        return
    try:
        value, _ = _load_secure_json(path, label="HEAD")
        _require_exact_fields(
            value,
            {"schema", "activation_epoch", "manifest_sha256", "generation_path", "last_sequence"},
            "HEAD",
        )
        if expected is None:
            return
        expected_value = {
            "schema": "tios.demo_decision_evidence.head.v1",
            "activation_epoch": expected.manifest["activation_epoch"],
            "manifest_sha256": expected.manifest_sha256,
            "generation_path": f"store/generations/G-{expected.manifest_sha256}",
            "last_sequence": expected.manifest["last_sequence"],
        }
        if value != expected_value:
            return
    except StageBEvidenceError:
        return


def load_snapshot(activation: ActivationContext) -> EvidenceSnapshot:
    """Recover the unique committed chain from manifests, ignoring HEAD authority."""

    generations_root = activation.private_root / "store/generations"
    loaded = tuple(
        _load_generation(Path(entry.path), activation) for entry in os.scandir(generations_root)
    )
    ordered = _order_generations(loaded)
    # ponytail: bounded pre-activation debt. Full-history replay is O(n^2) because each
    # generation re-reduces the whole accumulated chain, and the MAX_GENERATIONS /
    # MAX_TOTAL_EVENTS lifetime caps can be exhausted. Upgrade path = incremental
    # reducer / snapshotting so replay is O(n); deferred until activation.
    all_events: list[EvidenceEvent] = []
    prior_last = 0
    prior_event: EvidenceEvent | None = None
    prior_reducer_state: dict[str, object] | None = None
    prior_manifest_sha256: str | None = None
    for generation in ordered:
        if generation.events[0].sequence != prior_last + 1:
            raise StageBEvidenceError("generation sequence chain is incomplete")
        if prior_event is not None and (
            generation.events[0].previous_event_sha256 != prior_event.frame_sha256
            or generation.events[0].activation_epoch != prior_event.activation_epoch
        ):
            raise StageBEvidenceError("generation event parent chain is incomplete")
        if len(all_events) + len(generation.events) > MAX_TOTAL_EVENTS:
            raise StageBEvidenceError("total event count exceeds fixed replay bound")
        _validate_recovery_events(
            new_events=generation.events,
            prior_events=all_events,
            prior_reducer_state=prior_reducer_state,
            prior_head_sha256=prior_manifest_sha256,
            activation=activation,
        )
        all_events.extend(generation.events)
        reduced = reduce_events(all_events)
        if generation.reducer_state != reduced.reducer_state:
            raise StageBEvidenceError("committed reducer state does not replay")
        if generation.public_projection != reduced.public_projection:
            raise StageBEvidenceError("committed public projection does not replay")
        prior_last = generation.events[-1].sequence
        prior_event = generation.events[-1]
        prior_reducer_state = reduced.reducer_state
        prior_manifest_sha256 = generation.manifest_sha256
    if all_events:
        # Historical replay cross-binds receipt <-> manifest <-> reducer <-> event epochs:
        # the manifest epoch is bound in _validate_manifest and the reducer epoch through the
        # replay equality check above, while this binds every event's envelope activation_epoch
        # to the receipt epoch AND the genesis ACTIVATION_BOUND payload to the activation bundle.
        _validate_activation_context_chain(all_events, activation)
    head = ordered[-1] if ordered else None
    _validate_head(activation.private_root, head)
    return EvidenceSnapshot(
        activation=activation,
        generations=ordered,
        events=tuple(all_events),
        reducer_state=None if head is None else head.reducer_state,
        public_projection=None if head is None else head.public_projection,
        head_sha256=None if head is None else head.manifest_sha256,
    )


def _new_quarantine_dir(private_root: Path) -> Path:
    quarantine = private_root / "quarantine"
    for _ in range(32):
        candidate = quarantine / f"U-{uuid.uuid4()}"
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        os.chmod(candidate, 0o700)
        _fsync_directory(quarantine)
        return candidate
    raise StageBEvidenceError("cannot allocate quarantine identity")


def _demote_interrupted_material(private_root: Path) -> None:
    """Demote only allowlisted uncommitted material while the lane lock is held."""

    generations = private_root / "store/generations"
    for entry in tuple(os.scandir(generations)):
        if not _GENERATION.fullmatch(entry.name):
            raise StageBEvidenceError("unexpected generation entry")
        generation = Path(entry.path)
        _secure_lstat(generation, directory=True)
        names = {item.name for item in os.scandir(generation)}
        if "manifest.json" in names:
            continue
        if not names <= {
            "events.jsonl",
            "reducer_state.json",
            "public_projection.json",
            ".manifest.json.tmp",
        }:
            raise StageBEvidenceError("interrupted generation inventory is invalid")
        for item in os.scandir(generation):
            _secure_lstat(Path(item.path), directory=False)
        target = _new_quarantine_dir(private_root)
        os.rmdir(target)
        os.replace(generation, target)
        _fsync_directory(generations)
        _fsync_directory(private_root / "quarantine")
    store = private_root / "store"
    head_temp = store / "HEAD.json.tmp"
    if head_temp.exists():
        _secure_lstat(head_temp, directory=False)
        target = _new_quarantine_dir(private_root)
        os.replace(head_temp, target / "HEAD.json.tmp")
        _fsync_directory(target)
        _fsync_directory(store)
        _fsync_directory(private_root / "quarantine")


def _write_head(private_root: Path, generation: Generation) -> None:
    store = private_root / "store"
    temporary = store / "HEAD.json.tmp"
    value = {
        "schema": "tios.demo_decision_evidence.head.v1",
        "activation_epoch": generation.manifest["activation_epoch"],
        "manifest_sha256": generation.manifest_sha256,
        "generation_path": f"store/generations/G-{generation.manifest_sha256}",
        "last_sequence": generation.manifest["last_sequence"],
    }
    _write_exclusive(temporary, canonical_json_bytes(value))
    os.replace(temporary, store / "HEAD.json")
    _fsync_directory(store)


def _verify_exact_generation(
    path: Path,
    *,
    activation: ActivationContext,
    expected_files: Mapping[str, bytes],
) -> Generation:
    generation = _load_generation(path, activation)
    for name, expected in expected_files.items():
        if _read_secure_file(path / name, maximum=max(len(expected), 1)) != expected:
            raise StageBEvidenceError("content-addressed generation byte conflict")
    return generation


def _commit_generation(
    *,
    activation: ActivationContext,
    events: Sequence[EvidenceEvent],
    reduced: ReducedEvidence,
    previous_manifest_sha256: str | None,
    committed_at: datetime | str,
) -> Generation:
    events_raw = b"".join(event.frame() for event in events)
    reducer_raw = canonical_json_bytes(reduced.reducer_state)
    projection_raw = canonical_json_bytes(reduced.public_projection)
    _require_size(len(events_raw), MAX_EVENTS_BYTES, "events")
    _require_size(len(reducer_raw), MAX_REDUCER_BYTES, "reducer")
    _require_size(len(projection_raw), MAX_PUBLIC_PROJECTION_BYTES, "public projection")
    receipt = activation.receipt
    manifest: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.generation_manifest.v1",
        "activation_epoch": activation.activation_epoch,
        "activation_receipt_sha256": activation.receipt_sha256,
        "controlled_restart_id": receipt["controlled_restart_id"],
        "repo_commit": receipt["repo_commit"],
        "config_sha256": activation.config_sha256,
        "previous_manifest_sha256": previous_manifest_sha256,
        "first_sequence": events[0].sequence,
        "last_sequence": events[-1].sequence,
        "event_count": len(events),
        "events_sha256": sha256_bytes(events_raw),
        "events_bytes": len(events_raw),
        "reducer_state_sha256": sha256_bytes(reducer_raw),
        "reducer_state_bytes": len(reducer_raw),
        "public_projection_sha256": sha256_bytes(projection_raw),
        "public_projection_bytes": len(projection_raw),
        "committed_at": canonical_utc(committed_at),
    }
    manifest_raw = canonical_json_bytes(manifest)
    manifest_sha256 = sha256_bytes(manifest_raw)
    generation_path = activation.private_root / "store/generations" / f"G-{manifest_sha256}"
    expected_files = {
        "events.jsonl": events_raw,
        "reducer_state.json": reducer_raw,
        "public_projection.json": projection_raw,
        "manifest.json": manifest_raw,
    }
    if generation_path.exists():
        return _verify_exact_generation(
            generation_path, activation=activation, expected_files=expected_files
        )
    manifest_renamed = False
    try:
        os.mkdir(generation_path, 0o700)
        os.chmod(generation_path, 0o700)
        _fsync_directory(generation_path.parent)
        _write_exclusive(generation_path / "events.jsonl", events_raw)
        _write_exclusive(generation_path / "reducer_state.json", reducer_raw)
        _write_exclusive(generation_path / "public_projection.json", projection_raw)
        temporary_manifest = generation_path / ".manifest.json.tmp"
        _write_exclusive(temporary_manifest, manifest_raw)
        os.replace(temporary_manifest, generation_path / "manifest.json")
        manifest_renamed = True
        _fsync_directory(generation_path)
    except BaseException as exc:
        if manifest_renamed:
            raise StageBCommittedDurabilityError(manifest_sha256) from exc
        raise
    return _verify_exact_generation(
        generation_path, activation=activation, expected_files=expected_files
    )


_LANE_LOCK_CAPABILITY_SECRET: Final = object()


class LaneLockCapability:
    """Opaque proof that the caller owns this repository's real lane flock."""

    __slots__ = ("_active", "_descriptor", "_repo_root", "_stat")

    def __init__(
        self,
        secret: object,
        repo_root: Path,
        descriptor: int,
        lock_stat: os.stat_result,
    ) -> None:
        if secret is not _LANE_LOCK_CAPABILITY_SECRET:
            raise StageBEvidenceError("lane lock capability cannot be constructed by callers")
        self._repo_root = repo_root
        self._descriptor = descriptor
        self._stat = lock_stat
        self._active = True

    def _validate_for(self, repo_root: Path) -> None:
        if not self._active or self._repo_root != repo_root:
            raise StageBEvidenceError("exclusive lane lock capability is invalid")
        try:
            current = os.fstat(self._descriptor)
            path_stat = (repo_root / "artifacts/trading_domain/demo_lane/lane.lock").lstat()
        except OSError as exc:
            raise StageBEvidenceError("exclusive lane lock capability is unavailable") from exc
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or current.st_uid != os.getuid()
            or (current.st_dev, current.st_ino) != (self._stat.st_dev, self._stat.st_ino)
            or (path_stat.st_dev, path_stat.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise StageBEvidenceError("exclusive lane lock capability changed")

    def _invalidate(self) -> None:
        self._active = False


@contextmanager
def exclusive_lane_lock_capability(
    repo_root: Path | str,
) -> Iterator[LaneLockCapability]:
    """Acquire the fixed lane lock and yield a short-lived, non-boolean capability."""

    root = Path(repo_root).absolute()
    lock_path = root / "artifacts/trading_domain/demo_lane/lane.lock"
    _assert_beneath(root, lock_path)
    descriptor: int | None = None
    try:
        info = lock_path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.getuid()
        ):
            raise StageBEvidenceError("lane lock path is unsafe")
        flags = os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags)
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise StageBEvidenceError("lane lock path changed during acquisition")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except StageBEvidenceError:
        if descriptor is not None:
            os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise StageBEvidenceError("exclusive lane lock is unavailable") from exc
    if descriptor is None:
        raise StageBEvidenceError("exclusive lane lock is unavailable")
    capability = LaneLockCapability(
        _LANE_LOCK_CAPABILITY_SECRET,
        root,
        descriptor,
        opened,
    )
    try:
        yield capability
    finally:
        capability._invalidate()
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


class StageBEvidenceSink:
    """Fixed, non-pluggable Stage B sink for one repository root."""

    def __init__(self, repo_root: Path | str) -> None:
        self._repo_root = Path(repo_root).absolute()

    @property
    def private_root(self) -> Path:
        return self._repo_root / PRIVATE_ROOT_REL

    def activation_check(self, *, now: datetime | None = None) -> ActivationCheck:
        return activation_check(self._repo_root, now=now)

    def load(self, *, now: datetime | None = None) -> EvidenceSnapshot:
        activation = load_activation(self._repo_root, now=now)
        return load_snapshot(activation)

    def append(
        self,
        events: Sequence[EvidenceEvent],
        *,
        capability: LaneLockCapability,
        now: datetime | None = None,
    ) -> EvidenceSnapshot:
        """Commit new events. The owning lane must hold its exclusive lock."""

        if not isinstance(capability, LaneLockCapability):
            raise StageBEvidenceError("exclusive lane lock capability is required")
        capability._validate_for(self._repo_root)
        if not events:
            return self.load(now=now)
        if len(events) > MAX_EVENTS_PER_GENERATION:
            raise StageBEvidenceError("generation event count exceeds fixed bound")
        private_root = self.private_root
        if not private_root.exists():
            raise StageBNotActivatedError("Stage B is not activated")
        _preflight_mutation_inventory(self._repo_root, private_root)
        _demote_interrupted_material(private_root)
        activation = load_activation(self._repo_root, now=now)
        snapshot = load_snapshot(activation)

        existing_by_sequence = {event.sequence: event for event in snapshot.events}
        new_events: list[EvidenceEvent] = []
        for event in events:
            existing = existing_by_sequence.get(event.sequence)
            if existing is not None:
                if existing.frame() != event.frame():
                    raise StageBEvidenceError("conflicting replay at committed sequence")
                continue
            new_events.append(event)
        if not new_events:
            return snapshot
        expected_sequence = len(snapshot.events) + 1
        if new_events[0].sequence != expected_sequence:
            raise StageBEvidenceError("append begins after a sequence gap")
        if len(snapshot.events) + len(new_events) > MAX_TOTAL_EVENTS:
            raise StageBEvidenceError("total event count exceeds fixed replay bound")
        combined = tuple(snapshot.events) + tuple(new_events)
        # Bind every event's activation_epoch to the receipt epoch and validate the genesis
        # ACTIVATION_BOUND payload against the activation bundle BEFORE committing, so a wrong
        # epoch or wrong binding fails here and leaves the store with zero new generations.
        _validate_activation_context_chain(combined, activation)
        _validate_recovery_events(
            new_events=new_events,
            prior_events=snapshot.events,
            prior_reducer_state=snapshot.reducer_state,
            prior_head_sha256=snapshot.head_sha256,
            activation=activation,
        )
        reduced = reduce_events(combined)
        generation = _commit_generation(
            activation=activation,
            events=new_events,
            reduced=reduced,
            previous_manifest_sha256=snapshot.head_sha256,
            committed_at=datetime.now(UTC) if now is None else now,
        )
        try:
            _write_head(private_root, generation)
        except BaseException as exc:
            raise StageBCommittedHeadError(generation.manifest_sha256) from exc
        return load_snapshot(activation)


def public_stage_b_projection(
    repo_root: Path | str, *, now: datetime | None = None
) -> dict[str, object]:
    """Read only the fixed aggregate projection for the dashboard owner."""

    check = activation_check(repo_root, now=now)
    if check.state is ActivationState.NOT_ACTIVATED:
        return {
            "status": "NOT_ACTIVATED",
            "cohort_size": COHORT_SIZE,
            "series": [],
        }
    if check.state is ActivationState.UNAVAILABLE:
        return {
            "status": "UNAVAILABLE",
            "cohort_size": COHORT_SIZE,
            "series": [],
        }
    try:
        snapshot = StageBEvidenceSink(repo_root).load(now=now)
    except StageBEvidenceError:
        return {
            "status": "UNAVAILABLE",
            "cohort_size": COHORT_SIZE,
            "series": [],
        }
    if snapshot.public_projection is None:
        return {
            "status": "READY",
            "cohort_size": COHORT_SIZE,
            "series": [],
        }
    projection = snapshot.public_projection
    _require_exact_fields(
        projection, {"schema", "status", "cohort_size", "series"}, "public projection"
    )
    if (
        projection["schema"] != "tios.demo_decision_evidence.public_projection.v1"
        or projection["status"] not in {"READY", "ENTRY_BLOCK", "UNAVAILABLE"}
        or projection["cohort_size"] != COHORT_SIZE
        or not isinstance(projection["series"], list)
    ):
        return {
            "status": "UNAVAILABLE",
            "cohort_size": COHORT_SIZE,
            "series": [],
        }
    return {
        "status": projection["status"],
        "cohort_size": COHORT_SIZE,
        "series": projection["series"],
    }


def _validate_quarantine_relative(path_text: str) -> None:
    try:
        path_text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise StageBEvidenceError("quarantine path must be ASCII") from exc
    if (
        not re.fullmatch(r"[A-Za-z0-9._/-]+", path_text)
        or path_text.startswith("/")
        or path_text.endswith("/")
    ):
        raise StageBEvidenceError("quarantine path is invalid")
    parts = PurePosixPath(path_text).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise StageBEvidenceError("quarantine path is invalid")


def quarantine_inventory(private_root: Path) -> tuple[dict[str, object], str]:
    """Build the canonical, content-binding inventory used by recovery approval."""

    quarantine = private_root / "quarantine"
    _secure_lstat(quarantine, directory=True)
    rows: list[dict[str, object]] = []
    for root_text, directories, files in os.walk(quarantine, topdown=True, followlinks=False):
        root = Path(root_text)
        directories.sort(key=lambda item: item.encode("utf-8"))
        files.sort(key=lambda item: item.encode("utf-8"))
        for name in tuple(directories):
            path = root / name
            _secure_lstat(path, directory=True)
            relative = path.relative_to(quarantine).as_posix()
            _validate_quarantine_relative(relative)
            if path.parent == quarantine and not _QUARANTINE_DIR.fullmatch(name):
                raise StageBEvidenceError("quarantine directory identity is invalid")
            if path.parent != quarantine:
                raise StageBEvidenceError("nested quarantine directories are forbidden")
            rows.append(
                {
                    "path": relative,
                    "type": "DIR",
                    "mode": "0700",
                    "bytes": None,
                    "sha256": None,
                }
            )
        for name in files:
            path = root / name
            relative = path.relative_to(quarantine).as_posix()
            _validate_quarantine_relative(relative)
            if path.parent.parent != quarantine:
                raise StageBEvidenceError("nested quarantine files are forbidden")
            allowed = {
                "events.jsonl",
                "reducer_state.json",
                "public_projection.json",
                ".manifest.json.tmp",
                "HEAD.json.tmp",
            }
            if name not in allowed:
                raise StageBEvidenceError("quarantine file identity is invalid")
            if name == "HEAD.json.tmp" and len(files) != 1:
                raise StageBEvidenceError("orphan HEAD quarantine must be isolated")
            raw = _read_secure_file(path, maximum=MAX_EVENTS_BYTES)
            rows.append(
                {
                    "path": relative,
                    "type": "FILE",
                    "mode": "0600",
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                }
            )
    rows.sort(key=lambda row: cast(str, row["path"]).encode("utf-8"))
    inventory: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.quarantine_inventory.v1",
        "entries": rows,
    }
    return inventory, canonical_sha256(inventory)


_RECOVERY_APPROVAL_FIELDS: Final = {
    "schema",
    "decision",
    "activation_epoch",
    "expected_head_sha256",
    "expected_incident_sha256",
    "expected_reconciliation_event_id",
    "expected_quarantine_inventory_sha256",
    "reason_code",
    "approved_at",
}


def _validate_recovery_approval(
    value: Mapping[str, object],
    *,
    activation_epoch: str,
    expected_head: str,
    expected_incident: str,
    expected_reconciliation: str,
    expected_quarantine: str,
    now: datetime,
) -> None:
    _require_exact_fields(value, _RECOVERY_APPROVAL_FIELDS, "recovery approval")
    if (
        value["schema"] != "tios.demo_decision_evidence.recovery_approval.v1"
        or value["decision"] != "APPROVE_RECOVERY_RECORD_ONLY"
        or value["activation_epoch"] != activation_epoch
        or value["expected_head_sha256"] != expected_head
        or value["expected_incident_sha256"] != expected_incident
        or value["expected_reconciliation_event_id"] != expected_reconciliation
        or value["expected_quarantine_inventory_sha256"] != expected_quarantine
        or value["reason_code"] != "CHAIN_VERIFIED_AND_FLAT_RECONCILIATION_REQUIRED"
    ):
        raise StageBEvidenceError("recovery approval does not bind the requested recovery")
    _require_regex(value["activation_epoch"], _ACTIVATION_EPOCH, "activation epoch")
    _require_regex(value["expected_head_sha256"], _SHA256, "expected head")
    _require_regex(value["expected_incident_sha256"], _SHA256, "expected incident")
    _require_regex(
        value["expected_reconciliation_event_id"], _EVENT_ALIAS, "expected reconciliation"
    )
    _require_regex(value["expected_quarantine_inventory_sha256"], _SHA256, "expected quarantine")
    approved_at = _parse_approved_at(cast(str, value["approved_at"]))
    age = now - approved_at
    if age < timedelta(0) or age > RECOVERY_APPROVAL_MAX_AGE:
        raise StageBEvidenceError("recovery approval is stale")


def _validate_recovery_record(value: Mapping[str, object]) -> None:
    expected = {
        "schema",
        "activation_epoch",
        "approval_sha256",
        "incident_sha256",
        "expected_head_sha256",
        "expected_reconciliation_event_id",
        "expected_quarantine_inventory_sha256",
        "validated_head_sha256",
        "activation_receipt_sha256",
        "quarantine_entry_count",
        "recorded_at",
    }
    _require_exact_fields(value, expected, "recovery record")
    if value["schema"] != "tios.demo_decision_evidence.recovery_record.v1":
        raise StageBEvidenceError("recovery record schema is invalid")
    _require_regex(value["activation_epoch"], _ACTIVATION_EPOCH, "activation epoch")
    for name in (
        "approval_sha256",
        "incident_sha256",
        "expected_head_sha256",
        "expected_quarantine_inventory_sha256",
        "validated_head_sha256",
        "activation_receipt_sha256",
    ):
        _require_regex(value[name], _SHA256, name)
    _require_regex(
        value["expected_reconciliation_event_id"], _EVENT_ALIAS, "expected reconciliation"
    )
    _require_int(value["quarantine_entry_count"], "quarantine entry count", 0, 1_000_000)
    canonical_utc(cast(str, value["recorded_at"]))


def _validate_recovery_events(
    *,
    new_events: Sequence[EvidenceEvent],
    prior_events: Sequence[EvidenceEvent],
    prior_reducer_state: Mapping[str, object] | None,
    prior_head_sha256: str | None,
    activation: ActivationContext,
) -> None:
    recovery_events = [
        event for event in new_events if event.event_type is EventType.RECOVERY_COMMITTED
    ]
    if not recovery_events:
        return
    if len(recovery_events) != 1 or prior_reducer_state is None or prior_head_sha256 is None:
        raise StageBEvidenceError("recovery append must contain one typed recovery commit")
    recovery_event = recovery_events[0]
    payload = recovery_event.payload
    recovery_sha256 = cast(str, payload["recovery_record_sha256"])
    record_path = activation.private_root / "recovery" / f"RECOVERY-{recovery_sha256}.json"
    record, record_raw = _load_secure_json(record_path, label="recovery record")
    _validate_recovery_record(record)
    if sha256_bytes(record_raw) != recovery_sha256:
        raise StageBEvidenceError("recovery event record digest is invalid")
    if (
        record["activation_epoch"] != activation.activation_epoch
        or prior_reducer_state["evidence_state"] != "ENTRY_BLOCK"
        or record["incident_sha256"] != prior_reducer_state["incident_sha256"]
        or record["incident_sha256"] != payload["incident_sha256"]
        or record["expected_head_sha256"] != prior_head_sha256
        or record["validated_head_sha256"] != prior_head_sha256
        or payload["prior_head_sha256"] != prior_head_sha256
        or record["approval_sha256"] != payload["approval_sha256"]
        or record["activation_receipt_sha256"] != activation.receipt_sha256
    ):
        raise StageBEvidenceError("recovery append cross-binding is invalid")
    expected = next(
        (
            event
            for event in prior_events
            if event.event_id == record["expected_reconciliation_event_id"]
        ),
        None,
    )
    if (
        expected is None
        or expected.event_type is not EventType.TERMINAL_RECONCILIATION_COMMITTED
        or expected.payload["flat"] is not True
        or expected.payload["protective_stop_state"] != "CLEAR"
        or expected.payload["all_pages_complete"] is not True
    ):
        raise StageBEvidenceError("recovery record expected reconciliation is invalid")
    fresh = next(
        (event for event in new_events if event.event_id == payload["reconciliation_event_id"]),
        None,
    )
    unresolved_alias = prior_reducer_state["unresolved_order_alias"]
    if (
        fresh is None
        or fresh.event_type is not EventType.TERMINAL_RECONCILIATION_COMMITTED
        or fresh.sequence >= recovery_event.sequence
        or fresh.event_id == record["expected_reconciliation_event_id"]
        or (unresolved_alias is not None and fresh.payload["order_alias"] != unresolved_alias)
        or fresh.payload["flat"] is not True
        or fresh.payload["protective_stop_state"] != "CLEAR"
        or fresh.payload["all_pages_complete"] is not True
    ):
        raise StageBEvidenceError(
            "recovery commit requires a distinct fresh exact flat reconciliation"
        )
    fresh_index = next(
        index for index, event in enumerate(new_events) if event.event_id == fresh.event_id
    )
    reconciled = reduce_events(
        tuple(prior_events) + tuple(new_events[: fresh_index + 1])
    ).reducer_state
    if (
        reconciled["evidence_state"] != "ENTRY_BLOCK"
        or reconciled["incident_sha256"] != prior_reducer_state["incident_sha256"]
        or reconciled["flat"] is not True
        or reconciled["protective_stop_state"] != "CLEAR"
    ):
        raise StageBEvidenceError("fresh reconciliation does not prove whole-lane recovery")


def _existing_matching_recovery(
    recovery_root: Path, identity: Mapping[str, object]
) -> tuple[Path, dict[str, object]] | None:
    for entry in os.scandir(recovery_root):
        path = Path(entry.path)
        value, _ = _load_secure_json(path, label="recovery record")
        _validate_recovery_record(value)
        if all(value.get(name) == expected for name, expected in identity.items()):
            return path, value
    return None


def create_recovery_record(
    *,
    repo_root: Path | str,
    approval_path: Path,
    expected_head: str,
    expected_incident: str,
    expected_reconciliation: str,
    expected_quarantine: str,
    now: datetime | None = None,
) -> Path:
    """Validate recovery evidence and create only one hash-addressed record."""

    if not approval_path.is_absolute():
        raise StageBEvidenceError("recovery approval path must be absolute")
    _require_regex(expected_head, _SHA256, "expected head")
    _require_regex(expected_incident, _SHA256, "expected incident")
    _require_regex(expected_reconciliation, _EVENT_ALIAS, "expected reconciliation")
    _require_regex(expected_quarantine, _SHA256, "expected quarantine")
    checked_at = datetime.now(UTC) if now is None else now.astimezone(UTC)
    approval, approval_raw = _load_secure_json(approval_path, label="recovery approval")

    activation = load_activation(repo_root, now=checked_at)
    snapshot = load_snapshot(activation)
    if snapshot.head_sha256 != expected_head or snapshot.reducer_state is None:
        raise StageBEvidenceError("validated chain head does not match recovery request")
    if snapshot.reducer_state["evidence_state"] != "ENTRY_BLOCK":
        raise StageBEvidenceError("recovery record requires ENTRY_BLOCK")
    if snapshot.reducer_state["incident_sha256"] != expected_incident:
        raise StageBEvidenceError("current evidence incident does not match recovery request")
    reconciliation = next(
        (event for event in snapshot.events if event.event_id == expected_reconciliation), None
    )
    if (
        reconciliation is None
        or reconciliation.event_type is not EventType.TERMINAL_RECONCILIATION_COMMITTED
        or reconciliation.payload["flat"] is not True
        or reconciliation.payload["protective_stop_state"] != "CLEAR"
        or reconciliation.payload["all_pages_complete"] is not True
        or (
            snapshot.reducer_state["unresolved_order_alias"] is not None
            and reconciliation.payload["order_alias"]
            != snapshot.reducer_state["unresolved_order_alias"]
        )
    ):
        raise StageBEvidenceError("expected recovery reconciliation is not exact and flat")
    inventory, actual_quarantine = quarantine_inventory(activation.private_root)
    if actual_quarantine != expected_quarantine:
        raise StageBEvidenceError("quarantine inventory changed")
    _validate_recovery_approval(
        approval,
        activation_epoch=activation.activation_epoch,
        expected_head=expected_head,
        expected_incident=expected_incident,
        expected_reconciliation=expected_reconciliation,
        expected_quarantine=expected_quarantine,
        now=checked_at,
    )
    approval_sha256 = sha256_bytes(approval_raw)
    identity: dict[str, object] = {
        "activation_epoch": activation.activation_epoch,
        "approval_sha256": approval_sha256,
        "incident_sha256": expected_incident,
        "expected_head_sha256": expected_head,
        "expected_reconciliation_event_id": expected_reconciliation,
        "expected_quarantine_inventory_sha256": expected_quarantine,
        "validated_head_sha256": expected_head,
        "activation_receipt_sha256": activation.receipt_sha256,
        "quarantine_entry_count": len(cast(list[object], inventory["entries"])),
    }
    recovery_root = activation.private_root / "recovery"
    existing = _existing_matching_recovery(recovery_root, identity)
    if existing is not None:
        return existing[0]
    record: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.recovery_record.v1",
        **identity,
        "recorded_at": canonical_utc(checked_at),
    }
    _validate_recovery_record(record)
    raw = canonical_json_bytes(record)
    digest = sha256_bytes(raw)
    path = recovery_root / f"RECOVERY-{digest}.json"
    if path.exists():
        if _read_secure_file(path) != raw:
            raise StageBEvidenceError("recovery record content-address conflict")
        return path
    _write_exclusive(path, raw)
    _fsync_directory(recovery_root)
    return path


def _build_parser() -> argparse.ArgumentParser:
    # ponytail: pre-activation debt. argparse may reflect invalid tokens back in its
    # usage/error text on stderr; the recovery CLI itself never echoes request values.
    # Upgrade path = custom non-reflecting arg handling; do NOT change the CONFIG contract
    # (create_attempts_per_logical_submission etc.) to work around it. Deferred until activation.
    parser = argparse.ArgumentParser(prog="python -m tios.evidence.demo_decision_evidence_v2")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recovery = subparsers.add_parser("recover")
    recovery.add_argument("--approval", type=Path, required=True)
    recovery.add_argument("--expected-head", required=True)
    recovery.add_argument("--expected-incident", required=True)
    recovery.add_argument("--expected-reconciliation", required=True)
    recovery.add_argument("--expected-quarantine", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.command != "recover":
        raise StageBEvidenceError("unsupported command")
    try:
        record = create_recovery_record(
            repo_root=Path.cwd(),
            approval_path=arguments.approval,
            expected_head=arguments.expected_head,
            expected_incident=arguments.expected_incident,
            expected_reconciliation=arguments.expected_reconciliation,
            expected_quarantine=arguments.expected_quarantine,
        )
    except (StageBEvidenceError, OSError):
        print("STAGE_B_RECOVERY_REFUSED", file=sys.stderr)
        return 2
    print(f"STAGE_B_RECOVERY_RECORD_OK {record.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
