#!/usr/bin/env python3
"""Attribute retained B2 development/validation/holdout losses without tuning."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.services.reporting import (  # noqa: E402
    BacktestValidationEvidence,
    HistoricalTradeTraceLedger,
    analyze_long_only_roundtrips,
    build_historical_trade_traces,
    diagnose_backtest_failure,
)
from tios.trading_domain import DomainRef  # noqa: E402

BASE = ROOT / "artifacts/validation/B2_F0_S0"
REPORT_JSON = ROOT / "artifacts/reports/B2_REAL_LOSS_ATTRIBUTION_2026_07_21.json"
REPORT_MD = ROOT / "artifacts/reports/B2_REAL_LOSS_ATTRIBUTION_2026_07_21.md"
TRACE_LEDGER = ROOT / "artifacts/evidence/B2_HISTORICAL_TRADE_TRACES_2026_07_21.jsonl"
STRATEGY_VERSION = DomainRef("SV-d807f4a811312a74d73ddcf955078a78")
STRATEGY_SPEC_SHA256 = "d807f4a811312a74d73ddcf955078a7846ad18fab3006b996c2fa45be318f5e0"


def build_report() -> dict[str, object]:
    reports = tuple(
        analyze_long_only_roundtrips(
            BASE / f"runs/{label}/trades.parquet",
            label=label.upper(),
        )
        for label in ("development", "validation", "holdout")
    )
    validation = json.loads((BASE / "validation_summary.json").read_text(encoding="utf-8"))
    gates = validation["gates"]
    metrics = validation["metrics"]
    evidence = BacktestValidationEvidence(
        input_integrity_passed=all(gates[gate]["status"] == "PASS" for gate in ("G1", "G2")),
        fee_audit_passed=metrics["fee_audit"]["status"] == "PASS",
        walk_forward_positive_windows=(
            0 if "zero positive windows" in gates["G7"]["reason"] else None
        ),
        neighboring_positive_variants=(
            0 if "all remain negative" in gates["G8"]["reason"] else None
        ),
        benchmark_outperformed=False if "underperforms" in gates["G11"]["reason"] else None,
    )
    diagnosis = diagnose_backtest_failure(reports, evidence)
    traces = tuple(
        trace
        for split_report in reports
        for trace in build_historical_trade_traces(
            split_report,
            strategy_version_ref=STRATEGY_VERSION,
            strategy_spec_sha256=STRATEGY_SPEC_SHA256,
            evidence_refs=(
                DomainRef(f"EV-B2-{split_report.label}-TRADES"),
                DomainRef("EV-B2-VALIDATION-SUMMARY"),
            ),
        )
    )
    ledger = HistoricalTradeTraceLedger(TRACE_LEDGER)
    trace_digests = ledger.append_many(traces)
    if len(ledger.records()) != len(traces):
        raise RuntimeError("historical learning ledger does not match retained round trips")
    total_gross = sum((report.gross_pnl for report in reports), start=Decimal("0"))
    total_fees = sum((report.fees for report in reports), start=Decimal("0"))
    total_net = sum((report.net_pnl for report in reports), start=Decimal("0"))
    return {
        "schema_version": 1,
        "mode": "OFFLINE_RETAINED_BACKTEST_ATTRIBUTION",
        "strategy": validation["strategy"],
        "strategy_version_ref": str(STRATEGY_VERSION),
        "strategy_spec_sha256": STRATEGY_SPEC_SHA256,
        "source_status": validation["status"],
        "splits": [report.as_dict() for report in reports],
        "aggregate": {
            "roundtrips": sum(report.roundtrip_count for report in reports),
            "profitable": sum(report.profitable_count for report in reports),
            "ordinary_losses": sum(report.ordinary_loss_count for report in reports),
            "breakeven": sum(report.breakeven_count for report in reports),
            "cost_flipped_losses": sum(report.cost_flipped_loss_count for report in reports),
            "gross_pnl": str(total_gross),
            "fees": str(total_fees),
            "net_pnl": str(total_net),
        },
        "diagnosis": {
            "classification": diagnosis.classification.value,
            "recommendation": diagnosis.recommendation.value,
            "facts": list(diagnosis.facts),
            "creates_strategy_version": diagnosis.creates_strategy_version,
            "promotion_eligible": diagnosis.promotion_eligible,
        },
        "learning_ledger": {
            "path": str(TRACE_LEDGER.relative_to(ROOT)),
            "trace_count": len(traces),
            "unique_trace_digests": len(set(trace_digests)),
            "ledger_sha256": ledger.digest(),
            "idempotent_replay": ledger.append_many(traces) == trace_digests,
            "signal_history_reconstructed": False,
            "risk_history_reconstructed": False,
        },
        "counterfactuals": {
            "zero_fee_net_pnl": str(total_gross),
            "no_trade_net_pnl": "0",
            "loss_avoided_by_rejection": str(-total_net),
            "status": "DIAGNOSTIC_ONLY_NOT_A_STRATEGY_RESULT",
        },
        "execution_authority": "NONE",
        "orders_created": 0,
    }


def _markdown(report: dict[str, object]) -> str:
    aggregate = report["aggregate"]
    diagnosis = report["diagnosis"]
    counterfactuals = report["counterfactuals"]
    assert isinstance(aggregate, dict)
    assert isinstance(diagnosis, dict)
    assert isinstance(counterfactuals, dict)
    result_counts = (
        f"{aggregate['profitable']} / {aggregate['ordinary_losses']} / {aggregate['breakeven']}"
    )
    return f"""# B2 Real Loss Attribution

Date: 2026-07-21

Mode: retained offline backtest evidence; no tuning, holdout access expansion, or orders

## Hard evidence

- Round trips analyzed: **{aggregate["roundtrips"]}**
- Profitable / losing / breakeven: **{result_counts}**
- Gross P&L: **{aggregate["gross_pnl"]} USDT**
- Recorded fees: **{aggregate["fees"]} USDT**
- Net P&L: **{aggregate["net_pnl"]} USDT**
- Gross-positive trades turned negative by fees: **{aggregate["cost_flipped_losses"]}**

Classification: **{diagnosis["classification"]}**

Recommendation: **{diagnosis["recommendation"]}**

The zero-fee aggregate remains **{counterfactuals["zero_fee_net_pnl"]} USDT**, so fees are
severe but do not rescue the underlying development/holdout weakness. Existing validation
also records zero positive walk-forward windows, all neighboring variants negative, and
benchmark underperformance. The correct improvement is rejection, not a post-hoc V2.

The no-trade counterfactual avoids **{counterfactuals["loss_avoided_by_rejection"]} USDT**
of modeled loss, but it is diagnostic only and is not reported as trading profit.
"""


def main() -> None:
    report = build_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
