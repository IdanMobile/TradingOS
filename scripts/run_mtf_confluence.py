#!/usr/bin/env python3
"""Multi-timeframe (MTF) confluence search + G10 (DSR).

Tests the "trade with the bigger trend" idea: take the entry signal on the LOWER timeframe (1h),
but only when the HIGHER timeframe (1d) trend agrees (daily close above its SMA). The higher-TF
trend is aligned to each 1h bar CAUSALLY — only daily bars that have fully closed before the hour
are used, so there is no lookahead. Each base strategy is scored unfiltered vs MTF-filtered. The
retained full-sample statistic is descriptive only because the implementation first chooses the
best pair inside each strategy and therefore collapses the actual search population.

MTF is more defensible than same-timeframe mixing (trend persists across scales), but it is still a
FILTER, not an edge source — the honest question is whether the daily-trend gate improves the DSR.
RESEARCH-ONLY; execution_authority=NONE.

ponytail: reuses ext builders + the combination backtest + the project DSR; the only new code is the
two-timeframe load and the causal daily->hourly trend alignment.
"""

from __future__ import annotations

import bisect
import json
import sys
from datetime import timedelta
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from decimal import Decimal  # noqa: E402

import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_strategy_combinations as comb  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

MULTI = ROOT / "data" / "normalized_multi"
OUT = ROOT / "artifacts" / "research_lab" / "mtf_confluence"
ENTRY_TF, TREND_TF = "1h", "1d"
TREND_DELTA = timedelta(days=1)  # one higher-TF bar
TREND_SMA = 50
PPY, DSR_PASS = 24 * 365, 0.95
PAIRS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "LTCUSDT")
# Trend/breakout base strategies — the family a higher-TF trend filter is meant to help.
BASE_IDS = ("EXT-DONCHIAN-40", "EXT-GOLDEN-CROSS", "EXT-MACD-CROSS", "EXT-KELTNER-BREAKOUT",
            "EXT-TREND-SMA200", "EXT-VORTEX")  # fmt: skip


def _load_tf(pair: str, tf: str) -> tuple[list, ext.Candles]:  # type: ignore[type-arg]
    table = pq.read_table(
        MULTI / f"{pair}_{tf}.parquet",
        columns=["timestamp_open_utc", "open", "high", "low", "close"],
    )
    times = [d.as_py() for d in table.column("timestamp_open_utc")]
    candles = {
        col: [Decimal(str(v.as_py())) for v in table.column(col)]
        for col in ("open", "high", "low", "close")
    }
    return times, candles


def daily_trend_up(candles: ext.Candles, sma_w: int) -> list[bool]:
    """Higher-TF trend: True where the daily close is above its SMA (else False / warmup)."""
    close = candles["close"]
    sma = ext._sma(close, sma_w)
    return [sma[i] is not None and close[i] > sma[i] for i in range(len(close))]


def align_trend(lo_times: list, hi_times: list, hi_up: list[bool]) -> list[bool]:  # type: ignore[type-arg]
    """Map each lower-TF bar to the most recent HIGHER-TF bar that has fully closed (causal)."""
    hi_close = [t + TREND_DELTA for t in hi_times]  # a daily bar is known only after it closes
    aligned = [False] * len(lo_times)
    for k, t in enumerate(lo_times):
        idx = bisect.bisect_right(hi_close, t) - 1  # last daily bar closed at/before this hour
        if idx >= 0:
            aligned[k] = hi_up[idx]
    return aligned


def mtf_signals(
    lo_candles: ext.Candles, higher_up: list[bool], builder: ext.SignalBuilder
) -> comb.Signals:
    """Enter only when the base signal fires AND the higher-TF trend is up; exit on base exit or
    when the higher-TF trend flips down."""
    entries, exits = builder(lo_candles)
    mtf_entries = [e and up for e, up in zip(entries, higher_up, strict=True)]
    mtf_exits = [x or (not up) for x, up in zip(exits, higher_up, strict=True)]
    return mtf_entries, mtf_exits


