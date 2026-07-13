"""Offline checks for multi-timeframe confluence (alignment causality + gating)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scripts.run_mtf_confluence as mtf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_align_trend_is_causal_no_lookahead() -> None:
    # Daily bars open on day 1/2/3 with trend [down, up, up]; a daily bar is only usable AFTER it
    # closes (next day 00:00). An hour must never see the still-forming day's trend.
    hi_times = [datetime(2021, 1, 1), datetime(2021, 1, 2), datetime(2021, 1, 3)]
    hi_up = [False, True, True]
    lo_times = [
        datetime(2021, 1, 1, 12),  # day1 forming -> no daily closed yet -> default False
        datetime(2021, 1, 2, 12),  # day1 has closed -> use day1's trend (False), NOT day2's
        datetime(2021, 1, 3, 12),  # day2 has closed -> use day2's trend (True)
        datetime(2021, 1, 4, 0),  # day3 has closed -> use day3's trend (True)
    ]
    assert mtf.align_trend(lo_times, hi_times, hi_up) == [False, False, True, True]


def test_mtf_signals_gate_entries_on_higher_trend() -> None:
    lo = {"close": [Decimal(1), Decimal(2), Decimal(3)]}
    builder = lambda _c: ([True, True, True], [False, False, False])  # noqa: E731
    entries, exits = mtf.mtf_signals(lo, [True, False, True], builder)
    assert entries == [True, False, True]  # entry only when the higher-TF trend is up
    assert exits == [False, True, False]  # exit forced when the higher-TF trend flips down


def test_daily_trend_up_flags_price_above_sma() -> None:
    candles = {
        "close": [Decimal(str(c)) for c in [10, 10, 10, 20]]
    }  # last bar jumps above the mean
    up = mtf.daily_trend_up(candles, sma_w=3)
    assert up[-1] is True and up[0] is False  # warmup is False, final close > SMA3 is True


def test_retained_mtf_report_cannot_claim_g10_pass() -> None:
    report = json.loads(
        (ROOT / "artifacts/research_lab/mtf_confluence/MTF_CONFLUENCE.json").read_text()
    )
    assert report["g10_dsr"]["status"] == "NOT_RUN_METHOD_INVALID"
    assert report["g10_dsr"]["verdict"] == "NOT_RUN"
    assert report["g10_dsr"]["verdict_is_genuine"] is False
    assert report["g10_dsr"]["raw_strategy_pair_search_bound"] == 36
    assert "oos_dsr" not in report["out_of_sample"]
    assert report["out_of_sample"]["promotion_eligible"] is False
    assert "oos_psr_vs_zero" in report["out_of_sample"]
