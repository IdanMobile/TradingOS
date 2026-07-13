"""Offline checks for the carry robustness sweep (no files, no network)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_funding_carry_basis as fcb  # noqa: E402
import scripts.run_funding_carry_robustness as rob  # noqa: E402


def test_period_year_maps_to_calendar() -> None:
    # 2021-01-01 00:00 UTC -> 8h period index; must resolve back to year 2021.
    p = int(datetime(2021, 6, 1, tzinfo=UTC).timestamp() * 1000) // fcb.EIGHT_H_MS
    assert rob._period_year(p) == 2021
    p2 = int(datetime(2023, 3, 1, tzinfo=UTC).timestamp() * 1000) // fcb.EIGHT_H_MS
    assert rob._period_year(p2) == 2023


def test_bucket_by_year_partitions_all_periods() -> None:
    periods = [
        int(datetime(y, 6, 1, tzinfo=UTC).timestamp() * 1000) // fcb.EIGHT_H_MS
        for y in (2021, 2021, 2022, 2023)
    ]
    strat = [0.1, 0.2, 0.3, 0.4]
    buckets = rob.bucket_by_year(periods, strat)
    assert buckets[2021] == [0.1, 0.2] and buckets[2022] == [0.3] and buckets[2023] == [0.4]
    assert sum(len(v) for v in buckets.values()) == len(strat)  # nothing dropped


def test_counterparty_stress_full_haircut_is_unrecoverable() -> None:
    rows = rob.counterparty_stress(full_total_return_pct=50.0, ann_return_pct=8.0)
    by_h = {r["haircut_pct"]: r for r in rows}
    assert by_h[100.0]["recover"] == "UNRECOVERABLE"
    assert by_h[100.0]["terminal_loss_pct"] == -100.0
    # a 10% haircut is recoverable in finite years at a positive carry rate.
    assert by_h[10.0]["recover"].startswith("~") and by_h[10.0]["terminal_loss_pct"] == -10.0


def test_stress_unrecoverable_when_carry_nonpositive() -> None:
    rows = rob.counterparty_stress(full_total_return_pct=-5.0, ann_return_pct=-1.0)
    assert all(r["recover"] == "UNRECOVERABLE" for r in rows)
