#!/usr/bin/env python3
"""Funding-regime deploy filter for the carry — attacking the 2022-style bleed.

The robustness sweep found realistic-execution carry is regime-dependent: +42.6%/yr in the
2021 bull but −3.8%/yr in the 2022 bear. This adds a CAUSAL basket-level deploy gate on top of
the existing per-pair selection: only carry when the whole universe's trailing funding regime
is favorable; otherwise stand flat in cash (earn 0, take no basis risk). No lookahead — the
gate at period t uses only funding through t−1.

Honest question this answers: does standing down in weak-funding regimes improve the bear
outcome and the DSR without curve-fitting? The gate is a single trailing-mean threshold, not a
date filter, so it cannot "know" 2022 — it can only react to funding it has already seen. The
report shows gated-vs-ungated per regime; if it does not help out-of-regime, that is stated.

RESEARCH-ONLY; execution_authority=NONE; no venue, no orders. Float math for statistics.

ponytail: reuses cp.carry_walk's exact selection/fee logic + rob's calendar bucketing; the only
new physics is the universe-funding deploy gate, which collapses to the base walk when always-on.
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_funding_carry_basis as fcb  # noqa: E402
import scripts.run_funding_carry_robustness as rob  # noqa: E402
import scripts.run_funding_carry_s3_paper as cp  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "validation" / "funding_carry_regime_filter"
DSR_PASS = 0.95
DEPLOY_LOOKBACKS = (21, 63)  # 8h periods for the universe-regime trailing window (~1wk, ~3wk)
DEPLOY_THRESHOLDS = (0.0, 0.00003)  # min trailing universe mean funding to deploy (per 8h)


def regime_gated_walk(
    data: dict[str, dict[str, list[float | None]]],
    threshold: float,
    lookback: int,
    rebalance: int,
    toggle_cost: float,
    deploy_lookback: int,
    deploy_threshold: float,
) -> list[float]:
    """cp.carry_walk with a causal universe-funding deploy gate. deploy_threshold=-1.0 and
    deploy_lookback=1 reproduce the ungated base walk (asserted in tests)."""
    pairs = list(data)
    n = len(next(iter(data.values()))["fund"])
    held: set[str] = set()
    deployed = False
    strat = [0.0] * n
    for t in range(1, n):
        if held and deployed:
            got = [r for p in held if (r := fcb._carry_return(data[p], t)) is not None]
            strat[t] = sum(got) / len(got) if got else 0.0
        if t >= max(lookback, deploy_lookback) and t % rebalance == 0:
            regime = [
                data[p]["fund"][t - k]
                for p in pairs
                for k in range(deploy_lookback)
                if data[p]["fund"][t - k] is not None
            ]
            deployed = bool(regime) and mean(regime) > deploy_threshold
            new: set[str] = set()
            if deployed:
                for p in pairs:
                    w = [
                        data[p]["fund"][t - k]
                        for k in range(lookback)
                        if data[p]["fund"][t - k] is not None
                    ]
                    if w and mean(w) > threshold:
                        new.add(p)
            if new != held:
                strat[t] -= toggle_cost * len(new ^ held) / max(len(new | held), 1)
            held = new
    return strat


def _dsr(returns: list[float], sharpes: list[float], trials: int, bars: int) -> float:
    mr, sd = mean(returns), pstdev(returns)
    skew = (sum((r - mr) ** 3 for r in returns) / len(returns)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in returns) / len(returns)) / sd**4 if sd > 0 else 3.0
    return deflated_sharpe_ratio(
        observed_sharpe=mean(returns) / sd if sd > 0 else 0.0,
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=trials,
        sample_count=bars,
        skewness=skew,
        kurtosis=kurt,
    )["dsr"]


def build_report() -> dict:
    periods, data = fcb.build_matrix()
    threshold, lookback, rebalance = cp.select_best(data)

    ungated, _, _ = cp.carry_walk(data, threshold, lookback, rebalance, cp.PAPER_TOGGLE_COST)
    ungated_regime = {
        name: rob._segment_metrics(
            [r for y in years for r in rob.bucket_by_year(periods, ungated).get(y, [])]
        )
        for name, years in rob.REGIMES.items()
    }

    trials = []
    for deploy_lookback, deploy_threshold in product(DEPLOY_LOOKBACKS, DEPLOY_THRESHOLDS):
        strat = regime_gated_walk(
            data,
            threshold,
            lookback,
            rebalance,
            cp.PAPER_TOGGLE_COST,
            deploy_lookback,
            deploy_threshold,
        )
        m = fcb._metrics(strat)
        m.update(deploy_lookback=deploy_lookback, deploy_threshold=deploy_threshold, returns=strat)
        trials.append(m)

    sharpes = [t["sharpe_bar"] for t in trials]
    best = max(trials, key=lambda t: t["sharpe_bar"])
    by_year = rob.bucket_by_year(periods, best["returns"])
    gated_regime = {
        name: rob._segment_metrics([r for y in years for r in by_year.get(y, [])])
        for name, years in rob.REGIMES.items()
    }
    dsr = _dsr(best["returns"], sharpes, len(trials), best["bars"])

    ungated_m = fcb._metrics(ungated)
    bear_before = ungated_regime["2022_bear"]["ann_return_pct"]
    bear_after = gated_regime["2022_bear"]["ann_return_pct"]
    helped = bear_after > bear_before
    keys = ("deploy_lookback", "deploy_threshold", "sharpe_ann", "ann_return_pct",
            "max_drawdown_pct", "total_return_pct")  # fmt: skip
    return {
        "schema": "tios-funding-carry-regime-filter-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "base_config": {"threshold": threshold, "lookback": lookback, "rebalance": rebalance},
        "ungated": {
            "ann_return_pct": ungated_m["ann_return_pct"],
            "max_drawdown_pct": ungated_m["max_drawdown_pct"],
            "sharpe_ann": ungated_m["sharpe_ann"],
            "per_regime": ungated_regime,
        },
        "best_gated": {k: best[k] for k in keys},
        "gated_per_regime": gated_regime,
        "g10_dsr": {
            "dsr": round(dsr, 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr >= DSR_PASS else "FAIL",
            "verdict_is_genuine": False,
            "note": "Same off-sample counterparty caveat as the base carry — DSR cannot see the "
            "venue tail. The gate is a causal risk overlay, evaluated honestly per regime.",
        },
        "bear_regime_improved": helped,
        "verdict": (
            f"Regime filter changes 2022 bear from {bear_before}%/yr to {bear_after}%/yr and "
            f"full-period from {ungated_m['ann_return_pct']}% to {best['ann_return_pct']}%. "
            + (
                "The causal universe-funding gate reduces the bear bleed — a genuine risk "
                "improvement, not a date filter."
                if helped
                else "The causal gate does NOT rescue the bear regime (funding weakness is "
                "coincident, not leading) — carry's regime-dependence is intrinsic; do not "
                "over-trust the gate."
            )
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "FUNDING_CARRY_REGIME_FILTER.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    u, b = report["ungated"], report["best_gated"]
    print(f"base config {report['base_config']}")
    print(
        f"ungated:     ann {u['ann_return_pct']}%  "
        f"bear {u['per_regime']['2022_bear']['ann_return_pct']}%"
    )
    print(
        f"best gated:  ann {b['ann_return_pct']}%  bear "
        f"{report['gated_per_regime']['2022_bear']['ann_return_pct']}%  "
        f"(dl={b['deploy_lookback']} dt={b['deploy_threshold']})"
    )
    print(
        f"G10 DSR: {report['g10_dsr']['dsr']} -> {report['g10_dsr']['verdict']} "
        f"(genuine={report['g10_dsr']['verdict_is_genuine']})"
    )
    print(report["verdict"])


if __name__ == "__main__":
    main()
