"""Typed, order-inert projection from a finalized public-data checkpoint."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from tios.services.observations.flow import AUTHORITY, OBSERVATION_ROOT
from tios.trading_domain import (
    CreatorType,
    DomainRef,
    InstrumentId,
    Provenance,
    RiskCheck,
    RiskDecision,
    RiskId,
    RiskOutcome,
    RiskStateSignalEvent,
    RunId,
    Side,
    SignalId,
    Timeframe,
)

SIGNAL_SPEC_ID = "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1"
INSTRUMENT = InstrumentId("BTC-USD.BINANCE_COIN_M")
RATIONALE = "PROSPECTIVE_WARMUP_BLOCK"
RISK_REASON = "NOT_PROMOTION_ELIGIBLE_AND_WARMUP_BLOCK"


class RiskSignalFlowError(RuntimeError):
    """A checkpoint cannot be projected without crossing a frozen boundary."""


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise RiskSignalFlowError(f"{field} is invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise RiskSignalFlowError(f"{field} has no timezone")
    return parsed.astimezone(UTC)


def _load_checkpoint(root: Path, artifact_ref: object) -> tuple[dict[str, Any], str, str]:
    if not isinstance(artifact_ref, str):
        raise RiskSignalFlowError("finalized checkpoint reference is invalid")
    repo = root.resolve()
    path = (repo / artifact_ref).resolve()
    expected_parent = (repo / OBSERVATION_ROOT).resolve()
    if path.parent != expected_parent or not path.is_file():
        raise RiskSignalFlowError("finalized checkpoint escapes the observation root")
    match = re.fullmatch(r"session_([0-9a-f]{64})\.json", path.name)
    if match is None:
        raise RiskSignalFlowError("finalized checkpoint name is invalid")
    encoded = path.read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    if digest != match.group(1):
        raise RiskSignalFlowError("finalized checkpoint content hash mismatch")
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise RiskSignalFlowError("finalized checkpoint is unreadable") from error
    if not isinstance(payload, dict):
        raise RiskSignalFlowError("finalized checkpoint must be an object")
    return cast(dict[str, Any], payload), digest, path.relative_to(repo).as_posix()


def _latest_finalized(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    if observation.get("availability") != "AVAILABLE":
        raise RiskSignalFlowError("managed observation is unavailable")
    evidence = observation.get("evidence")
    if not isinstance(evidence, Mapping):
        raise RiskSignalFlowError("managed observation evidence is invalid")
    latest = evidence.get("latest")
    if not isinstance(latest, list):
        raise RiskSignalFlowError("managed observation latest evidence is invalid")
    finalized = [
        row
        for row in latest
        if isinstance(row, Mapping) and row.get("checkpoint_status") == "FINALIZED"
    ]
    if not finalized:
        raise RiskSignalFlowError("no finalized checkpoint is available")
    return max(finalized, key=lambda row: int(row.get("checkpoint_index", -1)))


def _typed_records(
    payload: Mapping[str, Any], digest: str
) -> tuple[RiskStateSignalEvent, RiskDecision, Mapping[str, Any]]:
    if payload.get("schema_version") != 5 or payload.get("authority") != AUTHORITY:
        raise RiskSignalFlowError("checkpoint schema or authority boundary changed")
    metadata = payload.get("persistent_observation")
    source = payload.get("source")
    raw_signal = payload.get("signal")
    raw_risk = payload.get("risk_decision")
    if not all(isinstance(item, Mapping) for item in (metadata, source, raw_signal, raw_risk)):
        raise RiskSignalFlowError("checkpoint signal envelope is incomplete")
    metadata = cast(Mapping[str, Any], metadata)
    source = cast(Mapping[str, Any], source)
    raw_signal = cast(Mapping[str, Any], raw_signal)
    raw_risk = cast(Mapping[str, Any], raw_risk)
    if metadata.get("checkpoint_status") != "FINALIZED":
        raise RiskSignalFlowError("checkpoint is not finalized")
    if source.get("status") != "COMPLETE" or any(
        source.get(key) != value
        for key, value in {
            "authentication": "NONE",
            "pair": "BTCUSD",
            "symbol": "BTCUSD_PERP",
            "complete_liquidation_tape": False,
        }.items()
    ):
        raise RiskSignalFlowError("checkpoint public-data source boundary changed")
    started = _parse_utc(payload.get("started_at"), "started_at")
    ended = _parse_utc(payload.get("ended_at"), "ended_at")
    if ended - started != timedelta(minutes=5):
        raise RiskSignalFlowError("checkpoint is not one complete five-minute window")
    coverage_started = _parse_utc(source.get("coverage_started_at"), "coverage_started_at")
    coverage_ended = _parse_utc(source.get("coverage_ended_at"), "coverage_ended_at")
    if coverage_started != started or coverage_ended != ended:
        raise RiskSignalFlowError("checkpoint source coverage does not match its window")
    expected_signal = {
        "side": "FLAT",
        "rationale_code": RATIONALE,
        "metric_eligible": False,
        "scorecard_eligible": False,
        "promotion_eligible": False,
    }
    if any(raw_signal.get(key) != value for key, value in expected_signal.items()):
        raise RiskSignalFlowError("checkpoint signal crossed its warmup boundary")
    if raw_risk != {"decision": "BLOCK", "independent": True, "reason": RISK_REASON}:
        raise RiskSignalFlowError("checkpoint independent risk decision changed")
    run_id = metadata.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{24}", run_id):
        raise RiskSignalFlowError("checkpoint run id is invalid")
    evidence = DomainRef(f"EV-{digest}")
    provenance = Provenance((evidence,))
    signal = RiskStateSignalEvent(
        signal_id=SignalId(str(raw_signal.get("signal_id"))),
        signal_spec_id=SIGNAL_SPEC_ID,
        run_ref=RunId(f"RUN-{run_id}"),
        instrument=INSTRUMENT,
        timeframe=Timeframe.M5,
        observed_at=ended,
        side=Side.FLAT,
        rationale_code=RATIONALE,
        metric_eligible=False,
        scorecard_eligible=False,
        promotion_eligible=False,
        created_at=ended,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    check = RiskCheck(
        rule_code="PROMOTION_AND_WARMUP_GATE",
        outcome=RiskOutcome.BLOCK,
        evidence_refs=(evidence,),
        detail=RISK_REASON,
    )
    risk = RiskDecision(
        risk_id=RiskId(f"RISK-{digest}"),
        subject_ref=DomainRef(str(signal.signal_id)),
        as_of=ended,
        decision=RiskOutcome.BLOCK,
        rule_results=(check,),
        evidence_refs=(evidence,),
        created_at=ended,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    return signal, risk, metadata


def _base_projection() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "availability": "MISSING",
        "flow_state": "BLOCKED",
        "checkpoint": None,
        "signal": None,
        "risk_decision": None,
        "blockers": ["FINALIZED_CHECKPOINT_MISSING"],
        "capabilities": {**AUTHORITY, "order_creation": False},
    }


def build_risk_signal_projection(root: Path, observation: Mapping[str, Any]) -> dict[str, Any]:
    """Project checkpoint → typed risk signal → independent risk decision, or block."""
    projection = _base_projection()
    try:
        row = _latest_finalized(observation)
        payload, digest, artifact_ref = _load_checkpoint(root, row.get("artifact_ref"))
        signal, risk, metadata = _typed_records(payload, digest)
        if int(row.get("checkpoint_index", -1)) != int(metadata.get("checkpoint_index", -2)):
            raise RiskSignalFlowError("checkpoint projection index mismatch")
        projection.update(
            availability="AVAILABLE",
            flow_state="RISK_BLOCKED",
            checkpoint={
                "artifact_ref": artifact_ref,
                "sha256": digest,
                "checkpoint_index": int(metadata["checkpoint_index"]),
                "started_at": payload["started_at"],
                "ended_at": payload["ended_at"],
            },
            signal={
                "signal_id": str(signal.signal_id),
                "signal_spec_id": signal.signal_spec_id,
                "run_ref": str(signal.run_ref),
                "instrument": signal.instrument.value,
                "timeframe": signal.timeframe.value,
                "observed_at": signal.observed_at.isoformat(),
                "side": signal.side.value,
                "rationale_code": signal.rationale_code,
                "metric_eligible": signal.metric_eligible,
                "scorecard_eligible": signal.scorecard_eligible,
                "promotion_eligible": signal.promotion_eligible,
            },
            risk_decision={
                "risk_id": str(risk.risk_id),
                "subject_ref": str(risk.subject_ref),
                "as_of": risk.as_of.isoformat(),
                "decision": risk.decision.value,
                "independent": risk.independent,
                "rule_results": [
                    {
                        "rule_code": check.rule_code,
                        "outcome": check.outcome.value,
                        "detail": check.detail,
                        "evidence_refs": [str(ref) for ref in check.evidence_refs],
                    }
                    for check in risk.rule_results
                ],
                "evidence_refs": [str(ref) for ref in risk.evidence_refs],
            },
            blockers=[RISK_REASON],
        )
    except Exception as error:
        projection.update(
            availability="ERROR",
            flow_state="BLOCKED",
            blockers=[f"{type(error).__name__}: {error}"],
        )
    return projection
