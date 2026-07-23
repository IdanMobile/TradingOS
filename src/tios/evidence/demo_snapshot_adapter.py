"""Read-only, capability-free capture adapter for the active demo-lane snapshots.

The adapter opens three fixed local files, proves a stable best-effort bracket, removes
wallets and execution-adjacent material, and publishes one immutable private snapshot.
It imports no demo runtime, venue adapter, credential provider, or order transport.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from tios.evidence.demo_decision_bridge import (
    MAX_ORDERS_BYTES,
    MAX_SNAPSHOT_BYTES,
    DemoDecisionBridgeError,
    NumericLexeme,
    build_legacy_projection,
    canonical_timestamp,
    parse_json_bytes,
    parse_jsonl_bytes,
    prepare_private_output_dir,
    validate_no_secrets,
)

SCHEMA = "tios.demo_snapshot.v1"
ACTIVE_LANE = Path("artifacts/trading_domain/demo_lane")
SNAPSHOTS_ROOT = Path("artifacts/evidence/private_demo/snapshots")
MAX_CAPTURE_ATTEMPTS = 3
_SOURCE_NAMES = ("lane_state.json", "heartbeat.json", "orders.jsonl")
_FINAL_FILES = frozenset(
    {"lane_state.json", "heartbeat.json", "orders.jsonl", "coverage.json", "manifest.json"}
)
_DATA_FILES = _FINAL_FILES - {"manifest.json"}
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_SAFE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}")
_OPAQUE_ORDER_REF = re.compile(r"VOH-[a-f0-9]{32}")
_SNAPSHOT_TEMP = re.compile(
    r"^\.(?P<snapshot>SNAP-[a-f0-9]{64})\."
    r"(?P<target>lane_state\.json|heartbeat\.json|orders\.jsonl|coverage\.json|manifest\.json)"
    r"\.tmp-(?P<pid>[1-9][0-9]*)$"
)
_NO_VENUE_ORDER_STAGES = frozenset({"kill_switch", "price_unavailable", "qty_below_step", "place"})
_STOP_NUMBER_FIELDS = (
    "risk_boundary_price",
    "trigger_price",
    "base_qty",
    "position_base_qty",
    "risk_fraction",
    "price_tick",
)
_ORDER_NUMBER_FIELDS = ("avg_price", "cum_exec_qty", "fee", "qty", "price")
_ORDER_TEXT_FIELDS = (
    "schema_version",
    "recorded_at",
    "side",
    "reason",
    "unit",
    "symbol",
    "ok",
    "order_status",
    "stage",
    "validation_state",
    "environment",
    "promotion_eligible",
    "real_money",
)


class DemoSnapshotError(DemoDecisionBridgeError):
    """The active files cannot be captured without weakening the snapshot contract."""


class _RetryableSnapshotError(DemoSnapshotError):
    """A bracket or corroboration mismatch that may disappear on the next whole attempt."""


@dataclass(frozen=True, slots=True)
class DemoSnapshotResult:
    snapshot_id: str
    snapshot_dir: Path
    manifest: dict[str, object]
    coverage: dict[str, object]
    capture_attempts: int


@dataclass(frozen=True, slots=True)
class _StableRead:
    data: bytes
    metadata: tuple[int, int, int, int, int, int, int]


def _json_fragment(value: object) -> str:
    if isinstance(value, NumericLexeme):
        raw = str(value)
        if not _JSON_NUMBER.fullmatch(raw):
            raise DemoSnapshotError("retained JSON number lexeme is invalid")
        return raw
    if isinstance(value, Mapping):
        items = (
            f"{json.dumps(str(key), ensure_ascii=False)}:{_json_fragment(item)}"
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
        return "{" + ",".join(items) + "}"
    if isinstance(value, (tuple, list)):
        return "[" + ",".join(_json_fragment(item) for item in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    raise DemoSnapshotError(f"unsupported snapshot value: {type(value).__name__}")


def canonical_snapshot_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON while preserving parsed number tokens."""

    validate_no_secrets(value)
    return (_json_fragment(value) + "\n").encode("utf-8")


