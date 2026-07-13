"""Offline checks for the funding-carry regime filter (no files, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_funding_carry_regime_filter as rf  # noqa: E402
import scripts.run_funding_carry_s3_paper as cp  # noqa: E402


def _toy() -> dict[str, dict[str, list[float | None]]]:
    flat = [100.0] * 15
    return {
        "AAA": {"spot": flat[:], "perp": flat[:], "fund": [0.0002] * 15},
        "BBB": {"spot": flat[:], "perp": flat[:], "fund": [-0.0005] * 7 + [0.0005] * 8},
    }


def test_always_on_gate_reproduces_base_walk() -> None:
    data = _toy()
    gated = rf.regime_gated_walk(
        data,
        threshold=0.0,
        lookback=3,
        rebalance=3,
        toggle_cost=cp.PAPER_TOGGLE_COST,
        deploy_lookback=1,
        deploy_threshold=-1.0,
    )
    base, _, _ = cp.carry_walk(data, 0.0, 3, 3, cp.PAPER_TOGGLE_COST)
    assert gated == base  # always-on gate is a no-op


def test_impossible_regime_threshold_stands_flat() -> None:
    data = _toy()
    # A deploy threshold no funding regime can clear -> never deploy -> all-zero returns.
    gated = rf.regime_gated_walk(
        data,
        threshold=0.0,
        lookback=3,
        rebalance=3,
        toggle_cost=cp.PAPER_TOGGLE_COST,
        deploy_lookback=3,
        deploy_threshold=1.0,
    )
    assert all(r == 0.0 for r in gated)


def test_gate_reduces_exposure_vs_base() -> None:
    data = _toy()
    base, _, _ = cp.carry_walk(data, 0.0, 3, 3, cp.PAPER_TOGGLE_COST)
    gated = rf.regime_gated_walk(
        data,
        threshold=0.0,
        lookback=3,
        rebalance=3,
        toggle_cost=cp.PAPER_TOGGLE_COST,
        deploy_lookback=3,
        deploy_threshold=0.0001,  # only deploy in strong-funding regimes
    )
    assert sum(1 for r in gated if r != 0.0) <= sum(1 for r in base if r != 0.0)
