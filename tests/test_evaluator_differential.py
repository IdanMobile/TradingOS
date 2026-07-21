"""Differential test of the D-112 campaign evaluator vs an independent implementation.

Runs the same synthetic fixtures through the project's campaign evaluator (trade-return builder
+ significance scorer) and a from-spec independent re-implementation, and asserts agreement on
per-trade P&L, trade counts, and summary statistics within tight tolerances. Also locks in the
F1 regression: the fail-closed sample_count guard must reject the pre-D-112 inflated bar count.

Scope: pure offline evaluation. No threshold or verdict is changed here (the audit's residual
follow-up is single-implementation risk, not the statistics themselves).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_evaluator_differential_test as diff  # noqa: E402
import run_first_budgeted_campaign as fb  # noqa: E402

from tios.validation.campaign import CampaignError, score_trade_significance  # noqa: E402


@pytest.mark.parametrize("fixture", diff.build_pnl_fixtures(), ids=lambda fx: fx["name"])
def test_trade_return_builder_matches_independent(fixture: dict[str, Any]) -> None:
    result = diff.compare_pnl_fixture(fixture)
    assert result["agree"], result["checks"]
    # Trade count is the exact quantity F1 mis-fed to the DSR; assert it three ways.
    assert (
        result["project"]["trade_count"]
        == result["independent"]["trade_count"]
        == len(fixture["expected_trade_returns"])
    )
    assert result["max_abs_diff"]["per_trade_pnl_vs_ground_truth"] <= diff.PNL_TOL
    assert result["max_abs_diff"]["per_trade_pnl_vs_independent"] <= diff.PNL_TOL


def test_significance_scorer_matches_independent() -> None:
    result = diff.compare_significance_fixture(diff.build_significance_fixture())
    assert result["agree"], result["checks"]
    assert result["max_abs_diff"]["z_score"] <= diff.STAT_TOL
    assert result["max_abs_diff"]["dsr"] <= diff.STAT_TOL


def test_f1_guard_rejects_inflated_sample_count() -> None:
    """The core D-112 fix: sample_count must equal the scored trade series length."""
    fixture = diff.build_significance_fixture()
    kwargs = {
        "observed_trade_returns": fixture["observed_trade_returns"],
        "trial_trade_returns": fixture["trial_trade_returns"],
        "trial_bar_returns": fixture["trial_bar_returns"],
        "hierarchy_trials": fixture["hierarchy_trials"],
        "min_validation_trades": 10,
    }
    n_trades = len(fixture["observed_trade_returns"])
    # Honest count is accepted.
    score_trade_significance(sample_count=n_trades, **kwargs)
    # The pre-D-112 inflated bar count is rejected fail-closed.
    with pytest.raises(CampaignError):
        score_trade_significance(sample_count=fixture["inflated_sample_count"], **kwargs)


def test_zero_and_single_trade_edge_cases() -> None:
    fixtures = {fx["name"]: fx for fx in diff.build_pnl_fixtures()}
    zero = fb.evaluate(fixtures["zero_trades"]["bars"], diff.PARAMS)
    single = fb.evaluate(fixtures["single_trade"]["bars"], diff.PARAMS)
    defect = fb.evaluate(fixtures["sample_count_inflation_defect"]["bars"], diff.PARAMS)
    assert len(zero.trade_returns) == 0
    assert len(single.trade_returns) == 1
    # The defect fixture is the F1 geometry: one trade, many bar-returns (bars >> trades).
    assert len(defect.trade_returns) == 1
    assert len(defect.bar_returns) > 100


def test_end_to_end_verdict_is_agreement() -> None:
    evidence = diff.run()
    assert evidence["verdict"] == "AGREEMENT", evidence
