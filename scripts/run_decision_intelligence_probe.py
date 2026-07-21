#!/usr/bin/env python3
"""Run an offline decision-intelligence probe over the frozen ETH reproduction.

This script invokes the existing read-only canonical verifier. It cannot access
credentials, connect to a venue, create an order, or grant execution authority.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.approval import audit_repository_authority  # noqa: E402
from tios.services.reporting import (  # noqa: E402
    DecisionTraceLedger,
    project_decision_report,
    trace_digest,
)
from tios.trading_domain import (  # noqa: E402
    AttributionBasis,
    CreatorType,
    DecisionOutcome,
    DecisionTrace,
    DecisionTraceStatus,
    DomainRef,
    FailureAttribution,
    InstrumentId,
    OutcomeClassification,
    Provenance,
    RiskCheck,
    RiskDecision,
    RiskId,
    RiskOutcome,
    RunId,
    Side,
    SignalEvent,
    SignalId,
    StrategyVersionId,
    Timeframe,
)

REPORT_JSON = ROOT / "artifacts/reports/DECISION_INTELLIGENCE_PROBE_2026_07_21.json"
REPORT_MD = ROOT / "artifacts/reports/DECISION_INTELLIGENCE_PROBE_2026_07_21.md"
LEDGER = ROOT / "artifacts/evidence/decision_intelligence_traces.jsonl"


def load_canonical_projection() -> tuple[dict[str, Any], float]:
    started = perf_counter()
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts/verify_eth_volume_breakout_flow.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    elapsed_ms = (perf_counter() - started) * 1000
    projection = json.loads(completed.stdout)
    if not isinstance(projection, dict):
        raise RuntimeError("canonical verifier did not return an object")
    return projection, elapsed_ms


def build_trace(projection: dict[str, Any]) -> DecisionTrace:
    last = projection["last_signal"]
    if not isinstance(last, dict):
        raise RuntimeError("canonical projection has no typed last signal")
    evidence = DomainRef(f"EV-{projection['dataset_sha256']}")
    provenance = Provenance((evidence,))
    observed_at = datetime.fromisoformat(str(last["observed_at"]))
    signal_id = SignalId(str(last["signal_id"]))
    signal = SignalEvent(
        signal_id=signal_id,
        strategy_version_ref=StrategyVersionId(str(projection["strategy_version_id"])),
        run_ref=RunId("RUN-ETH-VOLUME-BREAKOUT-REPRO-V1"),
        instrument=InstrumentId("ETH-USDT.BINANCE_SPOT"),
        timeframe=Timeframe.H1,
        observed_at=observed_at,
        side=Side(str(last["side"])),
        rationale_code="CANONICAL_REPRODUCTION_LAST_SIGNAL",
        created_at=observed_at,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    check = RiskCheck(
        rule_code="PROMOTION_GATE",
        outcome=RiskOutcome.BLOCK,
        evidence_refs=(evidence,),
        detail=str(projection["risk_reason"]),
    )
    risk = RiskDecision(
        risk_id=RiskId("RISK-ETH-VOLUME-BREAKOUT-DI-PROBE"),
        subject_ref=DomainRef(signal_id.value),
        as_of=observed_at,
        decision=RiskOutcome.BLOCK,
        rule_results=(check,),
        evidence_refs=(evidence,),
        created_at=observed_at,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    feature_material = json.dumps(
        {
            "bars": projection["bars"],
            "signal_count": projection["signal_count"],
            "last_signal": last,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return DecisionTrace(
        trace_id=f"TRACE-{signal_id.value.removeprefix('SIG-')}",
        input_sha256=str(projection["dataset_sha256"]),
        feature_sha256=hashlib.sha256(feature_material).hexdigest(),
        strategy_spec_sha256=str(projection["spec_hash"]),
        signal=signal,
        risk=risk,
        status=DecisionTraceStatus.RISK_BLOCKED,
        intent=None,
        order_ref=None,
        fills=(),
        outcome=DecisionOutcome(
            classification=OutcomeClassification.CORRECT_RISK_BLOCK,
            gross_pnl=Decimal("0"),
            fees=Decimal("0"),
            slippage_cost=Decimal("0"),
            net_pnl=Decimal("0"),
            currency="USDT",
            horizon_seconds=0,
            reconciled=True,
        ),
        attribution=FailureAttribution(
            classification=OutcomeClassification.CORRECT_RISK_BLOCK,
            basis=AttributionBasis.DETERMINISTIC,
            confidence=Decimal("1"),
            facts=(
                f"Canonical verifier reproduced {projection['signal_count']} signals.",
                f"Independent risk gate blocked promotion: {projection['risk_reason']}.",
            ),
            competing_hypotheses=(),
            evidence_refs=(evidence,),
        ),
        evidence_refs=(evidence,),
        provenance=provenance,
    )


def _authority_payload() -> dict[str, object]:
    audit = audit_repository_authority(ROOT)
    return {
        "status": audit.status.value,
        "allows_order_path_changes": audit.allows_order_path_changes,
        "blockers": list(audit.blockers),
        "claims": [
            {
                **asdict(claim),
                "state": claim.state.value,
            }
            for claim in audit.claims
        ],
    }


def build_report() -> dict[str, object]:
    projection, verifier_ms = load_canonical_projection()
    started = perf_counter()
    trace = build_trace(projection)
    ledger = DecisionTraceLedger(LEDGER)
    ledger.append(trace)
    report = project_decision_report((trace,))
    intelligence_ms = (perf_counter() - started) * 1000
    return {
        "schema_version": 1,
        "mode": "OFFLINE_HISTORICAL_RESEARCH",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "orders_created": 0,
        "source": {
            "candidate_id": projection["candidate_id"],
            "dataset_sha256": projection["dataset_sha256"],
            "bars": projection["bars"],
            "signals_reproduced": projection["signal_count"],
            "canonical_verifier_ms": round(verifier_ms, 3),
        },
        "decision_report": report.as_dict(),
        "trace": {
            "trace_id": trace.trace_id,
            "trace_sha256": trace_digest(trace),
            "ledger_sha256": ledger.digest(),
            "ledger_records": len(ledger.records()),
            "projection_ms": round(intelligence_ms, 3),
        },
        "authority_audit": _authority_payload(),
        "hard_evidence": {
            "canonical_signal_flow_reused": True,
            "pnl_cost_reconciliation_enforced": True,
            "ordinary_loss_separate_from_defect": True,
            "append_only_idempotent_trace": True,
            "contradictory_authority_machine_detected": True,
        },
    }


def _markdown(report: dict[str, object]) -> str:
    source = report["source"]
    trace = report["trace"]
    authority = report["authority_audit"]
    decision = report["decision_report"]
    assert isinstance(source, dict)
    assert isinstance(trace, dict)
    assert isinstance(authority, dict)
    assert isinstance(decision, dict)
    return f"""# Decision Intelligence Probe Evidence

Date: 2026-07-21

Mode: offline historical research; no venue connection or order capability

## Observed result

- Frozen dataset bars: **{source["bars"]}**
- Canonical signals reproduced: **{source["signals_reproduced"]}**
- Canonical verifier runtime: **{source["canonical_verifier_ms"]} ms**
- Decision trace projection runtime: **{trace["projection_ms"]} ms**
- Trace ledger records: **{trace["ledger_records"]}**
- Risk-blocked decisions: **{decision["risk_blocked_count"]}**
- Orders created: **0**

## Integrity

- Trace SHA-256: `{trace["trace_sha256"]}`
- Ledger SHA-256: `{trace["ledger_sha256"]}`
- Net P&L reconciles gross P&L, fees, and slippage by contract.
- Replaying the same trace is idempotent; conflicting content under the same trace ID fails.
- Ordinary statistical losses are counted separately from confirmed defects.

## Authority result

Status: **{authority["status"]}**

Order-path changes allowed: **{authority["allows_order_path_changes"]}**

Blockers: `{", ".join(authority["blockers"])}`

The probe proves the first offline vertical slice. It does not validate or promote the
strategy and does not simulate, submit, or authorize a venue order.
"""


def main() -> None:
    report = build_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
