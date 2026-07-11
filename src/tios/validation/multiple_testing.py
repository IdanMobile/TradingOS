"""Multiple-testing method fixtures for G10.

These helpers are pure math and do not approve a strategy. They validate the
local PBO/CSCV and DSR formulas against small known-answer fixtures so G10 can
graduate from "method candidate" only when callers also provide retained trial
populations and candidate-specific evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from math import e, isfinite, log, sqrt
from statistics import NormalDist, mean, variance

NORMAL = NormalDist()
EULER_GAMMA = 0.5772156649015329


def probability_of_backtest_overfitting(
    performance_by_trial_slice: Sequence[Sequence[float]],
) -> dict[str, object]:
    """Estimate PBO using combinatorially symmetric cross-validation.

    `performance_by_trial_slice` is trial-major: each row is one strategy/trial,
    each column is one equal-sized time slice, and larger values are better.
    """

    if not performance_by_trial_slice:
        raise ValueError("at least one trial is required")
    slice_count = len(performance_by_trial_slice[0])
    if slice_count < 2 or slice_count % 2:
        raise ValueError("an even number of at least two slices is required")
    if any(len(row) != slice_count for row in performance_by_trial_slice):
        raise ValueError("all trials must have the same slice count")

    trial_count = len(performance_by_trial_slice)
    split_size = slice_count // 2
    lambdas: list[float] = []

    for train_columns in combinations(range(slice_count), split_size):
        train = set(train_columns)
        test_columns = tuple(i for i in range(slice_count) if i not in train)
        train_scores = [mean(row[i] for i in train) for row in performance_by_trial_slice]
        selected = max(range(trial_count), key=lambda i: (train_scores[i], -i))
        test_scores = [mean(row[i] for i in test_columns) for row in performance_by_trial_slice]

        selected_test_score = test_scores[selected]
        rank_from_worst = 1 + sum(score < selected_test_score for score in test_scores)
        omega = rank_from_worst / (trial_count + 1)
        lambdas.append(log(omega / (1 - omega)))

    overfit_count = sum(value <= 0 for value in lambdas)
    return {
        "split_count": len(lambdas),
        "lambda_logits": tuple(lambdas),
        "pbo": overfit_count / len(lambdas),
    }


def expected_maximum_noise_sharpe(
    sharpe_variance: float,
    independent_trials: int,
) -> float:
    """False-strategy-theorem threshold used by DSR."""

    if sharpe_variance < 0 or not isfinite(sharpe_variance):
        raise ValueError("sharpe_variance must be finite and non-negative")
    if independent_trials < 1:
        raise ValueError("independent_trials must be positive")
    if independent_trials == 1 or sharpe_variance == 0:
        return 0.0
    return sqrt(sharpe_variance) * (
        (1 - EULER_GAMMA) * NORMAL.inv_cdf(1 - 1 / independent_trials)
        + EULER_GAMMA * NORMAL.inv_cdf(1 - 1 / (independent_trials * e))
    )


def deflated_sharpe_ratio(
    observed_sharpe: float,
    sharpe_variance: float,
    independent_trials: int,
    sample_count: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> dict[str, float]:
    """Return the DSR confidence and its multiple-testing Sharpe threshold."""

    if sample_count < 2:
        raise ValueError("sample_count must be at least 2")
    sr0 = expected_maximum_noise_sharpe(sharpe_variance, independent_trials)
    variance_adjustment = 1 - skewness * sr0 + ((kurtosis - 1) / 4) * sr0**2
    if variance_adjustment <= 0 or not isfinite(variance_adjustment):
        raise ValueError("invalid skew/kurtosis variance adjustment")
    z_score = (observed_sharpe - sr0) * sqrt(sample_count - 1) / sqrt(variance_adjustment)
    return {
        "expected_maximum_noise_sharpe": sr0,
        "z_score": z_score,
        "dsr": NORMAL.cdf(z_score),
    }


def sharpe_variance_from_trials(sharpes: Sequence[float]) -> float:
    """Cross-sectional sample variance for trial Sharpe ratios."""

    if len(sharpes) < 2:
        return 0.0
    return variance(sharpes)
