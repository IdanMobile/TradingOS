#!/usr/bin/env python3
"""Run G10-style PBO/DSR evidence for the top D-040 seed context.

The retained validation probe found one surviving positive proxy context:
STRAT-QC2-donchian-breakout on ETHUSDT_1h, selected from the declared QC2 window
grid. This script evaluates that searched population with the same local G10
methods used for baseline candidates. It approves nothing and enables no
execution path.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from itertools import combinations
from math import erf, sqrt
from pathlib import Path
from statistics import mean, variance
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_seed_research_cycle_v0 as seed  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    implied_independent_trials,
    probability_of_backtest_overfitting_from_return_statistics,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "validation" / "seed_candidates"
ARTIFACT = OUT / "SEED_G10_QC2_ETHUSDT_1H_2026_07_13.json"
SOURCE_CYCLE = (
    ROOT
    / "artifacts/research_lab/seed_cycle_v0"
    / "SEEDCYCLE-9b1652a62996fda4b753c6695f43569ab860acd8decb48c9c5994566f4a6488f"
    / "cycle_run.json"
)
DATASET = "ETHUSDT_1h"
CANDIDATE_ID = "STRAT-QC2-donchian-breakout"
SELECTED_TRIAL_KEY = "window=40"
SLICE_COUNT = 16
PBO_PASS_MAXIMUM = 0.5
DSR_PASS_MINIMUM = 0.95


@dataclass(frozen=True)
class TrialReturns:
    trial_key: str
    total_return: float
    trades: int
    slice_mean_returns: list[float]
    slice_return_statistics: list[list[float]]
    sharpe_per_bar: float
    returns_skewness: float
    returns_kurtosis: float


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _normal_inv_cdf(probability: float) -> float:
    low, high = -40.0, 40.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if _normal_cdf(middle) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _sharpe_from_statistics(statistics: list[list[float]]) -> float:
    count = sum(int(item[0]) for item in statistics)
    total = sum(float(item[1]) for item in statistics)
    squares = sum(float(item[2]) for item in statistics)
    if count < 2:
        raise ValueError("invalid retained return statistics")
    sample_variance = (squares - total * total / count) / (count - 1)
    if sample_variance <= 0:
        raise ValueError("invalid retained return statistics")
    return (total / count) / sqrt(sample_variance)


def _independent_pbo(matrix: list[list[list[float]]]) -> dict[str, float | int]:
    from math import log

    split_size = len(matrix[0]) // 2
    trial_count = len(matrix)
    logits: list[float] = []
    for test_columns in combinations(range(len(matrix[0])), split_size):
        test = set(test_columns)
        train_columns = [index for index in range(len(matrix[0])) if index not in test]
        train_scores = [
            _sharpe_from_statistics([row[index] for index in train_columns]) for row in matrix
        ]
        selected = max(range(trial_count), key=lambda index: (train_scores[index], -index))
        test_scores = [_sharpe_from_statistics([row[index] for index in test]) for row in matrix]
        selected_test_score = test_scores[selected]
        rank = 1 + sum(score < selected_test_score for score in test_scores)
        omega = rank / (trial_count + 1)
        logits.append(log(omega) - log(1.0 - omega))
    return {
        "split_count": len(logits),
        "pbo": sum(value <= 0 for value in logits) / len(logits),
        "mean_logit": mean(logits),
    }


def _independent_dsr(
    observed_sharpe: float,
    sharpes: list[float],
    sample_count: int,
    skewness: float,
    kurtosis: float,
    independent_trial_count: float | None = None,
) -> dict[str, float]:
    raw_count = len(sharpes)
    count = independent_trial_count if independent_trial_count is not None else float(raw_count)
    sharpe_variance = variance(sharpes) if raw_count > 1 else 0.0
    euler_gamma = 0.5772156649015329
    natural_e = 2.718281828459045
    if count == 1 or sharpe_variance == 0:
        threshold = 0.0
    else:
        threshold = sqrt(sharpe_variance) * (
            (1 - euler_gamma) * _normal_inv_cdf(1 - 1 / count)
            + euler_gamma * _normal_inv_cdf(1 - 1 / (count * natural_e))
        )
    adjustment = 1 - skewness * observed_sharpe + ((kurtosis - 1) / 4) * observed_sharpe**2
    z_score = (observed_sharpe - threshold) * sqrt(sample_count - 1) / sqrt(adjustment)
    return {
        "expected_maximum_noise_sharpe": threshold,
        "z_score": z_score,
        "dsr": _normal_cdf(z_score),
    }


def _bar_returns_for_trial(
    candles: dict[str, list[Decimal]], trial_key: str
) -> tuple[list[float], int, Decimal]:
    window = int(trial_key.split("=")[1])
    close, opens, high, low = candles["close"], candles["open"], candles["high"], candles["low"]
    entries: list[bool] = []
    exits: list[bool] = []
    for index, price in enumerate(close):
        if index < window:
            entries.append(False)
            exits.append(False)
            continue
        entries.append(price > max(high[index - window : index]))
        exits.append(price < min(low[index - window : index]))

    cash = Decimal("1000")
    quantity = Decimal("0")
    equity_curve: list[Decimal] = [cash]
    trades = 0
    for signal_index in range(len(opens) - 1):
        price = opens[signal_index + 1]
        if quantity == 0 and entries[signal_index]:
            quantity = (cash * (Decimal("1") - seed.FEES)) / price
            cash = Decimal("0")
            trades += 1
        elif quantity > 0 and exits[signal_index]:
            cash = quantity * price * (Decimal("1") - seed.FEES)
            quantity = Decimal("0")
            trades += 1
        equity = cash if quantity == 0 else quantity * price * (Decimal("1") - seed.FEES)
        equity_curve.append(equity)
    if len(equity_curve) < len(opens):
        final = cash if quantity == 0 else quantity * opens[-1] * (Decimal("1") - seed.FEES)
        equity_curve.append(final)
    bar_returns = [
        float(equity_curve[index] / equity_curve[index - 1] - Decimal("1"))
        if equity_curve[index - 1] != 0
        else 0.0
        for index in range(1, len(equity_curve))
    ]
    final_equity = equity_curve[-1]
    return bar_returns, trades, final_equity


def _moments(values: list[float]) -> tuple[float, float, float]:
    avg = mean(values)
    centered = [value - avg for value in values]
    if len(values) < 2:
        return 0.0, 0.0, 3.0
    sample_variance = sum(value * value for value in centered) / (len(values) - 1)
    std = sqrt(sample_variance)
    if std == 0:
        return 0.0, 0.0, 3.0
    skew = sum(value**3 for value in centered) / len(values) / (std**3)
    kurtosis = sum(value**4 for value in centered) / len(values) / (std**4)
    sharpe = avg / std
    return sharpe, skew, kurtosis


def _trial_returns(
    candles: dict[str, list[Decimal]], trial_key: str
) -> tuple[TrialReturns, list[float]]:
    returns, trades, final_equity = _bar_returns_for_trial(candles, trial_key)
    slice_length = len(returns) // SLICE_COUNT
    sliced = [
        returns[index * slice_length : (index + 1) * slice_length] for index in range(SLICE_COUNT)
    ]
    sharpe, skew, kurtosis = _moments(returns)
    return (
        TrialReturns(
            trial_key=trial_key,
            total_return=float(final_equity / Decimal("1000") - Decimal("1")),
            trades=trades,
            slice_mean_returns=[mean(chunk) for chunk in sliced],
            slice_return_statistics=[
                [len(chunk), sum(chunk), sum(value * value for value in chunk)] for chunk in sliced
            ],
            sharpe_per_bar=sharpe,
            returns_skewness=skew,
            returns_kurtosis=kurtosis,
        ),
        returns,
    )


def _pairwise_correlations(return_series: list[list[float]]) -> list[float]:
    correlations: list[float] = []
    for left, right in combinations(return_series, 2):
        left_mean, right_mean = mean(left), mean(right)
        numerator = sum(
            (left_value - left_mean) * (right_value - right_mean)
            for left_value, right_value in zip(left, right, strict=True)
        )
        left_scale = sqrt(sum((value - left_mean) ** 2 for value in left))
        right_scale = sqrt(sum((value - right_mean) ** 2 for value in right))
        if left_scale == 0 or right_scale == 0:
            raise ValueError("trial-return correlation is undefined")
        correlations.append(numerator / (left_scale * right_scale))
    return correlations


def build_report() -> dict[str, Any]:
    source_cycle = json.loads(SOURCE_CYCLE.read_text())
    if source_cycle.get("status") != "COMPLETED":
        raise RuntimeError("source seed cycle is incomplete")
    candles = seed.load_candles(seed.DATASETS[DATASET])
    trial_keys = [f"window={window}" for window in seed.QC2_WINDOW]
    trial_outputs = [_trial_returns(candles, trial_key) for trial_key in trial_keys]
    trials = [trial for trial, _ in trial_outputs]
    return_series = [returns for _, returns in trial_outputs]
    matrix = [trial.slice_return_statistics for trial in trials]
    sharpes = [trial.sharpe_per_bar for trial in trials]
    selected = next(trial for trial in trials if trial.trial_key == SELECTED_TRIAL_KEY)
    selected_by_declared_metric = max(trials, key=lambda trial: trial.sharpe_per_bar)
    if selected_by_declared_metric.trial_key != SELECTED_TRIAL_KEY:
        raise RuntimeError("selected trial does not match declared Sharpe argmax")
    primary_pbo = probability_of_backtest_overfitting_from_return_statistics(matrix)
    independent_pbo = _independent_pbo(matrix)
    pbo_delta = abs(float(primary_pbo["pbo"]) - float(independent_pbo["pbo"]))
    pairwise_correlations = _pairwise_correlations(return_series)
    average_correlation = mean(pairwise_correlations)
    effective_trials = implied_independent_trials(len(trials), average_correlation)
    sharpe_variance = sharpe_variance_from_trials(sharpes)
    primary_dsr = deflated_sharpe_ratio(
        observed_sharpe=selected.sharpe_per_bar,
        sharpe_variance=sharpe_variance,
        independent_trials=effective_trials,
        sample_count=len(candles["open"]) - 1,
        skewness=selected.returns_skewness,
        kurtosis=selected.returns_kurtosis,
    )
    independent_dsr = _independent_dsr(
        selected.sharpe_per_bar,
        sharpes,
        len(candles["open"]) - 1,
        selected.returns_skewness,
        selected.returns_kurtosis,
        effective_trials,
    )
    dsr_delta = max(
        abs(primary_dsr[key] - independent_dsr[key])
        for key in ("expected_maximum_noise_sharpe", "z_score", "dsr")
    )
    numeric_passed = (
        float(primary_dsr["dsr"]) >= DSR_PASS_MINIMUM
        and float(primary_pbo["pbo"]) <= PBO_PASS_MAXIMUM
    )
    return {
        "schema": "tios-seed-candidate-g10-v2",
        "candidate_id": CANDIDATE_ID,
        "dataset": DATASET,
        "selected_trial_key": SELECTED_TRIAL_KEY,
        "status": "COMPLETE",
        "g10_gate_status": "METHOD_BLOCKED",
        "numeric_verdict": "PASS" if numeric_passed else "FAIL",
        "promotion_verdict": "METHOD_BLOCKED",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "trial_count": len(trials),
        "raw_trial_count": len(trials),
        "effective_independent_trials": effective_trials,
        "independent_trials_basis": "DSR_2014_APPENDIX_3_AVERAGE_RETURN_CORRELATION",
        "effective_independent_trials_scope": "RETAINED_QC2_WINDOW_GRID_ONLY",
        "average_trial_return_correlation": average_correlation,
        "return_correlation_observation_count": len(return_series[0]),
        "return_correlations_upper_triangle": pairwise_correlations,
        "search_lineage_complete": False,
        "declared_selection_metric": "non_annualized_per_bar_sharpe",
        "pbo_slice_metric": "non_annualized_per_bar_sharpe",
        "dsr_metric": "sharpe_per_bar",
        "selection_metrics_aligned": True,
        "slice_count": SLICE_COUNT,
        "selection_procedure": "max full-sample non-annualized per-bar Sharpe over QC2 window grid",
        "method_sources": {
            "dsr": "https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf",
            "pbo": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
            "retrieved_at_utc": "2026-07-13",
        },
        "search_lineage": {
            "status": "INCOMPLETE",
            "retained_stages": [
                {
                    "stage": "multi-candidate multi-dataset seed cycle",
                    "raw_trial_count": source_cycle["counts"]["trials"],
                    "source": str(SOURCE_CYCLE.relative_to(ROOT)),
                },
                {
                    "stage": "QC2 ETHUSDT_1h window grid",
                    "raw_trial_count": len(trials),
                },
            ],
            "missing_stages": [
                "a governed rule for shortlisting the three positive proxy contexts",
                "return-correlation evidence and one selection metric across all 258 trials",
            ],
            "hierarchy_effective_independent_trials": None,
        },
        "trials": [asdict(trial) for trial in trials],
        "pbo": {
            "primary": {"pbo": primary_pbo["pbo"], "split_count": primary_pbo["split_count"]},
            "independent": independent_pbo,
            "max_abs_delta": pbo_delta,
        },
        "dsr": {
            "primary": primary_dsr,
            "independent": independent_dsr,
            "max_abs_delta": dsr_delta,
        },
        "verdict_rule": (
            f"PASS requires DSR >= {DSR_PASS_MINIMUM} and PBO <= {PBO_PASS_MAXIMUM}; "
            "PASS_REQUIRES_REVIEW remains NOT_ELIGIBLE until stats-specialist review and "
            "all other validation gates pass"
        ),
        "effect": "Approves no strategy, selects no winner, and enables no execution path.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_report()
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(ARTIFACT.relative_to(ROOT)),
                "status": payload["g10_gate_status"],
            }
        )
    )


if __name__ == "__main__":
    main()
