#!/usr/bin/env python3
"""Cross-sectional momentum across the pair universe + production G10 (DSR).

Structurally different from every single-asset test: each rebalance, rank ALL
daily-complete pairs by trailing return and rotate. Two variants:
  * long_only  — hold top-K with a dual-momentum cash filter + vol targeting (spot-
                 tradeable today).
  * long_short — dollar-neutral: long top-K, short bottom-K. This harvests the FULL
                 cross-sectional anomaly (Jegadeesh-Titman), but is RESEARCH-ONLY here:
                 shorting needs perps/margin, a venue capability behind the S4 gate.

Honest bar unchanged: production G10 DSR >= 0.95 (deflated for each variant's config
grid), plus a sane drawdown. No venue, no orders, execution_authority=NONE. Float math
for risk statistics.

ponytail: reuses the project DSR estimator; adds multi-asset alignment + rotation.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from itertools import product
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

MULTI = ROOT / "data" / "normalized_multi"
OUT = ROOT / "artifacts" / "validation" / "cross_sectional"
PPY = 365
FEE = 0.001
DSR_PASS = 0.95
MIN_DAYS = 1400
LOOKBACKS = (20, 40, 60, 90)
TOP_KS = (3, 5, 8)
REBALANCES = (7, 14, 30)

Prices = dict[str, list[float | None]]
StratFn = Callable[[Prices, int, int, int], list[float]]


def load_daily() -> tuple[list, Prices]:
    """Daily closes per pair, aligned to the union date index (None before listing)."""
    series: dict[str, dict] = {}
    for path in sorted(MULTI.glob("*_1d.parquet")):
        t = pq.read_table(path, columns=["timestamp_open_utc", "close"])
        if t.num_rows < MIN_DAYS:
            continue
        dates = [d.as_py().date() for d in t.column("timestamp_open_utc")]
        closes = [float(c.as_py()) for c in t.column("close")]
        series[path.stem[:-3]] = dict(zip(dates, closes, strict=True))
    all_dates = sorted(set().union(*[set(s) for s in series.values()]))
    prices = {p: [s.get(d) for d in all_dates] for p, s in series.items()}
    return all_dates, prices


def _day_return(prices: Prices, pairs: list[str], t: int) -> float:
    rets = [
        prices[p][t] / prices[p][t - 1] - 1
        for p in pairs
        if prices[p][t] is not None and prices[p][t - 1] is not None
    ]
    return sum(rets) / len(rets) if rets else 0.0


def _ranked(prices: Prices, lookback: int, t: int) -> list[tuple[float, str]]:
    scored = []
    for p in prices:
        now, past = prices[p][t], prices[p][t - lookback]
        if now is not None and past is not None:
            scored.append((now / past - 1, p))
    scored.sort(reverse=True)
    return scored


def backtest_long_only(prices: Prices, lookback: int, top_k: int, rebalance: int) -> list[float]:
    """Hold top-K by relative momentum, but only names with positive absolute momentum."""
    n = len(next(iter(prices.values())))
    held: list[str] = []
    strat = [0.0] * n
    for t in range(n):
        if t > 0 and held:
            strat[t] = _day_return(prices, held, t)
        if t >= lookback and t % rebalance == 0:
            new = [p for mom, p in _ranked(prices, lookback, t)[:top_k] if mom > 0]
            strat[t] -= FEE * len(set(new) ^ set(held)) / (2 * top_k)
            held = new
    return strat


def backtest_long_short(prices: Prices, lookback: int, top_k: int, rebalance: int) -> list[float]:
    """Dollar-neutral: +top-K / -bottom-K. Research-only (shorting needs perps/margin)."""
    n = len(next(iter(prices.values())))
    longs: list[str] = []
    shorts: list[str] = []
    strat = [0.0] * n
    for t in range(n):
        if t > 0 and (longs or shorts):
            strat[t] = 0.5 * (_day_return(prices, longs, t) - _day_return(prices, shorts, t))
        if t >= lookback and t % rebalance == 0:
            ranked = _ranked(prices, lookback, t)
            new_long = [p for _, p in ranked[:top_k]]
            new_short = [p for _, p in ranked[-top_k:]]
            turn = (len(set(new_long) ^ set(longs)) + len(set(new_short) ^ set(shorts))) / (
                4 * top_k
            )
            strat[t] -= FEE * turn
            longs, shorts = new_long, new_short
    return strat


def vol_target(strat: list[float], target: float = 0.30, window: int = 30) -> list[float]:
    """Scale each day's return by exposure set from PRIOR realized vol (no lookahead)."""
    ann = sqrt(PPY)
    scaled = [0.0] * len(strat)
    for t in range(1, len(strat)):
        recent = strat[max(0, t - window) : t]
        rv = pstdev(recent) * ann if len(recent) > 1 else 0.0
        frac = min(1.0, target / rv) if rv > 0 else 1.0
        scaled[t] = frac * strat[t]
    return scaled


