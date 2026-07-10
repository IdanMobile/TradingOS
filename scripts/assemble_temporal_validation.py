"""Assemble executed chronological B2 validation evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "validation" / "B2_F0_S0"
WINDOWS = {
    "development": "2021-01-01T00:00:00+00:00 → 2024-04-19T04:45:00+00:00",
    "validation": "2024-04-19T04:45:00.000001+00:00 → 2025-05-25T14:20:00+00:00",
    "holdout": "2025-05-25T14:20:00.000001+00:00 → 2026-06-30T23:55:00+00:00",
}


def main() -> None:
    results = {}
    for window, coverage in WINDOWS.items():
        metrics = json.loads((BASE / "runs" / window / "normalized_metrics.json").read_text())
        results[window] = {
            "coverage": coverage,
            "roundtrips": metrics["trades_roundtrips"],
            "fills": metrics["fills"],
            "profit_total_abs": metrics["profit_total_abs"],
            "fee_audit": metrics["fee_audit"],
            "artifact": str((BASE / "runs" / window).relative_to(ROOT)),
        }
    payload = {
        "status": "COMPLETE_ENGINE_RUNS",
        "strategy": "B2MaCrossover",
        "dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "engine": "freqtrade",
        "scenario": "F1/S1",
        "fixed_parameters": {"stake_amount": "1000", "max_open_trades": 1, "fee_per_side": "0.001"},
        "windows": results,
        "holdout_touched_before_optimization": False,
        "interpretation": (
            "B2 is negative in development, validation, and untouched holdout; no survivor claim."
        ),
    }
    (BASE / "oos_report.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {BASE / 'oos_report.json'}")


if __name__ == "__main__":
    main()
