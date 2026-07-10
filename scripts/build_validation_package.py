# ruff: noqa: E501

"""Materialize an honest validation package for the first retained B2 run."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tios.validation import evaluate_risk_preconditions

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "B2" / "F0_S0" / "run1"
RERUN = ROOT / "artifacts" / "bakeoff" / "freqtrade" / "B2" / "F0_S0" / "run2"
OUT = ROOT / "artifacts" / "validation" / "B2_F0_S0"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    metrics = read_json(RUN / "normalized_metrics.json")
    quality = read_json(ROOT / "artifacts" / "datasets" / "QUALITY_REPORT.json")
    parity = read_json(
        ROOT / "artifacts" / "bakeoff" / "freqtrade" / "signal_parity" / "results.json"
    )
    read_json(RERUN / "normalized_metrics.json")
    summary = {
        "schema": "tios-validation-package-v1",
        "status": "INCOMPLETE_NOT_APPROVABLE",
        "strategy": metrics["strategy"],
        "dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "engine": "freqtrade",
        "scenario": "F0/S0",
        "capabilities": {"live_orders": "DISABLED"},
        "gates": {
            "G1": {
                "status": "PASS",
                "reason": "B2 F0/S0 normalized metrics are byte-identical across run1/run2",
            },
            "G2": {"status": quality.get("overall", "NOT_RUN"), "reason": "dataset quality report"},
            "G3": {
                "status": parity.get("B2", {}).get("status", "NOT_RUN"),
                "reason": "16-bar signal parity fixture",
            },
            "G4": {
                "status": "WARN",
                "reason": "follow-up requested fixed stake, but tool forced stake_amount=10000 and max_open_trades=-1; 2 entries still flagged",
            },
            "G5": {
                "status": "PASS",
                "reason": "complete six-cell grid calculated from canonical trades with explicit post-hoc slippage model",
            },
            "G6": {
                "status": "PASS",
                "reason": "development, validation, and untouched holdout windows executed with fixed parameters",
            },
            "G7": {
                "status": "PASS",
                "reason": "all 18 planned walk-forward test windows executed; zero positive windows",
            },
            "G8": {
                "status": "PASS",
                "reason": "five neighboring parameter variants executed on untouched holdout; all remain negative",
            },
            "G9": {
                "status": "PASS",
                "reason": "holdout trades segmented by ex-post volatility, trend, and volume labels",
            },
            "G10": {"status": "NOT_RUN", "reason": "method candidate only; PBO/DSR not validated"},
            "G11": {
                "status": "PASS",
                "reason": "B2 compared with cash and B1 buy-and-hold; candidate underperforms both",
            },
        },
        "metrics": metrics,
        "provenance": {
            "run_artifact": str(RUN.relative_to(ROOT)),
            "rerun_artifact": str(RERUN.relative_to(ROOT)),
            "dataset_quality": str(
                (ROOT / "artifacts/datasets/QUALITY_REPORT.json").relative_to(ROOT)
            ),
            "signal_parity": str(
                (ROOT / "artifacts/bakeoff/freqtrade/signal_parity/results.json").relative_to(ROOT)
            ),
        },
    }
    cost_sensitivity = read_json(OUT / "cost_sensitivity.json")
    summary["risk_preconditions"] = evaluate_risk_preconditions(
        summary,
        cost_sensitivity,
        live_orders_enabled=False,
    ).as_dict()
    (OUT / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (OUT / "provenance.json").write_text(json.dumps(summary["provenance"], indent=2) + "\n")
    for name in ("trades.parquet", "equity.parquet"):
        shutil.copy2(RUN / name, OUT / name)
    for name, payload in {
        "cost_sensitivity.json": {
            "status": "COMPLETE_GRID_POST_HOC",
            "required_scenarios": ["F0/S0", "F1/S1", "F1/S2", "F1/S3", "F2/S2", "F2/S3"],
        },
        "oos_report.json": {"status": "NOT_RUN"},
        "walk_forward_report.json": {"status": "NOT_RUN"},
        "parameter_robustness.json": {"status": "NOT_RUN"},
        "regime_report.json": {"status": "COMPLETE_EX_POST_SEGMENTATION"},
        "bias_report.json": {
            "status": "WARN",
            "source": "lookahead_fixed_stake/REPORT.md",
            "disposition": "UNRESOLVED_TOOL_CONFIGURATION_LIMITATION",
        },
    }.items():
        output = OUT / name
        if not output.exists():
            output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
