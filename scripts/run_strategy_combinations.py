#!/usr/bin/env python3
"""Combination / ensemble search over the public strategies + G10 (DSR).

Operator ask: try mixing strategies to find good combinations. This takes a curated base set
(one builder per strategy, spanning trend / breakout / reversion / momentum / pattern) and tests:
  * CONFLUENCE pairs — enter only when BOTH agree (AND entries, OR exits);
  * VOTING ensembles — enter when >= K of N agree.
Each mix is backtested to a per-bar long/flat return series and DSR-scored, with the trial count
deflating the best (so "found a good mix" cannot be luck-mined).

Honest expectation, stated up front: mixing zero-edge components cannot manufacture edge — this
is coverage + a rigorous check, not a shortcut. RESEARCH-ONLY; execution_authority=NONE.

ponytail: reuses ext strategy builders + seed candles + the project DSR; new code is the AND/vote
combiners and a returns backtest.
"""

from __future__ import annotations

import json
import sys
from itertools import combinations
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_seed_research_cycle_v0 as seed  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "research_lab" / "strategy_combinations"
DATASETS = ("BTCUSDT_1h", "ETHUSDT_1h")
FEE = 0.001
PPY = 24 * 365
DSR_PASS = 0.95
# One representative builder per strategy, spanning every family (id -> first variant).
BASE_IDS = (
    "EXT-GOLDEN-CROSS", "EXT-DONCHIAN-40", "EXT-MACD-CROSS", "EXT-KELTNER-BREAKOUT",
    "EXT-RSI14", "EXT-BB-REVERSION", "EXT-STOCHASTIC", "EXT-VORTEX", "EXT-PAT-ENGULFING",
)  # fmt: skip
Signals = tuple[list[bool], list[bool]]


def _base_builders() -> dict[str, ext.SignalBuilder]:
    by_id = {s.strategy_id: s for s in ext.STRATEGIES}
    return {sid: next(iter(by_id[sid].variants.values())) for sid in BASE_IDS if sid in by_id}


def confluence(builders: list[ext.SignalBuilder]) -> ext.SignalBuilder:
    """Enter only when EVERY member signals entry; exit when ANY signals exit."""

    def build(c: ext.Candles) -> Signals:
        signals = [b(c) for b in builders]
        n = len(c["close"])
        entries = [all(s[0][i] for s in signals) for i in range(n)]
        exits = [any(s[1][i] for s in signals) for i in range(n)]
        return entries, exits

    return build


def voting(builders: list[ext.SignalBuilder], k: int) -> ext.SignalBuilder:
    """Enter when >= k members signal entry; exit when >= k signal exit."""

    def build(c: ext.Candles) -> Signals:
        signals = [b(c) for b in builders]
        n = len(c["close"])
        entries = [sum(s[0][i] for s in signals) >= k for i in range(n)]
        exits = [sum(s[1][i] for s in signals) >= k for i in range(n)]
        return entries, exits

    return build


def backtest_returns(candles: ext.Candles, signals: Signals) -> tuple[list[float], int]:
    """Long/flat per-bar returns; decide on bar i-1's signal, act at bar i, fee on each toggle."""
    close = [float(x) for x in candles["close"]]
    entries, exits = signals
    n = len(close)
    ret = [0.0] * n
    pos, trades = 0, 0
    for i in range(1, n):
        if pos:
            ret[i] = close[i] / close[i - 1] - 1
        new = pos
        if pos == 0 and entries[i - 1]:
            new = 1
        elif pos == 1 and exits[i - 1]:
            new = 0
        if new != pos:
            ret[i] -= FEE
            trades += 1
            pos = new
    return ret, trades


def _sharpe(returns: list[float]) -> float:
    sd = pstdev(returns)
    return mean(returns) / sd if sd > 0 else 0.0


def _evaluate(builder: ext.SignalBuilder) -> tuple[float, int, list[float]]:
    """Best per-bar Sharpe across datasets (with its trades + returns)."""
    best: tuple[float, int, list[float]] = (-1e9, 0, [])
    for name in DATASETS:
        candles = seed.load_candles(seed.DATASETS[name])
        returns, trades = backtest_returns(candles, builder(candles))
        sharpe = _sharpe(returns)
        if trades >= ext.MIN_TRADES and sharpe > best[0]:
            best = (sharpe, trades, returns)
    return best


def build_report() -> dict:
    base = _base_builders()
    ids = list(base)
    trials: list[dict] = []

    for a, b in combinations(ids, 2):  # confluence pairs
        sharpe, trades, returns = _evaluate(confluence([base[a], base[b]]))
        trials.append({"kind": "confluence", "members": [a, b], "sharpe_bar": sharpe,
                       "trades": trades, "returns": returns})  # fmt: skip
    for k in (2, 3):  # voting ensembles across the whole base set
        sharpe, trades, returns = _evaluate(voting([base[i] for i in ids], k))
        trials.append({"kind": f"vote_{k}_of_{len(ids)}", "members": ids, "sharpe_bar": sharpe,
                       "trades": trades, "returns": returns})  # fmt: skip

    scored = [t for t in trials if t["returns"]]
    best = max(scored, key=lambda t: t["sharpe_bar"])
    sharpes = [t["sharpe_bar"] for t in scored]
    ret = best["returns"]
    mr, sd = mean(ret), pstdev(ret)
    skew = (sum((r - mr) ** 3 for r in ret) / len(ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in ret) / len(ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(scored),
        sample_count=len(ret),
        skewness=skew,
        kurtosis=kurt,
    )
    top = sorted(scored, key=lambda t: t["sharpe_bar"], reverse=True)[:6]
    return {
        "schema": "tios-strategy-combinations-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "base_strategies": ids,
        "combinations_tested": len(scored),
        "best": {
            "kind": best["kind"],
            "members": best["members"],
            "sharpe_ann": round(best["sharpe_bar"] * sqrt(PPY), 2),
            "trades": best["trades"],
        },  # fmt: skip
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "verdict_is_genuine": False,
            "note": "Mixing zero-edge components does not create edge; confluence mostly cuts "
            "trade count. A PASS would still owe out-of-sample + cross-engine reproduction.",
        },
        "top_combinations": [
            {
                "kind": t["kind"],
                "members": t["members"],
                "sharpe_ann": round(t["sharpe_bar"] * sqrt(PPY), 2),
                "trades": t["trades"],
            }
            for t in top
        ],  # fmt: skip
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "STRATEGY_COMBINATIONS.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    b, g = report["best"], report["g10_dsr"]
    print(f"tested {report['combinations_tested']} mixes of {len(report['base_strategies'])} base")
    print(f"best: {b['kind']} {b['members']} | Sharpe {b['sharpe_ann']} | {b['trades']} trades")
    print(f"G10 DSR: {g['dsr']} (need >= {g['threshold']}) -> {g['verdict']}")


if __name__ == "__main__":
    main()
