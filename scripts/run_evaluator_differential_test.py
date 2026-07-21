#!/usr/bin/env python3
"""Differential test of the D-112 campaign evaluator against an independent implementation.

The D-112 remediation fixed the statistical core to trade-level significance (F1: the DSR
was fed the whole validation-bar count while the Sharpe was computed only over in-position
bars, inflating ``z`` by ``1/sqrt(in-position fraction)``). The residual concern the audit
left open is *single-implementation risk*: the evaluator and its significance scorer are
trusted because one code path says so. This script reduces that risk by re-deriving the same
quantities a second, independent way and demanding agreement within tight tolerances.

It is pure offline evaluation. No venue, credential, order, holdout, or ledger path is touched.
It does not change any threshold or verdict; a disagreement is reported as a finding, never
"fixed" here.

Two layers are compared, because the "campaign evaluator D-112 remediated" is really a pair:

* **Layer 1 — the trade-return builder** (``run_first_budgeted_campaign.evaluate``): turns
  OHLC bars + entry/exit rules + the F1/S1 cost model into per-completed-trade P&L,
  bar-aligned P&L, and a descriptive per-bar Sharpe. Compared against
  :func:`independent_evaluate` (a from-spec pure-stdlib re-implementation) and, where
  installed, vectorbt (the repo's accelerator, engine-env only) for trade count and
  aggregate P&L.

* **Layer 2 — the significance scorer** (``tios.validation.campaign.score_trade_significance``):
  the DSR / deflated-significance path with the fail-closed ``sample_count`` identity guard
  that is the actual F1 fix. Compared against :func:`independent_score_trade_significance`
  (a from-spec re-derivation of the Bailey/López de Prado DSR), plus an explicit regression
  that the guard *rejects* the pre-D-112 inflated ``sample_count`` and quantifies the
  inflation it used to let through.

The synthetic fixtures have hand-derivable ground truth: known entry/exit bars and known
fills, so every per-trade return equals a closed form (:func:`expected_trade_return`).

Independence note (this environment): the project's runtime env ships neither numpy nor
vectorbt, so the load-bearing independent implementation is written in the standard library
(``math`` / ``statistics``) from the published formulas — a genuinely separate code path, not
a numpy wrapper around the same one. The vectorbt leg uses only the API surface already
proven in ``engines/vectorbt/g10_returns.py`` and is skipped cleanly when vectorbt is absent.

    python scripts/run_evaluator_differential_test.py            # write the evidence artifact
    python scripts/run_evaluator_differential_test.py --check    # exit non-zero on any mismatch
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from math import e, sqrt
from pathlib import Path
from statistics import NormalDist, mean, pstdev, variance
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_first_budgeted_campaign as fb  # noqa: E402  (project trade-return builder under test)

from tios.validation.campaign import (  # noqa: E402
    CampaignError,
    TrialScore,
    score_trade_significance,
)

ARTIFACT_PATH = ROOT / "artifacts" / "validation" / "EVALUATOR_DIFFERENTIAL_TEST_2026_07_21.json"

# Cost model is a shared *input spec* (D-107 F1/S1), not part of the logic under test, so both
# implementations read the same rates. What is under test is the trade building, counting, and
# significance arithmetic layered on top of these rates.
FEE = fb.FEE_RATE_PER_SIDE
SLIP = fb.SLIPPAGE_RATE_PER_SIDE

# Tight tolerances: two same-machine float paths derived independently should agree to ~1e-15;
# 1e-12 leaves headroom for benign reordering of sums without hiding a real divergence.
PNL_TOL = 1e-12
STAT_TOL = 1e-12

NORMAL = NormalDist()
EULER_GAMMA = 0.5772156649015329

Bar = tuple[float, float, float, float]  # open, high, low, close

# Small, shared parameter set. warmup = max(2,2,2)+1 = 3; the contraction quantile picks the
# 0-th smallest of the prior two ranges, so an entry bar must be narrow-range *and* close above
# the prior two highs (a quiet new-high), which is what the fixtures below construct.
PARAMS: dict[str, Any] = {
    "contraction_window": 2,
    "breakout_window": 2,
    "exit_window": 2,
    "contraction_quantile": 0.2,
}


# --------------------------------------------------------------------------------------------
# Ground truth: closed-form per-trade P&L from the fill opens and the F1/S1 cost model.
# --------------------------------------------------------------------------------------------
def expected_trade_return(entry_fill_open: float, exit_fill_open: float) -> float:
    """The single trade's realised return, hand-derivable from the two fill opens.

    Signals fire on a closed bar and fill at the *next* open with adverse slippage and taker
    fees on both sides: buy at ``open*(1+slip)*(1+fee)``, sell at ``open*(1-slip)*(1-fee)``.
    """
    entry_price = entry_fill_open * (1 + SLIP) * (1 + FEE)
    exit_price = exit_fill_open * (1 - SLIP) * (1 - FEE)
    return exit_price / entry_price - 1


def _bar(o: float, h: float, low: float, c: float) -> Bar:
    return (float(o), float(h), float(low), float(c))


def _calm(level: float = 100.0) -> Bar:
    """A quiet bar (range 2/level) whose close never exceeds prior highs, so it never enters."""
    return _bar(level, level + 1, level - 1, level)


def _trade_block(exit_fill_open: float) -> list[Bar]:
    """One full entry->hold->exit cycle. Entry fills at open 101.5; exit fills at the given open.

    Bar 0 is a narrow-range new high (range 0.3/101.4, below the calm 0.02) closing at 101.4 above
    the prior calm highs of 101 -> entry. Bars 1-2 hold. Bar 3 closes at 99.5 below the prior two
    lows of 101 -> exit. Bar 4 supplies the exit fill open.
    """
    return [
        _bar(100.5, 101.5, 101.2, 101.4),  # ENTRY signal; fills at next open 101.5
        _bar(101.5, 102, 101, 101.5),  # hold (entry fill open)
        _bar(101.5, 102, 101, 101.5),  # hold
        _bar(101, 101, 99, 99.5),  # EXIT signal; fills at next open
        _bar(exit_fill_open, exit_fill_open + 0.5, exit_fill_open - 0.5, exit_fill_open),
    ]


def build_pnl_fixtures() -> list[dict[str, Any]]:
    """Layer-1 OHLC fixtures with hand-derived expected per-trade returns and counts."""
    r_loss = expected_trade_return(101.5, 100.0)
    r_gain = expected_trade_return(101.5, 104.0)
    return [
        {
            "name": "normal_two_trades",
            "description": "Two completed trades with distinct returns (one loss, one gain).",
            "bars": [_calm() for _ in range(5)]
            + _trade_block(100.0)
            + [_calm() for _ in range(4)]
            + _trade_block(104.0)
            + [_calm() for _ in range(6)],
            "expected_trade_returns": [r_loss, r_gain],
        },
        {
            "name": "zero_trades",
            "description": "No entry ever arms (calm never closes above prior highs).",
            "bars": [_calm() for _ in range(30)],
            "expected_trade_returns": [],
        },
        {
            "name": "single_trade",
            "description": "Exactly one completed trade.",
            "bars": [_calm() for _ in range(5)] + _trade_block(100.0) + [_calm() for _ in range(9)],
            "expected_trade_returns": [r_loss],
        },
        {
            "name": "sample_count_inflation_defect",
            "description": (
                "One completed trade over 120 bars (119 bar-returns): the CFTC-shaped geometry "
                "where in-position fraction is tiny. Pre-D-112, feeding the 119-bar count to the "
                "DSR instead of the 1-trade count inflated z; the Layer-2 checks below assert the "
                "fail-closed guard now rejects that substitution."
            ),
            "bars": [_calm() for _ in range(5)]
            + _trade_block(100.0)
            + [_calm() for _ in range(110)],
            "expected_trade_returns": [r_loss],
        },
    ]


# --------------------------------------------------------------------------------------------
# Independent implementation, Layer 1: from-spec pure-stdlib re-derivation of the builder.
# Structured differently from the project code (precompute the arm/exit signals, then walk the
# position state machine) so a shared structural bug is unlikely to survive in both.
# --------------------------------------------------------------------------------------------
def independent_evaluate(window: Sequence[Bar], parameters: dict[str, Any]) -> TrialScore:
    contraction = int(parameters["contraction_window"])
    breakout = int(parameters["breakout_window"])
    exit_window = int(parameters["exit_window"])
    quantile = float(parameters["contraction_quantile"])

    n = len(window)
    warmup = max(contraction, breakout, exit_window) + 1
    bar_returns = [0.0] * max(n - 1, 0)
    if n < warmup + 10:
        return TrialScore(0.0, (), tuple(bar_returns))

    rng = [(bar[1] - bar[2]) / bar[3] if bar[3] else 0.0 for bar in window]

    # Precompute the state-independent signals for every scored bar.
    armed: dict[int, bool] = {}
    exit_signal: dict[int, bool] = {}
    for i in range(warmup, n - 1):
        recent = rng[i - contraction : i]
        threshold = sorted(recent)[int(len(recent) * quantile)]
        contracted = rng[i] <= threshold
        close = window[i][3]
        prior_high = max(window[j][1] for j in range(i - breakout, i))
        prior_low = min(window[j][2] for j in range(i - exit_window, i))
        armed[i] = contracted and close > prior_high
        exit_signal[i] = close < prior_low

    returns: list[float] = []
    trade_returns: list[float] = []
    held = False
    entry_price = 0.0
    for i in range(warmup, n - 1):
        fill = window[i + 1][0]
        if not held and armed[i]:
            held = True
            entry_price = fill * (1 + SLIP) * (1 + FEE)
            continue
        if held and exit_signal[i]:
            held = False
            exit_price = fill * (1 - SLIP) * (1 - FEE)
            realised = exit_price / entry_price - 1
            trade_returns.append(realised)
            returns.append(realised)
            bar_returns[i] = realised
            continue
        if held:
            returns.append(0.0)

    if len(returns) < 2:
        return TrialScore(0.0, tuple(trade_returns), tuple(bar_returns))
    deviation = pstdev(returns)
    score = mean(returns) / deviation if deviation > 0 else 0.0
    return TrialScore(score, tuple(trade_returns), tuple(bar_returns))


# --------------------------------------------------------------------------------------------
# Independent implementation, Layer 2: from-spec re-derivation of the DSR significance path.
# Re-derived from the Bailey/López de Prado formulas documented in tios.validation.multiple_testing,
# not by importing that module, so the comparison is a genuine second opinion.
# --------------------------------------------------------------------------------------------
def _ind_sample_sharpe(returns: Sequence[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    m = sum(returns) / n
    var = sum((x - m) ** 2 for x in returns) / (n - 1)
    return m / sqrt(var) if var > 0 else 0.0


def _ind_sharpe_variance(sharpes: Sequence[float]) -> float:
    if len(sharpes) < 2:
        raise ValueError("at least two trial Sharpes are required")
    return variance(sharpes)


def _ind_implied_independent_trials(raw_trials: int, average_correlation: float) -> float:
    if raw_trials < 1:
        raise ValueError("raw_trials must be positive")
    return 1.0 + (1.0 - average_correlation) * (raw_trials - 1)


def _ind_expected_max_noise_sharpe(sharpe_variance: float, independent_trials: float) -> float:
    if independent_trials == 1 or sharpe_variance == 0:
        return 0.0
    return sqrt(sharpe_variance) * (
        (1 - EULER_GAMMA) * NORMAL.inv_cdf(1 - 1 / independent_trials)
        + EULER_GAMMA * NORMAL.inv_cdf(1 - 1 / (independent_trials * e))
    )


def _ind_deflated_sharpe_ratio(
    observed_sharpe: float,
    sharpe_variance: float,
    independent_trials: float,
    sample_count: int,
) -> dict[str, float]:
    if sample_count < 2:
        raise ValueError("sample_count must be at least 2")
    sr0 = _ind_expected_max_noise_sharpe(sharpe_variance, independent_trials)
    # Default skew 0 / kurtosis 3 -> variance_adjustment collapses to 1 + 0.5*S^2.
    variance_adjustment = 1 + 0.5 * observed_sharpe**2
    z = (observed_sharpe - sr0) * sqrt(sample_count - 1) / sqrt(variance_adjustment)
    return {"expected_maximum_noise_sharpe": sr0, "z_score": z, "dsr": NORMAL.cdf(z)}


def _ind_pairwise_corr(left: Sequence[float], right: Sequence[float]) -> float:
    idx = [i for i in range(len(left)) if left[i] != 0.0 or right[i] != 0.0]
    if len(idx) < 2:
        return 0.0
    a = [left[i] for i in idx]
    b = [right[i] for i in idx]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((a[k] - ma) * (b[k] - mb) for k in range(len(a)))
    return max(0.0, min(1.0, cov / sqrt(va * vb)))


def _ind_average_correlation(bar_returns: Sequence[Sequence[float]]) -> float:
    vectors = [tuple(v) for v in bar_returns if v]
    if len(vectors) < 2:
        return 0.0
    width = min(len(v) for v in vectors)
    pairs = [(i, j) for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
    total = sum(_ind_pairwise_corr(vectors[i][:width], vectors[j][:width]) for i, j in pairs)
    return total / len(pairs)


def independent_score_trade_significance(
    *,
    observed_trade_returns: Sequence[float],
    trial_trade_returns: Sequence[Sequence[float]],
    trial_bar_returns: Sequence[Sequence[float]],
    hierarchy_trials: int,
    sample_count: int,
    min_validation_trades: int,
) -> dict[str, Any]:
    if sample_count != len(observed_trade_returns):
        raise CampaignError("sample_count must equal the scored trade series length")
    n = sample_count
    if n < min_validation_trades:
        return {"status": "INSUFFICIENT_ACTIVITY", "validation_trades": n, "dsr": None}
    observed_sharpe = _ind_sample_sharpe(observed_trade_returns)
    variance_ = _ind_sharpe_variance([_ind_sample_sharpe(r) for r in trial_trade_returns])
    avg_corr = _ind_average_correlation(trial_bar_returns)
    eff = _ind_implied_independent_trials(hierarchy_trials, avg_corr)
    dsr = _ind_deflated_sharpe_ratio(
        observed_sharpe=observed_sharpe,
        sharpe_variance=variance_,
        independent_trials=eff,
        sample_count=n,
    )
    return {
        "status": "OK",
        "validation_trades": n,
        "observed_sharpe": observed_sharpe,
        "effective_trials": eff,
        "average_correlation": avg_corr,
        "dsr": dsr,
    }


def build_significance_fixture() -> dict[str, Any]:
    """Layer-2 fixture: >= floor completed trades plus the inflation demonstration inputs.

    Observed trade returns are 12 deterministic values with genuine dispersion so a DSR is
    actually computed (not INSUFFICIENT_ACTIVITY, not zero variance). ``bar_spread`` is the same
    12-trade P&L spread across 200 decision bars (mostly flat) -> the F1 geometry: pre-D-112 the
    200-bar count would be fed to the DSR while the Sharpe was computed on 12 observations.
    """
    observed = [
        0.012,
        -0.004,
        0.021,
        -0.010,
        0.008,
        0.015,
        -0.006,
        0.019,
        -0.002,
        0.011,
        0.007,
        -0.009,
    ]
    trial_a = [
        0.005,
        -0.003,
        0.010,
        -0.002,
        0.006,
        0.004,
        -0.001,
        0.008,
        -0.004,
        0.003,
        0.002,
        -0.005,
    ]
    trial_b = [
        -0.008,
        0.002,
        -0.011,
        0.004,
        -0.006,
        -0.003,
        0.001,
        -0.009,
        0.005,
        -0.002,
        -0.004,
        0.006,
    ]
    bar_a = observed + [0.0] * (200 - len(observed))
    bar_b = trial_a + [0.0] * (200 - len(trial_a))
    bar_c = trial_b + [0.0] * (200 - len(trial_b))
    return {
        "name": "twelve_trades_with_inflation_demo",
        "description": "12 completed trades; DSR computed; F1 inflation quantified and guarded.",
        "observed_trade_returns": observed,
        "trial_trade_returns": [observed, trial_a, trial_b],
        "trial_bar_returns": [bar_a, bar_b, bar_c],
        "hierarchy_trials": 40,
        "inflated_sample_count": 200,  # pre-D-112 would have used this (bar count)
    }


# --------------------------------------------------------------------------------------------
# vectorbt cross-check (engine env only). Uses solely the API proven in engines/vectorbt/
# g10_returns.py: Portfolio.from_signals, portfolio.trades.count(), portfolio.total_return().
# --------------------------------------------------------------------------------------------
def vectorbt_pnl_check(fixture: dict[str, Any], project: TrialScore) -> dict[str, Any]:
    try:
        import numpy as np  # type: ignore[import-not-found]
        import pandas as pd  # type: ignore[import-untyped]
        import vectorbt as vbt  # type: ignore[import-not-found]
    except ImportError:
        return {"status": "SKIPPED_NO_VECTORBT"}

    bars = fixture["bars"]
    n = len(bars)
    price = [float(bar[3]) for bar in bars]  # close baseline
    entries = [False] * n
    exits = [False] * n
    # Recover the signal bars from the project bar_returns (non-zero at exit bars) and the
    # independent pass, then bake the next-open fills with costs into the price so vbt (fees=0)
    # reproduces exit_fill/entry_fill - 1 exactly. This isolates vbt's trade pairing + counting.
    ind = independent_evaluate(bars, PARAMS)
    entry_idx, exit_idx = _signal_indices(bars)
    for i in entry_idx:
        entries[i] = True
        price[i] = bars[i + 1][0] * (1 + SLIP) * (1 + FEE)
    for i in exit_idx:
        exits[i] = True
        price[i] = bars[i + 1][0] * (1 - SLIP) * (1 - FEE)
    portfolio = vbt.Portfolio.from_signals(
        pd.Series(np.array(price, dtype="float64")),
        pd.Series(entries),
        pd.Series(exits),
        fees=0.0,
        init_cash=1000.0,
    )
    vbt_count = int(portfolio.trades.count())
    vbt_total = float(portfolio.total_return())
    expected_total = 1.0
    for r in project.trade_returns:
        expected_total *= 1 + r
    expected_total -= 1.0
    return {
        "status": "OK",
        "engine": f"vectorbt {vbt.__version__}",
        "vbt_trade_count": vbt_count,
        "project_trade_count": len(project.trade_returns),
        "trade_count_match": vbt_count == len(project.trade_returns) == len(ind.trade_returns),
        "vbt_total_return": vbt_total,
        "expected_total_return": expected_total,
        "total_return_match": abs(vbt_total - expected_total) <= 1e-9,
    }


def _signal_indices(bars: Sequence[Bar]) -> tuple[list[int], list[int]]:
    """Entry/exit bar indices from the independent state walk (for the vectorbt price baking)."""
    contraction = int(PARAMS["contraction_window"])
    breakout = int(PARAMS["breakout_window"])
    exit_window = int(PARAMS["exit_window"])
    quantile = float(PARAMS["contraction_quantile"])
    n = len(bars)
    warmup = max(contraction, breakout, exit_window) + 1
    rng = [(b[1] - b[2]) / b[3] if b[3] else 0.0 for b in bars]
    entries: list[int] = []
    exits: list[int] = []
    held = False
    for i in range(warmup, n - 1):
        recent = rng[i - contraction : i]
        threshold = sorted(recent)[int(len(recent) * quantile)]
        close = bars[i][3]
        armed = rng[i] <= threshold and close > max(bars[j][1] for j in range(i - breakout, i))
        exit_sig = close < min(bars[j][2] for j in range(i - exit_window, i))
        if not held and armed:
            held = True
            entries.append(i)
        elif held and exit_sig:
            held = False
            exits.append(i)
    return entries, exits


# --------------------------------------------------------------------------------------------
# Comparison drivers.
# --------------------------------------------------------------------------------------------
def _max_abs_diff(a: Sequence[float], b: Sequence[float]) -> float:
    return max((abs(x - y) for x, y in zip(a, b, strict=True)), default=0.0)


def compare_pnl_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    project = fb.evaluate(fixture["bars"], PARAMS)
    independent = independent_evaluate(fixture["bars"], PARAMS)
    expected = fixture["expected_trade_returns"]

    count_ok = len(project.trade_returns) == len(independent.trade_returns) == len(expected)
    pnl_vs_independent = _max_abs_diff(project.trade_returns, independent.trade_returns)
    pnl_vs_truth = _max_abs_diff(project.trade_returns, expected)
    bar_returns_diff = _max_abs_diff(project.bar_returns, independent.bar_returns)
    score_diff = abs(project.score - independent.score)

    checks = {
        "trade_count_match": count_ok,
        "per_trade_pnl_vs_independent_within_tol": pnl_vs_independent <= PNL_TOL,
        "per_trade_pnl_vs_ground_truth_within_tol": pnl_vs_truth <= PNL_TOL,
        "bar_returns_within_tol": bar_returns_diff <= PNL_TOL,
        "score_within_tol": score_diff <= STAT_TOL,
    }
    return {
        "name": fixture["name"],
        "description": fixture["description"],
        "bars": len(fixture["bars"]),
        "project": {
            "trade_returns": list(project.trade_returns),
            "trade_count": len(project.trade_returns),
            "score": project.score,
        },
        "independent": {
            "trade_returns": list(independent.trade_returns),
            "trade_count": len(independent.trade_returns),
            "score": independent.score,
        },
        "ground_truth_trade_returns": list(expected),
        "max_abs_diff": {
            "per_trade_pnl_vs_independent": pnl_vs_independent,
            "per_trade_pnl_vs_ground_truth": pnl_vs_truth,
            "bar_returns_vs_independent": bar_returns_diff,
            "score_vs_independent": score_diff,
        },
        "vectorbt": vectorbt_pnl_check(fixture, project),
        "checks": checks,
        "agree": all(checks.values()),
    }


def compare_significance_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    floor = 10
    kwargs = {
        "observed_trade_returns": fixture["observed_trade_returns"],
        "trial_trade_returns": fixture["trial_trade_returns"],
        "trial_bar_returns": fixture["trial_bar_returns"],
        "hierarchy_trials": fixture["hierarchy_trials"],
        "min_validation_trades": floor,
    }
    n_trades = len(fixture["observed_trade_returns"])
    project = score_trade_significance(sample_count=n_trades, **kwargs)
    independent = independent_score_trade_significance(sample_count=n_trades, **kwargs)

    z_diff = abs(project["dsr"]["z_score"] - independent["dsr"]["z_score"])
    dsr_diff = abs(project["dsr"]["dsr"] - independent["dsr"]["dsr"])
    sr_diff = abs(project["observed_sharpe"] - independent["observed_sharpe"])
    eff_diff = abs(project["effective_trials"] - independent["effective_trials"])

    # F1 regression: the fail-closed guard must reject the pre-D-112 inflated bar count, and the
    # inflation it used to admit is quantified (z scales with sqrt(sample_count - 1)).
    inflated_count = fixture["inflated_sample_count"]
    guard_rejected_inflated = False
    try:
        score_trade_significance(sample_count=inflated_count, **kwargs)
    except CampaignError:
        guard_rejected_inflated = True
    honest_z = project["dsr"]["z_score"]
    inflated_z = honest_z * sqrt((inflated_count - 1) / (n_trades - 1))
    inflation_factor = sqrt((inflated_count - 1) / (n_trades - 1))

    checks = {
        "observed_sharpe_within_tol": sr_diff <= STAT_TOL,
        "effective_trials_within_tol": eff_diff <= STAT_TOL,
        "z_score_within_tol": z_diff <= STAT_TOL,
        "dsr_within_tol": dsr_diff <= STAT_TOL,
        "f1_guard_rejects_inflated_sample_count": guard_rejected_inflated,
    }
    return {
        "name": fixture["name"],
        "description": fixture["description"],
        "trades": n_trades,
        "project": {
            "observed_sharpe": project["observed_sharpe"],
            "effective_trials": project["effective_trials"],
            "z_score": project["dsr"]["z_score"],
            "dsr": project["dsr"]["dsr"],
        },
        "independent": {
            "observed_sharpe": independent["observed_sharpe"],
            "effective_trials": independent["effective_trials"],
            "z_score": independent["dsr"]["z_score"],
            "dsr": independent["dsr"]["dsr"],
        },
        "max_abs_diff": {
            "observed_sharpe": sr_diff,
            "effective_trials": eff_diff,
            "z_score": z_diff,
            "dsr": dsr_diff,
        },
        "f1_inflation_demo": {
            "honest_sample_count": n_trades,
            "inflated_sample_count": inflated_count,
            "honest_z": honest_z,
            "would_be_inflated_z": inflated_z,
            "inflation_factor": inflation_factor,
            "guard_rejected_inflated_sample_count": guard_rejected_inflated,
        },
        "checks": checks,
        "agree": all(checks.values()),
    }


def run() -> dict[str, Any]:
    pnl = [compare_pnl_fixture(fx) for fx in build_pnl_fixtures()]
    significance = [compare_significance_fixture(build_significance_fixture())]
    all_agree = all(r["agree"] for r in pnl) and all(r["agree"] for r in significance)
    vbt_statuses = {r["vectorbt"]["status"] for r in pnl}
    return {
        "schema_version": 1,
        "title": "Campaign evaluator differential test (D-112 residual follow-up)",
        "decision_ref": "D-112",
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "purpose": (
            "Reduce single-implementation risk in the D-112-remediated campaign evaluator by "
            "comparing it against an independent from-spec implementation on synthetic data with "
            "hand-derivable ground truth. Does not change any threshold or verdict."
        ),
        "evaluator_under_test": {
            "trade_return_builder": "scripts/run_first_budgeted_campaign.py::evaluate",
            "significance_scorer": "src/tios/validation/campaign.py::score_trade_significance",
            "cost_model": {"fee_rate_per_side": FEE, "slippage_rate_per_side": SLIP},
            "parameters": PARAMS,
        },
        "independent_implementation": {
            "trade_return_builder": "run_evaluator_differential_test.py::independent_evaluate",
            "significance_scorer": (
                "run_evaluator_differential_test.py::independent_score_trade_significance"
            ),
            "language": "python stdlib (math, statistics) — no numpy/vectorbt in the runtime env",
            "vectorbt_cross_check": (
                "engine-env only; uses Portfolio.from_signals / trades.count() / total_return() "
                "as in engines/vectorbt/g10_returns.py; SKIPPED when vectorbt is not importable"
            ),
        },
        "tolerances": {
            "per_trade_pnl_abs": PNL_TOL,
            "summary_stat_abs": STAT_TOL,
            "trade_count": "exact",
        },
        "vectorbt_status": sorted(vbt_statuses),
        "layer_1_trade_return_builder": pnl,
        "layer_2_significance_scorer": significance,
        "verdict": "AGREEMENT" if all_agree else "DISCREPANCY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any fixture disagrees (do not just write the artifact)",
    )
    args = parser.parse_args()

    evidence = run()
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    print(f"verdict: {evidence['verdict']}")
    print(f"vectorbt: {', '.join(evidence['vectorbt_status'])}")
    for layer in ("layer_1_trade_return_builder", "layer_2_significance_scorer"):
        for r in evidence[layer]:
            print(f"  [{'ok' if r['agree'] else 'FAIL'}] {r['name']}")
    print(f"artifact: {ARTIFACT_PATH.relative_to(ROOT)}")

    if args.check and evidence["verdict"] != "AGREEMENT":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