def _metrics(strat: list[float]) -> dict:
    equity = peak = 1.0
    max_dd = 0.0
    for r in strat:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    sd = pstdev(strat)
    sharpe_bar = mean(strat) / sd if sd > 0 else 0.0
    return {
        "sharpe_bar": sharpe_bar,
        "sharpe_ann": round(sharpe_bar * sqrt(PPY), 2),
        "ann_return_pct": round((equity ** (PPY / len(strat)) - 1) * 100, 1)
        if equity > 0
        else -100.0,
        "max_drawdown_pct": round(max_dd * 100, 1),
        "total_return_pct": round((equity - 1) * 100, 1),
        "bars": len(strat),
    }


def _grid_result(prices: Prices, strat_fn: StratFn) -> dict:
    trials = []
    for lookback, top_k, rebalance in product(LOOKBACKS, TOP_KS, REBALANCES):
        strat = vol_target(strat_fn(prices, lookback, top_k, rebalance))
        m = _metrics(strat)
        m.update(lookback=lookback, top_k=top_k, rebalance=rebalance, returns=strat)
        trials.append(m)
    sharpes = [t["sharpe_bar"] for t in trials]
    best = max(trials, key=lambda t: t["sharpe_bar"])
    ret = best["returns"]
    mr, sd = mean(ret), pstdev(ret)
    skew = (sum((r - mr) ** 3 for r in ret) / len(ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in ret) / len(ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(trials),
        sample_count=best["bars"],
        skewness=skew,
        kurtosis=kurt,
    )
    keys = ("lookback", "top_k", "rebalance", "sharpe_ann", "ann_return_pct", "max_drawdown_pct")
    return {
        "trials_searched": len(trials),
        "best": {k: best[k] for k in (*keys, "total_return_pct")},
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "note": "PASS still requires stats-specialist review (RG-07) before promotion.",
        },
        "top_configs": [
            {k: t[k] for k in keys}
            for t in sorted(trials, key=lambda t: t["sharpe_bar"], reverse=True)[:5]
        ],
    }


def _benchmark_equal_weight(prices: Prices) -> dict:
    n = len(next(iter(prices.values())))
    return _metrics([0.0] + [_day_return(prices, list(prices), t) for t in range(1, n)])


def build_report() -> dict:
    dates, prices = load_daily()
    return {
        "schema": "tios-cross-sectional-momentum-v2",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "universe_pairs": len(prices),
        "days": len(dates),
        "benchmark_equal_weight_all": _benchmark_equal_weight(prices),
        "long_only": _grid_result(prices, backtest_long_only),
        "long_short": {
            **_grid_result(prices, backtest_long_short),
            "tradeability": "RESEARCH_ONLY — shorting needs perps/margin (S4-gated)",
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "CROSS_SECTIONAL_MOMENTUM.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bench = report["benchmark_equal_weight_all"]
    print(f"universe: {report['universe_pairs']} pairs, {report['days']} days")
    print(
        f"benchmark equal-weight-all: Sharpe {bench['sharpe_ann']}, "
        f"maxDD {bench['max_drawdown_pct']}%"
    )
    for name in ("long_only", "long_short"):
        r = report[name]
        b, g = r["best"], r["g10_dsr"]
        print(
            f"{name:>11}: best Sharpe {b['sharpe_ann']} (L={b['lookback']} K={b['top_k']} "
            f"reb={b['rebalance']}) ann {b['ann_return_pct']}% maxDD {b['max_drawdown_pct']}% "
            f"| DSR {g['dsr']} -> {g['verdict']}"
        )


if __name__ == "__main__":
    main()