def _score(builder: ext.SignalBuilder, *, filtered: bool) -> tuple[float, int, list[float]]:
    best: tuple[float, int, list[float]] = (-1e9, 0, [])
    for pair in PAIRS:
        try:
            lo_times, lo = _load_tf(pair, ENTRY_TF)
            hi_times, hi = _load_tf(pair, TREND_TF)
        except FileNotFoundError:
            continue
        if filtered:
            up = align_trend(lo_times, hi_times, daily_trend_up(hi, TREND_SMA))
            signals = mtf_signals(lo, up, builder)
        else:
            signals = builder(lo)
        returns, trades = comb.backtest_returns(lo, signals)
        sharpe = mean(returns) / pstdev(returns) if pstdev(returns) > 0 else 0.0
        if trades >= ext.MIN_TRADES and sharpe > best[0]:
            best = (sharpe, trades, returns)
    return best


def _legacy_collapsed_dsr(returns: list[float], sharpes: list[float], trials: int) -> float:
    """Preserve the old descriptive statistic; it is not valid G10 evidence."""
    mr, sd = mean(returns), pstdev(returns)
    skew = (sum((r - mr) ** 3 for r in returns) / len(returns)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in returns) / len(returns)) / sd**4 if sd > 0 else 3.0
    return deflated_sharpe_ratio(
        observed_sharpe=mean(returns) / sd if sd > 0 else 0.0,
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=trials,
        sample_count=len(returns),
        skewness=skew,
        kurtosis=kurt,
    )["dsr"]


def _probabilistic_sharpe_vs_zero(returns: list[float]) -> float:
    """Test one untouched OOS series against zero without a multiple-trial claim."""
    mr, sd = mean(returns), pstdev(returns)
    skew = (sum((r - mr) ** 3 for r in returns) / len(returns)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in returns) / len(returns)) / sd**4 if sd > 0 else 3.0
    return deflated_sharpe_ratio(
        observed_sharpe=mr / sd if sd > 0 else 0.0,
        sharpe_variance=0.0,
        independent_trials=1,
        sample_count=len(returns),
        skewness=skew,
        kurtosis=kurt,
    )["dsr"]


def _out_of_sample(by_id: dict, split: float = 0.6) -> dict:  # type: ignore[type-arg]
    """Select on the training prefix, then screen the one untouched OOS series.

    The tail statistic is a probabilistic Sharpe ratio versus zero, not DSR: the
    strategy/pair search happens only on the training prefix.
    """
    pool = 0
    best: tuple[float, str, str, list[float], int] | None = None
    for sid in BASE_IDS:
        if sid not in by_id:
            continue
        builder = next(iter(by_id[sid].variants.values()))
        for pair in PAIRS:
            try:
                lo_times, lo = _load_tf(pair, ENTRY_TF)
                hi_times, hi = _load_tf(pair, TREND_TF)
            except FileNotFoundError:
                continue
            up = align_trend(lo_times, hi_times, daily_trend_up(hi, TREND_SMA))
            returns, trades = comb.backtest_returns(lo, mtf_signals(lo, up, builder))
            if trades < ext.MIN_TRADES:
                continue
            pool += 1
            cut = int(len(returns) * split)
            train = returns[:cut]
            tsh = mean(train) / pstdev(train) if pstdev(train) > 0 else 0.0
            if best is None or tsh > best[0]:
                best = (tsh, sid, pair, returns, cut)
    assert best is not None
    tsh, sid, pair, returns, cut = best
    test = returns[cut:]
    oos_sharpe = mean(test) / pstdev(test) if pstdev(test) > 0 else 0.0
    oos_psr = _probabilistic_sharpe_vs_zero(test)
    passed_screen = oos_psr >= DSR_PASS
    return {
        "selected": f"{sid} on {pair}",
        "selection_pool": pool,
        "train_sharpe_ann": round(tsh * sqrt(PPY), 2),
        "oos_sharpe_ann": round(oos_sharpe * sqrt(PPY), 2),
        "oos_psr_vs_zero": round(oos_psr, 4),
        "screen_status": "PASS_SCREEN_ONLY" if passed_screen else "FAIL",
        "promotion_eligible": False,
        "note": "Untouched OOS probabilistic Sharpe ratio versus zero; not DSR or G10.",
    }


