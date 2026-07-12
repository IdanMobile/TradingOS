"""Checks for the funding-carry backtest (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_funding_carry as fc  # noqa: E402


def test_positive_funding_pair_is_carried_and_profits() -> None:
    matrix = {"A": [0.001] * 200}  # constant +0.1%/8h funding
    strat = fc.backtest(matrix, threshold=0.0, lookback=3, rebalance=3)
    total = 1.0
    for r in strat:
        total *= 1 + r
    assert total > 1.0  # collecting positive funding compounds up


def test_negative_funding_pair_is_filtered_out() -> None:
    matrix = {"B": [-0.001] * 200}  # persistently negative funding
    strat = fc.backtest(matrix, threshold=0.0, lookback=3, rebalance=3)
    # The trailing-mean filter never holds it (mean < 0), so no carry losses accrue.
    assert all(r == 0.0 for r in strat)


def test_metrics_shape() -> None:
    m = fc._metrics([0.001] * 100)
    assert m["bars"] == 100
    assert m["total_return_pct"] > 0
    assert m["max_drawdown_pct"] <= 0
