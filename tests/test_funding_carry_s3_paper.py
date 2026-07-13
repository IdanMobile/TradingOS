"""Offline checks for the S3 carry paper-lane execution probe (no files, no network)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_funding_carry_basis as fcb  # noqa: E402
import scripts.run_funding_carry_s3_paper as cp  # noqa: E402


def _toy_data() -> dict[str, dict[str, list[float | None]]]:
    """2 pairs, 15 periods, flat prices (basis 0 -> carry == funding). BBB flips positive
    mid-series so the held set toggles at a rebalance."""
    flat = [100.0] * 15
    return {
        "AAA": {"spot": flat[:], "perp": flat[:], "fund": [0.0002] * 15},
        "BBB": {"spot": flat[:], "perp": flat[:], "fund": [-0.0005] * 7 + [0.0005] * 8},
    }


def test_baseline_walk_reproduces_backtest_exactly() -> None:
    # The honesty anchor: at the backtest's own fee, the probe walk == fcb.backtest.
    data = _toy_data()
    strat, _, _ = cp.carry_walk(data, threshold=0.0, lookback=3, rebalance=3, toggle_cost=fcb.FEE)
    assert strat == fcb.backtest(data, 0.0, 3, 3)


def test_realistic_execution_costs_more_but_same_toggles() -> None:
    data = _toy_data()
    args = (data, 0.0, 3, 3)
    _, bt_fee, bt_toggles = cp.carry_walk(*args, toggle_cost=cp.BACKTEST_TOGGLE_COST)
    _, pp_fee, pp_toggles = cp.carry_walk(*args, toggle_cost=cp.PAPER_TOGGLE_COST)
    assert cp.PAPER_TOGGLE_COST > cp.BACKTEST_TOGGLE_COST
    assert pp_toggles == bt_toggles > 0  # identical signals -> identical fills
    assert pp_fee > bt_fee  # realistic per-leg cost is strictly higher


def test_ledger_reconstructs_net_equity_without_overdraw() -> None:
    ledger = cp.build_ledger(net_equity=Decimal("12000.00"), total_fees=Decimal("34.56"))
    assert len(ledger.entries) == 3  # initial + settlement + fees
    assert ledger.balances[0].amount == Decimal("12000.00")


def test_report_is_static_cost_stress_not_paper_or_g12(monkeypatch) -> None:
    monkeypatch.setattr(cp.fcb, "build_matrix", lambda: (list(range(15)), _toy_data()))
    monkeypatch.setattr(cp, "select_best", lambda _data: (0.0, 3, 3))
    report = cp.build_report()
    assert report["status"] == "STATIC_COST_STRESS_NOT_G12"
    assert report["observed_venue_fills"] is False
    assert report["g12_status"] == "NOT_RUN"
    assert report["paper_lane_qualification"] is False
