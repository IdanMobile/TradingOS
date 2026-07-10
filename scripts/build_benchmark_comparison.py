"""Compare the B2 validation artifact with retained simple baselines."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation" / "B2_F0_S0" / "baseline_comparison.json"


def metric(path: Path) -> float:
    return float(json.loads(path.read_text())["profit_total_abs"])


def main() -> None:
    candidate = metric(ROOT / "artifacts/bakeoff/freqtrade/B2/F0_S0/run1/normalized_metrics.json")
    buy_hold = metric(ROOT / "artifacts/bakeoff/freqtrade/B1/F0_S0/run1/normalized_metrics.json")
    data = {
        "status": "COMPLETE",
        "candidate": {"id": "B2MaCrossover", "profit_total_abs": candidate},
        "baselines": {
            "cash_no_trade": {"profit_total_abs": 0.0},
            "B1BuyAndHold": {"profit_total_abs": buy_hold},
        },
        "candidate_beats_cash": candidate > 0,
        "candidate_beats_buy_and_hold": candidate > buy_hold,
        "interpretation": (
            "B2 underperforms both cash and B1 buy-and-hold in this retained F0/S0 run."
        ),
        "approval_effect": "negative evidence; no promotion claim",
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
