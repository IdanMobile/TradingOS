"""Checks for the cross-sectional momentum engine (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scripts.run_cross_sectional_momentum as xs  # noqa: E402


def test_backtest_holds_the_winner_and_avoids_losers() -> None:
    n = 120
    prices = {
        "WIN": [100.0 * (1.01**i) for i in range(n)],  # steady riser
        "LOSE": [100.0 * (0.99**i) for i in range(n)],  # steady faller
    }
    strat = xs.backtest_long_only(prices, lookback=10, top_k=1, rebalance=10)
    total = 1.0
    for r in strat:
        total *= 1 + r
    assert total > 1.0  # rotating into WIN makes money


def test_dual_filter_goes_to_cash_when_all_negative() -> None:
    n = 120
    prices = {
        "A": [100.0 * (0.99**i) for i in range(n)],
        "B": [100.0 * (0.98**i) for i in range(n)],
    }
    strat = xs.backtest_long_only(prices, lookback=10, top_k=2, rebalance=10)
    # Everything is falling -> dual filter holds nothing -> flat (near-zero) equity.
    total = 1.0
    for r in strat:
        total *= 1 + r
    assert total > 0.6  # not riding the losers down; cash-protected


def test_vol_target_scales_down_high_vol() -> None:
    calm = [0.001] * 60
    wild = [0.05 * (1 if i % 2 else -1) for i in range(60)]
    calm_scaled = xs.vol_target(calm, target=0.30, window=20)
    wild_scaled = xs.vol_target(wild, target=0.30, window=20)
    # High-vol series gets scaled down harder (smaller average absolute exposure).
    avg_calm = sum(abs(x) for x in calm_scaled) / len(calm_scaled)
    avg_wild = sum(abs(x) for x in wild_scaled) / len(wild_scaled)
    assert avg_wild < sum(abs(x) for x in wild) / len(wild)  # scaled below raw
    assert avg_calm > 0
