"""Deterministic projections and append-only storage for offline decision traces."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from tios.trading_domain.decision_intelligence import (
    DEFECT_CLASSIFICATIONS,
    AttributionBasis,
    DecisionTrace,
    DecisionTraceStatus,
    HistoricalTradeTrace,
    OutcomeClassification,
)
from tios.trading_domain.models import RiskOutcome


class DecisionTraceLedgerError(ValueError):
    """A trace cannot be retained without violating append-only guarantees."""


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise DecisionTraceLedgerError("trace timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise DecisionTraceLedgerError(f"unsupported trace value: {type(value).__name__}")


LearningTrace = DecisionTrace | HistoricalTradeTrace


def canonical_trace_payload(trace: LearningTrace) -> dict[str, Any]:
    payload = _jsonable(trace)
    assert isinstance(payload, dict)
    return payload


def trace_digest(trace: LearningTrace) -> str:
    encoded = json.dumps(
        canonical_trace_payload(trace), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class DecisionTraceLedger:
    """Append-only JSONL ledger with idempotent replay and conflicting-replay rejection."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def append(self, trace: DecisionTrace) -> str:
        payload = canonical_trace_payload(trace)
        digest = trace_digest(trace)
        row = {"trace_id": trace.trace_id, "payload_sha256": digest, "payload": payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            existing = {item["trace_id"]: item for item in self.records()}
            if trace.trace_id in existing:
                if existing[trace.trace_id]["payload_sha256"] != digest:
                    raise DecisionTraceLedgerError(
                        "trace id conflicts with different retained content"
                    )
                return digest
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        return digest

    def records(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        try:
            rows = tuple(
                json.loads(line) for line in self.path.read_text().splitlines() if line.strip()
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise DecisionTraceLedgerError("decision trace ledger is unreadable") from exc
        trace_ids: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or not {
                "trace_id",
                "payload_sha256",
                "payload",
            }.issubset(row):
                raise DecisionTraceLedgerError("retained trace row is malformed")
            if not isinstance(row["payload"], dict):
                raise DecisionTraceLedgerError("retained trace payload is malformed")
            if row["trace_id"] != row["payload"].get("trace_id"):
                raise DecisionTraceLedgerError("retained trace identity mismatch")
            trace_ids.append(str(row["trace_id"]))
            payload_json = json.dumps(row["payload"], sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(payload_json.encode()).hexdigest() != row["payload_sha256"]:
                raise DecisionTraceLedgerError("retained trace digest mismatch")
        if len(set(trace_ids)) != len(trace_ids):
            raise DecisionTraceLedgerError("retained trace ids must be unique")
        return rows

    def digest(self) -> str:
        content = self.path.read_bytes() if self.path.exists() else b""
        return hashlib.sha256(content).hexdigest()


class HistoricalTradeTraceLedger:
    """Append-only batch ledger for reconstructed historical trade evidence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def append_many(self, traces: tuple[HistoricalTradeTrace, ...]) -> tuple[str, ...]:
        """Validate the full batch before a single append and fsync."""

        ids = [trace.trace_id for trace in traces]
        if len(set(ids)) != len(ids):
            raise DecisionTraceLedgerError("historical trace batch contains duplicate ids")
        pending = tuple(
            {
                "trace_id": trace.trace_id,
                "payload_sha256": trace_digest(trace),
                "payload": canonical_trace_payload(trace),
            }
            for trace in traces
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            existing = {item["trace_id"]: item for item in self.records()}
            for row in pending:
                prior = existing.get(row["trace_id"])
                if prior is not None and prior["payload_sha256"] != row["payload_sha256"]:
                    raise DecisionTraceLedgerError(
                        "trace id conflicts with different retained content"
                    )
            additions = tuple(row for row in pending if row["trace_id"] not in existing)
            if additions:
                encoded = "".join(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in additions
                )
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        return tuple(str(row["payload_sha256"]) for row in pending)

    def records(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        try:
            rows = tuple(
                json.loads(line) for line in self.path.read_text().splitlines() if line.strip()
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise DecisionTraceLedgerError("historical trade trace ledger is unreadable") from exc
        trace_ids: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or not {
                "trace_id",
                "payload_sha256",
                "payload",
            }.issubset(row):
                raise DecisionTraceLedgerError("retained trace row is malformed")
            payload = row["payload"]
            if not isinstance(payload, dict) or row["trace_id"] != payload.get("trace_id"):
                raise DecisionTraceLedgerError("retained trace identity mismatch")
            trace_ids.append(str(row["trace_id"]))
            payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(payload_json.encode()).hexdigest() != row["payload_sha256"]:
                raise DecisionTraceLedgerError("retained trace digest mismatch")
        if len(set(trace_ids)) != len(trace_ids):
            raise DecisionTraceLedgerError("retained trace ids must be unique")
        return rows

    def digest(self) -> str:
        content = self.path.read_bytes() if self.path.exists() else b""
        return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionIntelligenceReport:
    trace_count: int
    no_trade_count: int
    risk_blocked_count: int
    risk_passed_count: int
    intent_count: int
    order_count: int
    fill_event_count: int
    reconciled_count: int
    profitable_count: int
    ordinary_loss_count: int
    confirmed_defect_count: int
    ai_hypothesis_count: int
    unknown_count: int
    net_pnl: Decimal
    currency: str | None
    source_trace_digests: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "net_pnl": str(self.net_pnl),
            "source_trace_digests": list(self.source_trace_digests),
        }


def project_decision_report(
    traces: tuple[DecisionTrace, ...],
) -> DecisionIntelligenceReport:
    """Project a reproducible funnel and diagnosis summary from immutable traces."""

    ids = [trace.trace_id for trace in traces]
    if len(set(ids)) != len(ids):
        raise DecisionTraceLedgerError("report input contains duplicate trace ids")
    currencies = {trace.outcome.currency for trace in traces}
    if len(currencies) > 1:
        raise DecisionTraceLedgerError("report cannot sum outcomes with different currencies")
    ordered = tuple(sorted(traces, key=lambda trace: trace.trace_id))
    return DecisionIntelligenceReport(
        trace_count=len(ordered),
        no_trade_count=sum(trace.status is DecisionTraceStatus.NO_TRADE for trace in ordered),
        risk_blocked_count=sum(
            trace.status is DecisionTraceStatus.RISK_BLOCKED for trace in ordered
        ),
        risk_passed_count=sum(trace.risk.decision is RiskOutcome.PASS for trace in ordered),
        intent_count=sum(trace.intent is not None for trace in ordered),
        order_count=sum(trace.order_ref is not None for trace in ordered),
        fill_event_count=sum(len(trace.fills) for trace in ordered),
        reconciled_count=sum(
            trace.order_ref is not None and trace.outcome.reconciled for trace in ordered
        ),
        profitable_count=sum(
            trace.outcome.classification is OutcomeClassification.PROFITABLE for trace in ordered
        ),
        ordinary_loss_count=sum(
            trace.outcome.classification is OutcomeClassification.ORDINARY_STATISTICAL_LOSS
            for trace in ordered
        ),
        confirmed_defect_count=sum(
            trace.outcome.classification in DEFECT_CLASSIFICATIONS
            and trace.attribution is not None
            and trace.attribution.confirmed
            for trace in ordered
        ),
        ai_hypothesis_count=sum(
            trace.attribution is not None
            and trace.attribution.basis is AttributionBasis.AI_HYPOTHESIS
            for trace in ordered
        ),
        unknown_count=sum(
            trace.outcome.classification is OutcomeClassification.UNKNOWN for trace in ordered
        ),
        net_pnl=sum((trace.outcome.net_pnl for trace in ordered), start=Decimal("0")),
        currency=next(iter(currencies), None),
        source_trace_digests=tuple(trace_digest(trace) for trace in ordered),
    )
