#!/usr/bin/env python3
"""Realistic-sizing validation of the trend-following cluster + production G10 (DSR).

The universe search's headline returns (+18,657% etc.) are an artifact of all-in
compounding on the 2021 alt bull. This replaces that with VOLATILITY-TARGETED sizing
(target ~15% annualized, capped at 1.0 — no leverage), which is the standard for
trend-following and removes the distortion, then reports risk-adjusted metrics
(Sharpe, annualized return/vol, max drawdown) and deflates the best Sharpe through
production G10 (Deflated Sharpe Ratio) for the FULL number of trials searched.

DSR >= 0.95 AND a sane max drawdown is the honest bar. Research only; nothing
validated for trading until the stats-specialist review (RG-07) signs off; no venue,
no orders, execution_authority=NONE. Float math is fine for risk statistics.

ponytail: reuses the universe dataset loader + strategy builders + the project's own
DSR estimator (tios.validation.multiple_testing); adds the vol-targeted P&L engine.
"""

from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_universe_search as uni  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "validation" / "trend_cluster"
TARGET_VOL = 0.15  # annualized volatility target
VOL_WINDOW = 30  # bars for realized-vol estimate
FEE = 0.001  # per unit turnover
PPY = {"1h": 24 * 365, "4h": 6 * 365, "1d": 365}
DSR_PASS = 0.95

# The trend / breakout / momentum families (exclude pure mean-reversion & flow).
TREND_IDS = {
    "EXT-GOLDEN-CROSS", "EXT-SMA-10-30", "EXT-SMA-20-50", "EXT-EMA-12-26", "EXT-EMA-8-21",
    "EXT-EMA-20-50", "EXT-EMA-50-200", "EXT-TRIPLE-MA", "EXT-TREND-SMA200", "EXT-TURTLE-S1",
    "EXT-TURTLE-S2", "EXT-DONCHIAN-40", "EXT-BB-BREAKOUT", "EXT-ROC-12", "EXT-ROC-20",
    "SIG-VOLUME-BREAKOUT", "SIG-VOL-REGIME-TREND", "SIG-VWAP-TREND",
}  # fmt: skip


def _asset_returns(closes: list[float]) -> list[float]:
    return [0.0] + [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def _realized_vol(returns: list[float], window: int, ppy: int) -> list[float]:
    """Rolling annualized volatility of asset returns (O(n))."""
    out = [0.0] * len(returns)
    total = sq = 0.0
    ann = sqrt(ppy)
    for i, r in enumerate(returns):
        total += r
        sq += r * r
        if i >= window:
            old = returns[i - window]
            total -= old
            sq -= old * old
        if i + 1 >= window:
            var = max(sq / window - (total / window) ** 2, 0.0)
            out[i] = sqrt(var) * ann
    return out


def _positions(entries: list[bool], exits: list[bool], rvol: list[float]) -> list[float]:
    """Long/flat state -> vol-targeted fraction in [0,1] (no leverage)."""
    pos = [0.0] * len(entries)
    in_pos = False
    for i in range(len(entries)):
        if not in_pos and entries[i]:
            in_pos = True
        elif in_pos and exits[i]:
            in_pos = False
        if in_pos and rvol[i] > 0:
            pos[i] = min(1.0, TARGET_VOL / rvol[i])
    return pos


def backtest(closes: list[float], entries: list[bool], exits: list[bool], ppy: int) -> dict:
    """Vol-targeted long/flat P&L with turnover costs; returns risk metrics + return series."""
    asset_ret = _asset_returns(closes)
    rvol = _realized_vol(asset_ret, VOL_WINDOW, ppy)
    pos = _positions(entries, exits, rvol)
    strat = [0.0] * len(closes)
    prev = 0.0
    trades = 0
    for i in range(1, len(closes)):
        held = pos[i - 1]
        strat[i] = held * asset_ret[i] - FEE * abs(held - prev)
        if (held > 0) != (prev > 0):
            trades += 1
        prev = held
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in strat:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    sd = pstdev(strat)
    sharpe_bar = mean(strat) / sd if sd > 0 else 0.0
    return {
        "sharpe_bar": sharpe_bar,  # per-bar (for DSR)
        "sharpe_ann": sharpe_bar * sqrt(ppy),
        "ann_return_pct": round((equity ** (ppy / len(strat)) - 1) * 100, 1)
        if equity > 0
        else -100.0,
        "ann_vol_pct": round(sd * sqrt(ppy) * 100, 1),
        "total_return_pct": round((equity - 1) * 100, 1),
        "max_drawdown_pct": round(max_dd * 100, 1),
        "trades": trades,
        "bars": len(strat),
        "returns": strat,
    }


def build_report() -> dict:
    datasets = uni._datasets()
    strategies = [s for s in uni.ALL_STRATEGIES if s.strategy_id in TREND_IDS]
    trials: list[dict] = []
    for strat in strategies:
        for name, candles in datasets:
            ppy = PPY[name.rsplit("_", 1)[1]]
            closes = [float(c) for c in candles["close"]]
            for key, builder in strat.variants.items():
                entries, exits = builder(candles)
                m = backtest(closes, entries, exits, ppy)
                if m["trades"] < 10:
                    continue
                trials.append(
                    {"strategy_id": strat.strategy_id, "dataset": name, "variant": key, **m}
                )
    if not trials:
        return {"schema": "tios-trend-validation-v1", "error": "no trials"}
    sharpes = [t["sharpe_bar"] for t in trials]
    best = max(trials, key=lambda t: t["sharpe_bar"])
    ret = best["returns"]
    m_ret = mean(ret)
    sd = pstdev(ret)
    skew = (sum((r - m_ret) ** 3 for r in ret) / len(ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - m_ret) ** 4 for r in ret) / len(ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(trials),
        sample_count=best["bars"],
        skewness=skew,
        kurtosis=kurt,
    )
    top = sorted(trials, key=lambda t: t["sharpe_bar"], reverse=True)[:12]
    return {
        "schema": "tios-trend-validation-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "sizing": f"volatility-targeted {TARGET_VOL:.0%} annualized, no leverage",
        "trials_searched": len(trials),
        "best": {
            k: best[k]
            for k in (
                "strategy_id",
                "dataset",
                "variant",
                "sharpe_ann",
                "ann_return_pct",
                "ann_vol_pct",
                "max_drawdown_pct",
                "trades",
                "bars",
            )
        },
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "z_score": round(dsr["z_score"], 3),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "note": "PASS still requires stats-specialist review (RG-07) before promotion.",
        },
        "top_contexts": [
            {
                k: t[k]
                for k in (
                    "strategy_id",
                    "dataset",
                    "variant",
                    "sharpe_ann",
                    "ann_return_pct",
                    "max_drawdown_pct",
                    "trades",
                )
            }
            for t in top
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "TREND_VALIDATION.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "error" in report:
        print(report)
        return
    b, g = report["best"], report["g10_dsr"]
    print(f"trials searched: {report['trials_searched']}  (sizing: {report['sizing']})")
    print(
        f"best Sharpe(ann): {b['sharpe_ann']:.2f}  {b['strategy_id']} on {b['dataset']} "
        f"| ann {b['ann_return_pct']}% | maxDD {b['max_drawdown_pct']}% | {b['trades']} trades"
    )
    print(
        f"G10 DSR: {g['dsr']}  (need >= {g['threshold']})  -> {g['verdict']}   "
        f"[E[max noise Sharpe]={g['expected_max_noise_sharpe']}]"
    )


if __name__ == "__main__":
    main()
