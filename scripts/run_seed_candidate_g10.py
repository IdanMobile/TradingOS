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
    probability_of_backtest_overfitting,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "validation" / "seed_candidates"
ARTIFACT = OUT / "SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json"
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


def _independent_pbo(matrix: list[list[float]]) -> dict[str, float | int]:
    from math import log

    split_size = len(matrix[0]) // 2
    trial_count = len(matrix)
    logits: list[float] = []
    for test_columns in combinations(range(len(matrix[0])), split_size):
        test = set(test_columns)
        train_columns = [index for index in range(len(matrix[0])) if index not in test]
        train_scores = [mean(row[index] for index in train_columns) for row in matrix]
        selected = max(range(trial_count), key=lambda index: (train_scores[index], -index))
        test_scores = [mean(row[index] for index in test) for row in matrix]
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
) -> dict[str, float]:
    count = len(sharpes)
    sharpe_variance = variance(sharpes) if count > 1 else 0.0
    euler_gamma = 0.5772156649015329
    natural_e = 2.718281828459045
    if count == 1 or sharpe_variance == 0:
        threshold = 0.0
    else:
        threshold = sqrt(sharpe_variance) * (
            (1 - euler_gamma) * _normal_inv_cdf(1 - 1 / count)
            + euler_gamma * _normal_inv_cdf(1 - 1 / (count * natural_e))
        )
    adjustment = 1 - skewness * threshold + ((kurtosis - 1) / 4) * threshold**2
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


def _trial_returns(candles: dict[str, list[Decimal]], trial_key: str) -> TrialReturns:
    returns, trades, final_equity = _bar_returns_for_trial(candles, trial_key)
    slice_length = len(returns) // SLICE_COUNT
    sliced = [
        returns[index * slice_length : (index + 1) * slice_length] for index in range(SLICE_COUNT)
    ]
    sharpe, skew, kurtosis = _moments(returns)
    return TrialReturns(
        trial_key=trial_key,
        total_return=float(final_equity / Decimal("1000") - Decimal("1")),
        trades=trades,
        slice_mean_returns=[mean(chunk) for chunk in sliced],
        sharpe_per_bar=sharpe,
        returns_skewness=skew,
        returns_kurtosis=kurtosis,
    )


def build_report() -> dict[str, Any]:
    candles = seed.load_candles(seed.DATASETS[DATASET])
    trial_keys = [f"window={window}" for window in seed.QC2_WINDOW]
    trials = [_trial_returns(candles, trial_key) for trial_key in trial_keys]
    matrix = [trial.slice_mean_returns for trial in trials]
    sharpes = [trial.sharpe_per_bar for trial in trials]
    selected = next(trial for trial in trials if trial.trial_key == SELECTED_TRIAL_KEY)
    primary_pbo = probability_of_backtest_overfitting(matrix)
    independent_pbo = _independent_pbo(matrix)
    pbo_delta = abs(float(primary_pbo["pbo"]) - float(independent_pbo["pbo"]))
    sharpe_variance = sharpe_variance_from_trials(sharpes)
    primary_dsr = deflated_sharpe_ratio(
        observed_sharpe=selected.sharpe_per_bar,
        sharpe_variance=sharpe_variance,
        independent_trials=len(trials),
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
    )
    dsr_delta = max(
        abs(primary_dsr[key] - independent_dsr[key])
        for key in ("expected_maximum_noise_sharpe", "z_score", "dsr")
    )
    pass_rule = (
        float(primary_dsr["dsr"]) >= DSR_PASS_MINIMUM
        and float(primary_pbo["pbo"]) <= PBO_PASS_MAXIMUM
    )
    return {
        "schema": "tios-seed-candidate-g10-v1",
        "candidate_id": CANDIDATE_ID,
        "dataset": DATASET,
        "selected_trial_key": SELECTED_TRIAL_KEY,
        "status": "COMPLETE",
        "g10_gate_status": "PASS_REQUIRES_REVIEW" if pass_rule else "FAIL",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "trial_count": len(trials),
        "slice_count": SLICE_COUNT,
        "selection_procedure": "max total_return over declared QC2 window grid",
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
