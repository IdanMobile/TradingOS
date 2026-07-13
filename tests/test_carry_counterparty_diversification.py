"""Offline checks for the carry counterparty-diversification model (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_carry_counterparty_diversification as cd  # noqa: E402


def test_single_venue_default_is_unrecoverable() -> None:
    row = cd.diversification_row(k=1, p=0.05, ann_return_pct=8.0)
    assert row["single_default_loss_pct"] == 100.0
    assert row["single_default_recover_years"] == "UNRECOVERABLE"
    assert row["all_venues_default_prob"] == 0.05  # p**1


def test_diversification_bounds_single_default_and_shrinks_wipeout() -> None:
    row = cd.diversification_row(k=4, p=0.05, ann_return_pct=8.0)
    assert row["single_default_loss_pct"] == 25.0  # 1/4
    assert isinstance(row["single_default_recover_years"], float)  # recoverable now
    assert abs(row["all_venues_default_prob"] - 0.05**4) < 1e-9  # p**4, tiny


def test_expected_drag_is_independent_of_venue_count() -> None:
    # E[loss] = k * p * (1/k) = p — diversification does not change the mean, only the tail.
    drags = {cd.diversification_row(k, 0.05, 8.0)["expected_annual_counterparty_drag_pct"]
             for k in (1, 2, 3, 4, 5)}  # fmt: skip
    assert drags == {5.0}


def test_years_to_recover_monotonic_and_capped() -> None:
    assert cd.years_to_recover(1.0, 8.0) == "UNRECOVERABLE"
    assert cd.years_to_recover(0.5, 0.0) == "UNRECOVERABLE"  # no carry -> cannot recover
    y25 = cd.years_to_recover(0.25, 8.0)
    y50 = cd.years_to_recover(0.50, 8.0)
    assert isinstance(y25, float) and isinstance(y50, float) and y50 > y25
