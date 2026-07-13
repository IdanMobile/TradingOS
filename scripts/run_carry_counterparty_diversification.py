#!/usr/bin/env python3
"""Counterparty-diversification model for the funding carry — bounding the −100% tail.

The robustness sweep found the carry's binding risk is not market regime but COUNTERPARTY:
a single-venue exchange default is an unrecoverable −100% event (FTX/LUNA 2022). This models
the one structural mitigation that exists: split capital across K venues, each capped at 1/K,
so a single default costs 1/K (recoverable) instead of everything, and a total wipeout needs
all K to fail at once (probability p**K under independence).

Key honest result the operator needs: diversification does NOT reduce the *expected* annual
counterparty drag (~p regardless of K) — it converts an unrecoverable catastrophe into a
bounded, survivable loss. That is exactly why HG-4 (which venues, how many accounts) is the
decision that dominates carry's real-world viability, not the backtest number.

Assumptions (stated, not hidden): venue defaults are independent, one-shot, total-per-venue,
with an annual per-venue probability p (a parameter — pick it from operator due diligence, not
this script). RESEARCH-ONLY; execution_authority=NONE; no venue, no orders.

ponytail: pure capital-structure arithmetic over the realized carry ann return; no new data.
The carry ann return is injectable so the model is testable without loading the basis matrix.
"""

from __future__ import annotations

import json
import sys
from math import log
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "artifacts" / "validation" / "carry_counterparty_diversification"
VENUE_COUNTS = (1, 2, 3, 4, 5)
DEFAULT_PROBS = (0.02, 0.05, 0.10)  # per-venue annual default probability (illustrative)


def realized_carry_ann_pct() -> float:
    """Realistic-execution carry annual return from the S3 paper walk (single source)."""
    import scripts.run_funding_carry_basis as fcb
    import scripts.run_funding_carry_s3_paper as cp

    _, data = fcb.build_matrix()
    cfg = cp.select_best(data)
    strat, _, _ = cp.carry_walk(data, *cfg, cp.PAPER_TOGGLE_COST)
    return fcb._metrics(strat)["ann_return_pct"]


def years_to_recover(loss_fraction: float, ann_return_pct: float) -> float | str:
    """Years of compounding carry to climb back from a (1-loss) multiplier."""
    if loss_fraction >= 1.0 or ann_return_pct <= 0:
        return "UNRECOVERABLE"
    growth = 1.0 + ann_return_pct / 100.0
    # (1-loss) * growth**y >= 1  ->  y >= -ln(1-loss)/ln(growth)
    return round(-log(1.0 - loss_fraction) / log(growth), 1)


def diversification_row(k: int, p: float, ann_return_pct: float) -> dict:
    """Structural outcome of splitting capital across k venues, each defaulting w.p. p."""
    per_venue = 1.0 / k
    expected_drag_pct = round(p * 100, 2)  # E[loss] = k * p * (1/k) = p, independent of k
    single_default_loss_pct = round(per_venue * 100, 1)
    total_wipeout_prob = p**k
    net_expected_ann_pct = round((1 + ann_return_pct / 100) * (1 - p) * 100 - 100, 2)
    return {
        "venues": k,
        "per_venue_cap_pct": round(per_venue * 100, 1),
        "expected_annual_counterparty_drag_pct": expected_drag_pct,
        "single_default_loss_pct": single_default_loss_pct,
        "single_default_recover_years": years_to_recover(per_venue, ann_return_pct),
        "all_venues_default_prob": total_wipeout_prob,
        "all_venues_default_is_unrecoverable": True,
        "net_expected_ann_return_pct": net_expected_ann_pct,
    }


def build_report(ann_return_pct: float | None = None) -> dict:
    ann = realized_carry_ann_pct() if ann_return_pct is None else ann_return_pct
    grid = {f"p={p}": [diversification_row(k, p, ann) for k in VENUE_COUNTS] for p in DEFAULT_PROBS}
    return {
        "schema": "tios-carry-counterparty-diversification-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "carry_ann_return_pct": ann,
        "assumptions": {
            "default_model": "independent, one-shot, total-loss-per-venue",
            "per_venue_annual_default_prob": list(DEFAULT_PROBS),
            "note": "p is an operator due-diligence input, NOT estimated here. Correlated "
            "defaults (a systemic crypto event) violate independence and are a residual risk "
            "no allocation removes — only capital sizing does.",
        },
        "grid": grid,
        "verdict": (
            "Single-venue carry (K=1) carries an UNRECOVERABLE −100% counterparty tail at "
            "probability p. Splitting across K venues with per-venue caps leaves the expected "
            "drag unchanged (~p) but converts the catastrophe into a bounded 1/K loss that "
            "carry can recover from, and shrinks total wipeout to p**K. Therefore the "
            "real-world go/no-go is an HG-4 decision — how many independent venues, which ones, "
            "and per-venue capital caps — not a backtest metric. Correlated (systemic) default "
            "is the residual only position sizing (HG-4 item 8) can bound."
        ),
        "operator_note": "Feeds HG-4 (venue count/selection) and HG-5 (capital + max drawdown). "
        "No venue, no orders, no credentials; execution_authority=NONE.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "CARRY_COUNTERPARTY_DIVERSIFICATION.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"carry ann: {report['carry_ann_return_pct']}%")
    for p in DEFAULT_PROBS:
        print(f"per-venue default p={p}:")
        for row in report["grid"][f"p={p}"]:
            print(
                f"  K={row['venues']}  cap {row['per_venue_cap_pct']}%  "
                f"1-default loss {row['single_default_loss_pct']}% "
                f"(recover {row['single_default_recover_years']})  "
                f"all-fail p={row['all_venues_default_prob']}  "
                f"net exp ann {row['net_expected_ann_return_pct']}%"
            )
    print(report["verdict"])


if __name__ == "__main__":
    main()