def _jsonl_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    if not rows:
        return b""
    return b"".join(canonical_snapshot_bytes(row) for row in rows)


def _metadata(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_fd(descriptor: int, *, byte_limit: int) -> bytes:
    chunks: list[bytes] = []
    retained = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, byte_limit + 1 - retained))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        retained += len(chunk)
        if retained > byte_limit:
            raise DemoSnapshotError("active source exceeds its fixed byte limit")


def _open_lane_descriptor(repo_root: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    try:
        current = os.open(repo_root.resolve(), flags | os.O_NOFOLLOW)
    except OSError as exc:
        raise DemoSnapshotError("repository root cannot be opened as a real directory") from exc
    try:
        for component in ACTIVE_LANE.parts:
            following = os.open(component, flags | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = following
        return current
    except OSError as exc:
        os.close(current)
        raise DemoSnapshotError("active demo-lane directory traversal is unsafe") from exc


def _read_entry(lane_descriptor: int, name: str, *, byte_limit: int) -> _StableRead:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        descriptor = os.open(name, flags, dir_fd=lane_descriptor)
    except OSError as exc:
        raise DemoSnapshotError(f"active source {name} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DemoSnapshotError(f"active source {name} must be a single-link regular file")
        first = _read_fd(descriptor, byte_limit=byte_limit)
        middle = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = _read_fd(descriptor, byte_limit=byte_limit)
        after = os.fstat(descriptor)
        try:
            linked = os.stat(name, dir_fd=lane_descriptor, follow_symlinks=False)
        except OSError as exc:
            raise _RetryableSnapshotError(f"active source {name} entry changed") from exc
        if (
            stat.S_ISLNK(linked.st_mode)
            or not stat.S_ISREG(linked.st_mode)
            or linked.st_nlink != 1
            or _metadata(before) != _metadata(middle)
            or _metadata(middle) != _metadata(after)
            or _metadata(linked) != _metadata(after)
            or first != second
        ):
            raise _RetryableSnapshotError(f"active source {name} changed during read")
        return _StableRead(first, _metadata(after))
    finally:
        os.close(descriptor)


def _read_bracket(repo_root: Path) -> tuple[bytes, bytes, bytes]:
    lane_descriptor = _open_lane_descriptor(repo_root)
    try:
        state1 = _read_entry(lane_descriptor, "lane_state.json", byte_limit=MAX_SNAPSHOT_BYTES)
        heartbeat1 = _read_entry(lane_descriptor, "heartbeat.json", byte_limit=MAX_SNAPSHOT_BYTES)
        orders1 = _read_entry(lane_descriptor, "orders.jsonl", byte_limit=MAX_ORDERS_BYTES)
        state2 = _read_entry(lane_descriptor, "lane_state.json", byte_limit=MAX_SNAPSHOT_BYTES)
        heartbeat2 = _read_entry(lane_descriptor, "heartbeat.json", byte_limit=MAX_SNAPSHOT_BYTES)
        orders2 = _read_entry(lane_descriptor, "orders.jsonl", byte_limit=MAX_ORDERS_BYTES)
        state3 = _read_entry(lane_descriptor, "lane_state.json", byte_limit=MAX_SNAPSHOT_BYTES)
        heartbeat3 = _read_entry(lane_descriptor, "heartbeat.json", byte_limit=MAX_SNAPSHOT_BYTES)
    finally:
        os.close(lane_descriptor)
    if not (
        state1 == state2 == state3 and heartbeat1 == heartbeat2 == heartbeat3 and orders1 == orders2
    ):
        raise _RetryableSnapshotError("active source bracket did not converge")
    return state1.data, heartbeat1.data, orders1.data


def _required_text(source: Mapping[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DemoSnapshotError(f"{key} must be a non-empty string")
    return value


def _safe_text(value: object, *, key: str) -> str:
    if not isinstance(value, str) or not _SAFE_TOKEN.fullmatch(value):
        raise DemoSnapshotError(f"{key} is not a bounded safe token")
    return value


def _required_bool(source: Mapping[str, object], key: str, expected: bool) -> bool:
    value = source.get(key)
    if value is not expected:
        raise _RetryableSnapshotError(f"{key} does not match the demo-only invariant")
    return expected


def _decimal(value: object, *, key: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, NumericLexeme, int)):
        raise DemoSnapshotError(f"{key} must be an exact JSON decimal or decimal string")
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise DemoSnapshotError(f"{key} is not a valid decimal") from exc
    if not parsed.is_finite():
        raise DemoSnapshotError(f"{key} must be finite")
    return parsed


def _retained_number(source: Mapping[str, object], key: str) -> object:
    if key not in source:
        raise DemoSnapshotError(f"{key} is required")
    _decimal(source[key], key=key)
    return source[key]


def snapshot_venue_order_ref(raw_order_id: object) -> str:
    text = str(raw_order_id).strip() if raw_order_id is not None else ""
    if not text:
        raise DemoSnapshotError("raw venue order id must be non-empty")
    digest = hashlib.sha256(f"{SCHEMA}:venue-order-id:{text}".encode()).hexdigest()
    return f"VOH-{digest[:32]}"


def _venue_order_identity_required(source: Mapping[str, object]) -> bool:
    return not (
        source.get("ok") is False
        and isinstance(source.get("stage"), str)
        and source["stage"] in _NO_VENUE_ORDER_STAGES
    )


def _order_ref(source: Mapping[str, object], *, required: bool) -> str | None:
    raw_present = "order_id" in source and source.get("order_id") is not None
    ref_present = "venue_order_ref" in source and source.get("venue_order_ref") is not None
    if raw_present and ref_present:
        raise DemoSnapshotError("order identity cannot contain both order_id and venue_order_ref")
    if not raw_present and not ref_present:
        if required:
            raise DemoSnapshotError(
                "successful or created venue order requires order_id or venue_order_ref"
            )
        return None
    if raw_present:
        return snapshot_venue_order_ref(source["order_id"])
    retained = source["venue_order_ref"]
    if not isinstance(retained, str) or not _OPAQUE_ORDER_REF.fullmatch(retained):
        raise DemoSnapshotError("venue_order_ref is invalid")
    return retained


def _sanitize_stop(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise DemoSnapshotError("resting_stop must be an object")
    state = _safe_text(value.get("state"), key="resting_stop.state")
    if state != "ACTIVE":
        raise _RetryableSnapshotError("resting_stop is not currently ACTIVE")
    result: dict[str, object] = {
        "state": state,
        "venue_order_ref": _order_ref(cast(Mapping[str, object], value), required=True),
    }
    for key in _STOP_NUMBER_FIELDS:
        if key not in value:
            raise _RetryableSnapshotError(f"resting_stop.{key} is required")
        number = _decimal(value[key], key=f"resting_stop.{key}")
        if number <= 0:
            raise _RetryableSnapshotError(f"resting_stop.{key} must be positive")
        result[key] = value[key]
    risk_fraction = _decimal(result["risk_fraction"], key="resting_stop.risk_fraction")
    if risk_fraction > 1:
        raise _RetryableSnapshotError("resting_stop.risk_fraction must not exceed one")
    return result


def _sanitize_state(source: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "cursor": canonical_timestamp(_required_text(source, "cursor")),
        "lane_base": _retained_number(source, "lane_base"),
        "entry_price": _retained_number(source, "entry_price"),
        "resting_stop": _sanitize_stop(source.get("resting_stop")),
    }
    return result


def _copy_optional_safe(source: Mapping[str, object], target: dict[str, object], key: str) -> None:
    if key not in source:
        return
    value = source[key]
    if isinstance(value, str):
        target[key] = _safe_text(value, key=key)
    elif value is None or isinstance(value, (bool, int, NumericLexeme)):
        target[key] = value
    else:
        raise DemoSnapshotError(f"{key} has an unsafe type")


def _sanitize_heartbeat(source: Mapping[str, object]) -> dict[str, object]:
    environment = _required_text(source, "environment")
    validation = _required_text(source, "validation_state")
    if environment != "VENUE_DEMO" or validation != "UNVALIDATED":
        raise _RetryableSnapshotError("heartbeat is not an unvalidated venue-demo observation")
    result: dict[str, object] = {
        "at": canonical_timestamp(_required_text(source, "at")),
        "environment": environment,
        "latest_closed_bar": canonical_timestamp(_required_text(source, "latest_closed_bar")),
        "lane_base": _retained_number(source, "lane_base"),
        "entry_price": _retained_number(source, "entry_price"),
        "mark_price": _retained_number(source, "mark_price"),
        "resting_stop": _sanitize_stop(source.get("resting_stop")),
        "validation_state": validation,
        "promotion_eligible": _required_bool(source, "promotion_eligible", False),
        "real_money": _required_bool(source, "real_money", False),
    }
    for key in (
        "schema_version",
        "candidate",
        "fresh_signals",
        "signals_in_window",
        "kill_switch",
    ):
        _copy_optional_safe(source, result, key)
    return result


def _sanitize_order(source: Mapping[str, object]) -> dict[str, object]:
    environment = _required_text(source, "environment")
    validation = _required_text(source, "validation_state")
    if environment != "VENUE_DEMO" or validation != "UNVALIDATED":
        raise _RetryableSnapshotError("order is not an unvalidated venue-demo observation")
    result: dict[str, object] = {
        "recorded_at": canonical_timestamp(_required_text(source, "recorded_at")),
        "environment": environment,
        "validation_state": validation,
        "promotion_eligible": _required_bool(source, "promotion_eligible", False),
        "real_money": _required_bool(source, "real_money", False),
        "venue_order_ref": _order_ref(
            source,
            required=_venue_order_identity_required(source),
        ),
    }
    for key in _ORDER_TEXT_FIELDS:
        if key in result or key not in source:
            continue
        _copy_optional_safe(source, result, key)
    for key in _ORDER_NUMBER_FIELDS:
        if key in source:
            _decimal(source[key], key=key)
            result[key] = source[key]
    if "reconcile" in source:
        reconciliation = source["reconcile"]
        if not isinstance(reconciliation, Mapping) or not reconciliation:
            raise DemoSnapshotError("reconcile must be a non-empty object")
        deltas: dict[str, object] = {}
        for raw_key, value in sorted(reconciliation.items(), key=lambda item: str(item[0])):
            key = str(raw_key)
            if not re.fullmatch(r"[A-Z0-9]{2,16}_delta", key):
                continue
            _decimal(value, key=f"reconcile.{key}")
            deltas[key] = value
        if not deltas:
            raise DemoSnapshotError("reconcile retained no recognized decimal deltas")
        result["reconcile"] = deltas
    if source.get("signal_ref") is not None:
        result["signal_ref_sha256"] = hashlib.sha256(
            str(source["signal_ref"]).encode("utf-8")
        ).hexdigest()
    return result


def _semantic_corroboration(
    state: Mapping[str, object],
    heartbeat: Mapping[str, object],
    orders: Sequence[Mapping[str, object]],
    *,
    captured_at: str,
) -> None:
    if state["cursor"] != heartbeat["latest_closed_bar"]:
        raise _RetryableSnapshotError("state cursor and heartbeat latest bar disagree")
    if _decimal(state["lane_base"], key="lane_base") <= 0:
        raise _RetryableSnapshotError("demo snapshot has no positive exposure")
    if _decimal(state["entry_price"], key="entry_price") <= 0:
        raise _RetryableSnapshotError("demo snapshot has no retained positive entry")
    if _decimal(heartbeat["mark_price"], key="mark_price") <= 0:
        raise _RetryableSnapshotError("demo snapshot has no positive mark price")
    for key in ("lane_base", "entry_price"):
        if _decimal(state[key], key=key) != _decimal(heartbeat[key], key=key):
            raise _RetryableSnapshotError(f"state and heartbeat {key} disagree")
    state_stop = cast(Mapping[str, object], state["resting_stop"])
    heartbeat_stop = cast(Mapping[str, object], heartbeat["resting_stop"])
    if (
        state_stop["state"] != heartbeat_stop["state"]
        or state_stop["venue_order_ref"] != heartbeat_stop["venue_order_ref"]
        or set(state_stop) != set(heartbeat_stop)
        or any(
            _decimal(state_stop[key], key=f"resting_stop.{key}")
            != _decimal(heartbeat_stop[key], key=f"resting_stop.{key}")
            for key in set(state_stop) - {"state", "venue_order_ref"}
        )
    ):
        raise _RetryableSnapshotError("state and heartbeat resting_stop disagree")
    position_base = _decimal(state_stop["position_base_qty"], key="resting_stop.position_base_qty")
    stop_base = _decimal(state_stop["base_qty"], key="resting_stop.base_qty")
    lane_base = _decimal(state["lane_base"], key="lane_base")
    boundary = _decimal(state_stop["risk_boundary_price"], key="resting_stop.risk_boundary_price")
    trigger = _decimal(state_stop["trigger_price"], key="resting_stop.trigger_price")
    mark = _decimal(heartbeat["mark_price"], key="mark_price")
    if position_base != lane_base:
        raise _RetryableSnapshotError("resting_stop.position_base_qty does not match lane exposure")
    if stop_base > position_base:
        raise _RetryableSnapshotError("resting_stop.base_qty exceeds lane exposure")
    if not (boundary <= trigger < mark):
        raise _RetryableSnapshotError("resting_stop prices are incoherent with current mark")
    heartbeat_at = datetime.fromisoformat(str(heartbeat["at"]).replace("Z", "+00:00"))
    latest_bar = datetime.fromisoformat(str(heartbeat["latest_closed_bar"]).replace("Z", "+00:00"))
    captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    if heartbeat_at < latest_bar:
        raise _RetryableSnapshotError("heartbeat predates its latest closed bar")
    if captured < heartbeat_at:
        raise _RetryableSnapshotError("captured_at predates the retained heartbeat")
    for order in orders:
        recorded_at = datetime.fromisoformat(str(order["recorded_at"]).replace("Z", "+00:00"))
        if recorded_at > heartbeat_at:
            raise _RetryableSnapshotError("an order observation postdates the heartbeat")
        if captured < recorded_at:
            raise _RetryableSnapshotError("captured_at predates an order observation")


def _reference(kind: str, label: str, payload: bytes) -> dict[str, object]:
    return {
        "kind": kind,
        "label": label,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _numeric_fidelity_counts(values: Sequence[object]) -> dict[str, object]:
    raw_numbers = 0
    decimal_strings = 0

    def visit(value: object) -> None:
        nonlocal raw_numbers, decimal_strings
        if isinstance(value, NumericLexeme):
            raw_numbers += 1
        elif isinstance(value, str):
            try:
                parsed = Decimal(value)
            except Exception:
                return
            if parsed.is_finite():
                decimal_strings += 1
        elif isinstance(value, Mapping):
            for item in value.values():
                visit(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)

    for value in values:
        visit(value)
    return {
        "raw_json_number_count": raw_numbers,
        "decimal_string_count": decimal_strings,
        "raw_json_number_fraction": None,
        "decimal_string_fraction": None,
    }


def _coverage(
    *,
    raw_refs: Sequence[Mapping[str, object]],
    output_refs: Sequence[Mapping[str, object]],
    sanitized_values: Sequence[object],
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "capture_status": "PASS",
        "evidence_completeness": "PARTIAL_LEGACY_OPEN",
        "stage_a_input_ready": True,
        "stage_a_commit_status": "NOT_RUN",
        "snapshot_consistency": "BEST_EFFORT_MULTI_FILE",
        "position_state": "OPEN_INCOMPLETE",
        "realized_outcome_count": 0,
        "pnl_available": False,
        "strategy_evaluation_available": False,
        "historical_bar_decision_coverage": "UNAVAILABLE",
        "historical_bar_decision_coverage_fraction": None,
        "no_trade_coverage": "UNAVAILABLE",
        "no_trade_coverage_fraction": None,
        "block_refusal_duplicate_expiry_coverage": "UNAVAILABLE",
        "block_refusal_duplicate_expiry_coverage_fraction": None,
        "order_coverage": "AGGREGATE_OBSERVATIONS_ONLY",
        "order_coverage_fraction": None,
        "fill_coverage": "NO_INDIVIDUAL_FILL_IDS",
        "fill_coverage_fraction": None,
        "stop_coverage": "CURRENT_STATE_ONLY",
        "stop_coverage_fraction": None,
        "cursor_coverage": "CURRENT_VALUE_ONLY",
        "cursor_coverage_fraction": None,
        "wallet_balance_exported": False,
        "execution_authority": "NONE",
        "promotion_eligible": False,
        "numeric_fidelity": _numeric_fidelity_counts(sanitized_values),
        "source_digests": [dict(item) for item in raw_refs],
        "output_digests": [dict(item) for item in output_refs],
    }


def _read_private_file(
    path: Path,
    *,
    allowed_links: frozenset[int],
) -> tuple[bytes, os.stat_result]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise DemoSnapshotError("retained snapshot entry cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink not in allowed_links:
            raise DemoSnapshotError("retained snapshot entry has an invalid link count")
        if stat.S_IMODE(before.st_mode) != 0o600:
            raise DemoSnapshotError("retained snapshot files must have 0600 permissions")
        data = _read_fd(descriptor, byte_limit=MAX_ORDERS_BYTES)
        after = os.fstat(descriptor)
        try:
            linked = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise DemoSnapshotError("retained snapshot entry became unlinked") from exc
        if (
            _metadata(before) != _metadata(after)
            or stat.S_ISLNK(linked.st_mode)
            or _metadata(linked) != _metadata(after)
        ):
            raise DemoSnapshotError("retained snapshot entry changed during verification")
        return data, after
    finally:
        os.close(descriptor)


def _assert_private_file(path: Path) -> bytes:
    return _read_private_file(path, allowed_links=frozenset({1}))[0]


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _recover_snapshot_temporaries(
    *,
    snapshots_root: Path,
    snapshot_dir: Path,
    snapshot_id: str,
    payloads: Mapping[str, bytes],
    target_names: frozenset[str],
) -> None:
    prefix = f".{snapshot_id}."
    for temporary in sorted(snapshots_root.iterdir(), key=lambda path: path.name):
        if not temporary.name.startswith(prefix):
            continue
        match = _SNAPSHOT_TEMP.fullmatch(temporary.name)
        if match is None or match.group("snapshot") != snapshot_id:
            raise DemoSnapshotError("snapshot root contains a malformed known temporary")
        target_name = match.group("target")
        if target_name not in target_names:
            continue
        target = snapshot_dir / target_name
        expected = payloads[target_name]
        retained, temp_info = _read_private_file(
            temporary,
            allowed_links=frozenset({1, 2}),
        )
        if retained != expected:
            temporary.unlink()
            _fsync_directory(snapshots_root)
            continue
        if target.exists() or target.is_symlink():
            target_info = target.stat(follow_symlinks=False)
            if (target_info.st_dev, target_info.st_ino) != (
                temp_info.st_dev,
                temp_info.st_ino,
            ) and _assert_private_file(target) != expected:
                raise DemoSnapshotError("snapshot temporary conflicts with retained target")
            temporary.unlink()
        else:
            os.link(temporary, target, follow_symlinks=False)
            temporary.unlink()
        _fsync_directory(snapshot_dir)
        _fsync_directory(snapshots_root)


def _write_create_only(
    path: Path,
    payload: bytes,
    *,
    snapshots_root: Path,
) -> None:
    if path.exists() or path.is_symlink():
        if _assert_private_file(path) != payload:
            raise DemoSnapshotError("immutable snapshot file conflicts with retained bytes")
        return
    temporary = snapshots_root / f".{path.parent.name}.{path.name}.tmp-{os.getpid()}"
    if temporary.exists() or temporary.is_symlink():
        raise DemoSnapshotError("snapshot temporary path already exists")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        created = os.fstat(descriptor)
        if (
            not stat.S_ISREG(created.st_mode)
            or created.st_nlink != 1
            or stat.S_IMODE(created.st_mode) != 0o600
        ):
            raise DemoSnapshotError("new snapshot temporary is not a private regular file")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError:
        temporary.unlink()
        if _assert_private_file(path) != payload:
            raise DemoSnapshotError(
                "immutable snapshot file conflicts with concurrent bytes"
            ) from None
        return
    temporary.unlink()
    _fsync_directory(path.parent)
    _fsync_directory(snapshots_root)


def _publish_snapshot(
    *,
    repo_root: Path,
    snapshot_id: str,
    payloads: Mapping[str, bytes],
) -> Path:
    snapshots_root = prepare_private_output_dir(SNAPSHOTS_ROOT, repo_root=repo_root)
    snapshot_dir = prepare_private_output_dir(SNAPSHOTS_ROOT / snapshot_id, repo_root=repo_root)
    if stat.S_IMODE(snapshot_dir.stat().st_mode) != 0o700:
        raise DemoSnapshotError("snapshot directory must have 0700 permissions")
    _recover_snapshot_temporaries(
        snapshots_root=snapshots_root,
        snapshot_dir=snapshot_dir,
        snapshot_id=snapshot_id,
        payloads=payloads,
        target_names=_DATA_FILES,
    )
    entries = {entry.name for entry in snapshot_dir.iterdir()}
    if not entries.issubset(_FINAL_FILES):
        raise DemoSnapshotError("snapshot directory contains unexpected or temporary entries")
    if "manifest.json" in entries and entries != _FINAL_FILES:
        raise DemoSnapshotError("manifest exists for an incomplete snapshot")
    for name in entries - {"manifest.json"}:
        if _assert_private_file(snapshot_dir / name) != payloads[name]:
            raise DemoSnapshotError("snapshot id conflicts with retained content")
    for name in sorted(_DATA_FILES):
        _write_create_only(
            snapshot_dir / name,
            payloads[name],
            snapshots_root=snapshots_root,
        )
    if any(_assert_private_file(snapshot_dir / name) != payloads[name] for name in _DATA_FILES):
        raise DemoSnapshotError("snapshot data verification failed before manifest commit")
    _recover_snapshot_temporaries(
        snapshots_root=snapshots_root,
        snapshot_dir=snapshot_dir,
        snapshot_id=snapshot_id,
        payloads=payloads,
        target_names=frozenset({"manifest.json"}),
    )
    if any(_assert_private_file(snapshot_dir / name) != payloads[name] for name in _DATA_FILES):
        raise DemoSnapshotError("snapshot data changed before manifest recovery")
    _write_create_only(
        snapshot_dir / "manifest.json",
        payloads["manifest.json"],
        snapshots_root=snapshots_root,
    )
    if {entry.name for entry in snapshot_dir.iterdir()} != _FINAL_FILES:
        raise DemoSnapshotError("snapshot publication did not produce the fixed inventory")
    for name in _FINAL_FILES:
        if _assert_private_file(snapshot_dir / name) != payloads[name]:
            raise DemoSnapshotError("published snapshot bytes failed final verification")
    _fsync_directory(snapshot_dir)
    _fsync_directory(snapshots_root)
    return snapshot_dir


def _build_snapshot(
    *,
    raw_state: bytes,
    raw_heartbeat: bytes,
    raw_orders: bytes,
    captured_at: str,
    capture_attempts: int,
    repo_root: Path,
) -> DemoSnapshotResult:
    if raw_orders and not raw_orders.endswith(b"\n"):
        raise DemoSnapshotError("orders.jsonl must end with a terminal newline")
    if any(not line.strip() for line in raw_orders.splitlines()):
        raise DemoSnapshotError("orders.jsonl must not contain blank lines")
    state_source = parse_json_bytes(raw_state, label="active lane_state.json")
    heartbeat_source = parse_json_bytes(raw_heartbeat, label="active heartbeat.json")
    order_sources = parse_jsonl_bytes(raw_orders, label="active orders.jsonl")
    validate_no_secrets(state_source, path="$.raw_lane_state")
    validate_no_secrets(heartbeat_source, path="$.raw_heartbeat")
    validate_no_secrets(order_sources, path="$.raw_orders")
    state = _sanitize_state(state_source)
    heartbeat = _sanitize_heartbeat(heartbeat_source)
    orders = tuple(_sanitize_order(order) for order in order_sources)
    _semantic_corroboration(state, heartbeat, orders, captured_at=captured_at)

    state_bytes = canonical_snapshot_bytes(state)
    heartbeat_bytes = canonical_snapshot_bytes(heartbeat)
    orders_bytes = _jsonl_bytes(orders)
    raw_refs = (
        _reference("lane_state", "active-demo.lane_state", raw_state),
        _reference("heartbeat", "active-demo.heartbeat", raw_heartbeat),
        _reference("orders", "active-demo.orders", raw_orders),
    )
    output_refs = (
        _reference("lane_state", "snapshot.lane_state", state_bytes),
        _reference("heartbeat", "snapshot.heartbeat", heartbeat_bytes),
        _reference("orders", "snapshot.orders", orders_bytes),
    )
    build_legacy_projection(
        state,
        heartbeat,
        orders,
        source_refs=output_refs,
        captured_at=captured_at,
        source_label="active-demo-snapshot",
    )
    coverage = _coverage(
        raw_refs=raw_refs,
        output_refs=output_refs,
        sanitized_values=(state, heartbeat, orders),
    )
    coverage_bytes = canonical_snapshot_bytes(coverage)
    all_output_refs = (
        *output_refs,
        _reference("coverage", "snapshot.coverage", coverage_bytes),
    )
    identity = {
        "schema": SCHEMA,
        "captured_at": captured_at,
        "source_labels": [item["label"] for item in raw_refs],
        "source_files": [dict(item) for item in raw_refs],
        "sanitized_files": [dict(item) for item in all_output_refs],
    }
    digest = hashlib.sha256(canonical_snapshot_bytes(identity)).hexdigest()
    snapshot_id = f"SNAP-{digest}"
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "snapshot_id": snapshot_id,
        "captured_at": captured_at,
        "source_files": [dict(item) for item in raw_refs],
        "sanitized_files": [dict(item) for item in all_output_refs],
        "snapshot_consistency": "BEST_EFFORT_MULTI_FILE",
        "execution_authority": "NONE",
        "promotion_eligible": False,
    }
    payloads = {
        "lane_state.json": state_bytes,
        "heartbeat.json": heartbeat_bytes,
        "orders.jsonl": orders_bytes,
        "coverage.json": coverage_bytes,
        "manifest.json": canonical_snapshot_bytes(manifest),
    }
    snapshot_dir = _publish_snapshot(
        repo_root=repo_root,
        snapshot_id=snapshot_id,
        payloads=payloads,
    )
    return DemoSnapshotResult(
        snapshot_id=snapshot_id,
        snapshot_dir=snapshot_dir,
        manifest=manifest,
        coverage=coverage,
        capture_attempts=capture_attempts,
    )


def capture_demo_snapshot(*, captured_at: str, repo_root: Path) -> DemoSnapshotResult:
    """Capture the fixed active sources after at most three whole bracket attempts."""

    try:
        canonical_captured_at = canonical_timestamp(captured_at)
    except DemoDecisionBridgeError as exc:
        raise DemoSnapshotError(str(exc)) from exc
    last_retry: _RetryableSnapshotError | None = None
    for attempt in range(1, MAX_CAPTURE_ATTEMPTS + 1):
        try:
            state, heartbeat, orders = _read_bracket(repo_root)
            return _build_snapshot(
                raw_state=state,
                raw_heartbeat=heartbeat,
                raw_orders=orders,
                captured_at=canonical_captured_at,
                capture_attempts=attempt,
                repo_root=repo_root,
            )
        except _RetryableSnapshotError as exc:
            last_retry = exc
        except DemoSnapshotError:
            raise
        except DemoDecisionBridgeError as exc:
            raise DemoSnapshotError(str(exc)) from exc
    detail = str(last_retry) if last_retry is not None else "active sources did not converge"
    raise DemoSnapshotError(f"UNSTABLE_ACTIVE_SOURCE: {detail}")
