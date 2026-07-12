"""Checks for the vol-targeted P&L engine (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scripts.run_trend_validation as tv  # noqa: E402


def test_asset_returns_and_positions() -> None:
    rets = tv._asset_returns([100.0, 110.0, 99.0])
    assert rets[0] == 0.0
    assert abs(rets[1] - 0.10) < 1e-9 and abs(rets[2] - (-0.10)) < 1e-9
    rvol = [0.0, 0.20, 0.60]  # 60% vol -> target/rvol caps below 1
    pos = tv._positions([True, True, True], [False, False, False], rvol)
    assert pos[0] == 0.0  # rvol 0 -> no size even though long
    assert 0 < pos[1] <= 1.0 and 0 < pos[2] <= 1.0
    assert pos[2] < pos[1]  # higher vol -> smaller position


def test_backtest_flat_series_is_zero_and_uptrend_is_positive() -> None:
    flat = tv.backtest([100.0] * 200, [True] * 200, [False] * 200, ppy=365)
    assert flat["total_return_pct"] == 0.0
    assert flat["max_drawdown_pct"] == 0.0

    # Oscillating uptrend (+1% / -0.5%): real volatility so vol-targeting can size it,
    # net upward so an always-long position makes money.
    closes = [100.0]
    for i in range(399):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 0.995))
    up = tv.backtest(closes, [True] * 400, [False] * 400, ppy=365)
    assert up["total_return_pct"] > 0
    assert up["max_drawdown_pct"] <= 0
    assert up["bars"] == 400 and "returns" in up and len(up["returns"]) == 400


def test_trend_cluster_excludes_mean_reversion() -> None:
    assert "EXT-GOLDEN-CROSS" in tv.TREND_IDS  # trend included
    assert "EXT-BB-REVERSION" not in tv.TREND_IDS  # mean-reversion excluded
    assert "EXT-CONNORS-RSI2" not in tv.TREND_IDS
