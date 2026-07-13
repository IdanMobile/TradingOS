#!/usr/bin/env python3
"""Carry robustness sweep: per-regime walk-forward + counterparty-haircut stress.

The basis-aware carry survives basis risk and realistic execution (net ~8.4%/yr). Before
that number reaches a human S3/S4 decision, its worst case must be bounded, not just its
average. This does two honest things on the SAME realistic-execution P&L:

  1. WALK-FORWARD BY REGIME: split the per-period carry return by calendar year and by
     market regime (2021 bull / 2022 bear / 2023-26 recovery-chop) and report each segment
     standalone. A carry that only works in one regime is not an all-weather edge.
  2. COUNTERPARTY-HAIRCUT STRESS: the dominant unmodelled risk is exchange insolvency (the
     actual 2022 killer). Model a one-shot haircut of X% of deployed equity and report the
     terminal loss and how many years of carry it takes to recover. A 100% haircut is
     unrecoverable — that is the whole reason venue choice is an operator decision.

RESEARCH-ONLY; execution_authority=NONE; no venue, no orders. Float math for statistics.

ponytail: reuses the S3 realistic-execution carry_walk + fcb.build_matrix/_metrics; the only
new code is calendar bucketing and a linear haircut model. No new strategy, no new data.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_funding_carry_basis as fcb  # noqa: E402
import scripts.run_funding_carry_s3_paper as cp  # noqa: E402

OUT = ROOT / "artifacts" / "validation" / "funding_carry_robustness"
HAIRCUTS = (0.10, 0.25, 0.50, 1.00)  # one-shot counterparty loss on deployed equity
REGIMES = {
    "2021_bull": (2021,),
    "2022_bear": (2022,),
    "2023_26_recovery_chop": (2023, 2024, 2025, 2026),
}


def _period_year(period_index: int) -> int:
    """8h period index -> calendar year (period 0 = epoch)."""
    epoch_seconds = period_index * (fcb.EIGHT_H_MS / 1000)
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).year


def bucket_by_year(periods: list[int], strat: list[float]) -> dict[int, list[float]]:
    buckets: dict[int, list[float]] = {}
    for t, p in enumerate(periods):
        buckets.setdefault(_period_year(p), []).append(strat[t])
    return buckets


def _segment_metrics(returns: list[float]) -> dict:
    """fcb._metrics restricted to the fields that make sense per-segment."""
    m = fcb._metrics(returns)
    positive = sum(1 for r in returns if r > 0)
    return {
        "periods": m["bars"],
        "ann_return_pct": m["ann_return_pct"],
        "total_return_pct": m["total_return_pct"],
        "max_drawdown_pct": m["max_drawdown_pct"],
        "sharpe_ann": m["sharpe_ann"],
        "positive_period_pct": round(100 * positive / len(returns), 1) if returns else 0.0,
    }


def counterparty_stress(full_total_return_pct: float, ann_return_pct: float) -> list[dict]:
    """One-shot haircut of the deployed equity; terminal loss + carry-years to recover."""
    terminal = 1.0 + full_total_return_pct / 100.0
    rows = []
    for h in HAIRCUTS:
        after = terminal * (1.0 - h)
        loss_pct = round((after / terminal - 1.0) * 100, 1)  # == -h*100
        if h >= 1.0 or ann_return_pct <= 0:
            recover = "UNRECOVERABLE"
        else:
            # years of compounding carry to climb back from a (1-h) multiplier.
            years = 0.0
            eq = 1.0 - h
            while eq < 1.0 and years < 1000:
                eq *= 1.0 + ann_return_pct / 100.0
                years += 1
            recover = f"~{years:.0f} yr"
        rows.append(
            {"haircut_pct": round(h * 100, 1), "terminal_loss_pct": loss_pct, "recover": recover}
        )
    return rows


def build_report() -> dict:
    periods, data = fcb.build_matrix()
    cfg = cp.select_best(data)
    strat, fee_frac, toggles = cp.carry_walk(data, *cfg, cp.PAPER_TOGGLE_COST)
    full = fcb._metrics(strat)

    by_year = bucket_by_year(periods, strat)
    per_year = {str(y): _segment_metrics(r) for y, r in sorted(by_year.items())}
    per_regime = {
        name: _segment_metrics([r for y in years for r in by_year.get(y, [])])
        for name, years in REGIMES.items()
    }

    stress = counterparty_stress(full["total_return_pct"], full["ann_return_pct"])
    worst_year = min(per_year.items(), key=lambda kv: kv[1]["ann_return_pct"])
    all_weather = all(m["ann_return_pct"] > 0 for m in per_regime.values())

    verdict = (
        f"Realistic-execution carry is {'ALL-WEATHER' if all_weather else 'REGIME-DEPENDENT'}: "
        + ", ".join(f"{n} {m['ann_return_pct']}%/yr" for n, m in per_regime.items())
        + f". Worst calendar year: {worst_year[0]} at {worst_year[1]['ann_return_pct']}%/yr "
        f"(maxDD {worst_year[1]['max_drawdown_pct']}%). The binding risk is NOT market regime "
        "but COUNTERPARTY: a full exchange default is unrecoverable at any carry rate, so venue "
        "selection + collateral custody is the operator decision that dominates — not the "
        "backtest. Diversify venues and cap per-venue equity accordingly."
    )

    return {
        "schema": "tios-funding-carry-robustness-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "tradeability": "RESEARCH_ONLY — perps/margin S4-gated; counterparty risk operator-owned",
        "config": {"threshold": cfg[0], "lookback": cfg[1], "rebalance": cfg[2]},
        "basis": "realistic per-leg execution (spot+perp, taker+slippage) from the S3 paper probe",
        "full_period": {
            "periods_8h": full["bars"],
            "ann_return_pct": full["ann_return_pct"],
            "total_return_pct": full["total_return_pct"],
            "max_drawdown_pct": full["max_drawdown_pct"],
            "sharpe_ann": full["sharpe_ann"],
            "leg_toggles": toggles,
        },
        "per_year": per_year,
        "per_regime": per_regime,
        "counterparty_stress": stress,
        "all_weather": all_weather,
        "verdict": verdict,
        "operator_note": "Gates unchanged: this is evidence for a HUMAN S3/S4 decision, not an "
        "activation. execution_authority=NONE; no venue, no orders, no credentials.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "FUNDING_CARRY_ROBUSTNESS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    f = report["full_period"]
    print(
        f"config {report['config']}  full: ann {f['ann_return_pct']}% maxDD "
        f"{f['max_drawdown_pct']}% Sharpe {f['sharpe_ann']}"
    )
    print("per-regime:")
    for name, m in report["per_regime"].items():
        print(
            f"  {name:<24} ann {m['ann_return_pct']:>6}%  maxDD {m['max_drawdown_pct']:>6}%  "
            f"pos-periods {m['positive_period_pct']}%"
        )
    print("counterparty haircut stress:")
    for row in report["counterparty_stress"]:
        print(
            f"  -{row['haircut_pct']:>5}% equity -> terminal {row['terminal_loss_pct']}%  "
            f"recover {row['recover']}"
        )
    print(report["verdict"])


if __name__ == "__main__":
    main()
