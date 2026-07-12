"""Smoke check for the market-character profile over the real frozen dataset.

Descriptive-stats logic (loops over 1.6M rows) has no small fixture, so this
asserts the derived metrics land in sane ranges for all six coin/timeframe tables.
A regression that zeroes volatility, inverts drawdown, or breaks the buy-pressure
ratio fails here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.data_profile as dp  # noqa: E402


def test_profile_metrics_are_sane_for_every_table() -> None:
    report = dp.build_report()
    profiles = report["profiles"]
    assert len(profiles) == len(dp.INSTRUMENTS) * len(dp.TIMEFRAMES)
    for p in profiles:
        assert p["bars"] > 10_000
        assert p["annualized_vol_pct"] > 0  # crypto is never zero-vol
        assert p["avg_atr_pct"] > 0
        assert p["avg_daily_usd_volume_musd"] > 0  # BTC/ETH are deeply liquid
        assert p["median_trades_per_bar"] > 0
        assert 0 < p["avg_buy_pressure_pct"] < 100  # a fraction of volume, in percent
        assert p["price_max_drawdown_pct"] < 0  # drawdown is a loss, always negative
