"""Checks for the basis-aware funding carry (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_funding_carry_basis as fcb  # noqa: E402


def test_timestamp_unit_and_period() -> None:
    ms = 1_609_459_200_000  # 2021-01-01 00:00 UTC in ms
    us = ms * 1000  # same instant in µs (Amendment A1)
    assert fcb._to_ms(ms) == ms and fcb._to_ms(us) == ms
    assert fcb._period(ms) == fcb._period(us)  # both map to the same 8h bucket
    assert fcb._period(ms + fcb.EIGHT_H_MS) == fcb._period(ms) + 1


def test_carry_return_is_funding_plus_basis() -> None:
    # spot and perp move identically -> basis term is 0 -> return == funding.
    d = {"spot": [100.0, 110.0], "perp": [100.0, 110.0], "fund": [None, 0.0003]}
    assert abs(fcb._carry_return(d, 1) - 0.0003) < 1e-12
    # perp rises MORE than spot -> short-perp loses on the basis, cutting the carry.
    d2 = {"spot": [100.0, 110.0], "perp": [100.0, 112.0], "fund": [None, 0.0003]}
    r = fcb._carry_return(d2, 1)
    assert r < 0.0003  # basis divergence eats into the funding


def test_carry_return_none_on_missing_data() -> None:
    d = {"spot": [None, 110.0], "perp": [100.0, 110.0], "fund": [None, 0.0003]}
    assert fcb._carry_return(d, 1) is None