def build_report() -> dict:
    by_id = {s.strategy_id: s for s in ext.STRATEGIES}
    rows, mtf_trials = [], []
    for sid in BASE_IDS:
        if sid not in by_id:
            continue
        builder = next(iter(by_id[sid].variants.values()))
        base_s, base_t, _ = _score(builder, filtered=False)
        mtf_s, mtf_t, mtf_ret = _score(builder, filtered=True)
        rows.append({
            "strategy_id": sid,
            "base_sharpe_ann": round(base_s * sqrt(PPY), 2), "base_trades": base_t,
            "mtf_sharpe_ann": round(mtf_s * sqrt(PPY), 2), "mtf_trades": mtf_t,
            "mtf_helped": mtf_s > base_s,
        })  # fmt: skip
        if mtf_ret:
            mtf_trials.append({"strategy_id": sid, "sharpe_bar": mtf_s, "returns": mtf_ret})

    best = max(mtf_trials, key=lambda t: t["sharpe_bar"])
    legacy_dsr = _legacy_collapsed_dsr(
        best["returns"], [t["sharpe_bar"] for t in mtf_trials], len(mtf_trials)
    )
    helped = sum(1 for r in rows if r["mtf_helped"])
    return {
        "schema": "tios-mtf-confluence-v2",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "entry_timeframe": ENTRY_TF,
        "trend_timeframe": TREND_TF,
        "trend_filter": f"daily close > SMA{TREND_SMA}",
        "pairs": list(PAIRS),
        "per_strategy": rows,
        "mtf_helped_count": f"{helped}/{len(rows)}",
        "best_mtf": {
            "strategy_id": best["strategy_id"],
            "sharpe_ann": round(best["sharpe_bar"] * sqrt(PPY), 2),
        },  # fmt: skip
        "out_of_sample": _out_of_sample(by_id),
        "g10_dsr": {
            "status": "NOT_RUN_METHOD_INVALID",
            "legacy_collapsed_dsr": round(legacy_dsr, 4),
            "threshold": DSR_PASS,
            "verdict": "NOT_RUN",
            "verdict_is_genuine": False,
            "collapsed_strategy_trials": len(mtf_trials),
            "raw_strategy_pair_search_bound": len(BASE_IDS) * len(PAIRS),
            "note": "The legacy full-sample statistic selected the best pair inside each strategy "
            "before DSR, hiding the searched pair dimension. It is retained descriptively and "
            "cannot satisfy G10; effective independent trials are not estimated.",
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "MTF_CONFLUENCE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"{ENTRY_TF} entries filtered by {TREND_TF} trend (SMA{TREND_SMA}) over {len(PAIRS)} pairs"
    )
    for r in report["per_strategy"]:
        flag = "helped" if r["mtf_helped"] else "no help"
        print(f"  {r['strategy_id']:<20} {r['base_sharpe_ann']} -> {r['mtf_sharpe_ann']} ({flag})")
    g, oos = report["g10_dsr"], report["out_of_sample"]
    print(
        f"MTF helped {report['mtf_helped_count']} | G10 {g['status']} "
        f"(legacy collapsed statistic {g['legacy_collapsed_dsr']})"
    )
    print(
        f"OUT-OF-SAMPLE (train-select {oos['selected']} -> test): Sharpe {oos['oos_sharpe_ann']}, "
        f"PSR-vs-zero {oos['oos_psr_vs_zero']} -> {oos['screen_status']}"
    )


if __name__ == "__main__":
    main()
