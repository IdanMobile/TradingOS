"""Canonical, next-bar-open B2/B3/B4 campaign extractor.

This module is the governed successor to ``g10_returns.py``.  The legacy
extractor remains immutable because it reproduces an older current-close,
crossover-event sweep.  Here the frozen strategy YAML files are the source of
the exact control parameters, while the surrounding grids preserve the prior
research population (plus the missing B2 3/5 control).

The module is deliberately offline: it reads one local Parquet file, runs
vectorbt, and writes JSON.  It has no venue, credential, network, or order path.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numba as nb  # type: ignore[import-not-found]
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/normalized/BTCUSDT_5m.parquet"
SPEC_DIR = ROOT / "fixtures/strategies/baselines"
VALIDATION_OUT = ROOT / "artifacts/validation"
BAR_DELTA = pd.Timedelta(minutes=5)
INIT_CASH = 1000.0
SLICES = 16

# Prior sweep population.  B2 3/5 is appended from the frozen spec because it
# was absent from the legacy grid.
B2_FAST = (2, 3, 5, 8, 10, 15)
B2_SLOW = (10, 20, 30, 40, 50, 60)
B3_WINDOW = (3, 5, 10, 20)
B3_DEVIATION = (0.5, 1.0, 1.5, 2.0)
B4_LOOKBACK = (3, 5, 10, 20)
B4_EXIT_WINDOW = (2, 3, 5, 10)


@dataclass(frozen=True)
class CostScenario:
    scenario: str
    fee_rate_per_side: float
    slippage_bps_per_side: float
    diagnostic_only: bool = False

    @property
    def slippage_fraction(self) -> float:
        return self.slippage_bps_per_side / 10_000.0


COST_SCENARIOS = (
    CostScenario("F0/S0", 0.0, 0.0, diagnostic_only=True),
    CostScenario("F1/S1", 0.001, 1.0),
    CostScenario("F1/S2", 0.001, 5.0),
    CostScenario("F1/S3", 0.001, 10.0),
    CostScenario("F2/S2", 0.0015, 5.0),
    CostScenario("F2/S3", 0.0015, 10.0),
)
PRIMARY_SCENARIO = next(item for item in COST_SCENARIOS if item.scenario == "F1/S1")

SPEC_FILES = {
    "b2": SPEC_DIR / "B2_ma_crossover.yaml",
    "b3": SPEC_DIR / "B3_bollinger_mean_reversion.yaml",
    "b4": SPEC_DIR / "B4_volatility_breakout.yaml",
}


@dataclass(frozen=True)
class TrialDescriptor:
    family: str
    trial_key: str
    parameters: tuple[tuple[str, int | float], ...]
    exact_canonical_control: bool
    structural_zero_trade: bool = False

    def parameter_dict(self) -> dict[str, int | float]:
        return dict(self.parameters)


@dataclass(frozen=True)
class SignalBatch:
    family: str
    descriptors: tuple[TrialDescriptor, ...]
    entries: pd.DataFrame
    exits: pd.DataFrame


@dataclass(frozen=True)
class ExecutionEvents:
    entries: pd.DataFrame
    exits: pd.DataFrame
    ending_held: np.ndarray


@dataclass(frozen=True)
class SimulationResult:
    returns: pd.DataFrame
    total_returns: pd.Series
    trade_counts: pd.Series
    gross_executed_notional: pd.Series
    buy_order_counts: pd.Series
    sell_order_counts: pd.Series
    order_records: pd.DataFrame | None = None


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _one_match(pattern: str, text: str, label: str) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one frozen-spec match, got {len(matches)}")
    return matches[0]


def load_frozen_specs(spec_dir: Path | str = SPEC_DIR) -> dict[str, dict[str, Any]]:
    """Parse and validate the small frozen YAML surface without adding PyYAML.

    The isolated vectorbt environment intentionally contains only its frozen
    numerical dependencies.  Anchored parsing of these three stable fixtures is
    narrower than duplicating a YAML dependency into that environment, and any
    structural or semantic edit fails closed.
    """

    directory = Path(spec_dir)
    paths = {family: directory / path.name for family, path in SPEC_FILES.items()}
    texts = {family: path.read_text(encoding="utf-8") for family, path in paths.items()}

    strategy_ids = {
        family: _one_match(r"^strategy_id: (\S+)$", text, f"{family} strategy_id").group(1)
        for family, text in texts.items()
    }

    b2 = texts["b2"]
    b2_indicators = re.findall(
        r"- name: sma\n\s+parameters: \{window: (\d+), source: close\}"
        r"\n\s+outputs: \[(sma_fast|sma_slow)\]",
        b2,
    )
    if len(b2_indicators) != 2 or {name for _, name in b2_indicators} != {
        "sma_fast",
        "sma_slow",
    }:
        raise RuntimeError("b2: frozen SMA definitions changed")
    b2_windows = {name: int(window) for window, name in b2_indicators}
    for required in ("- sma_fast > sma_slow", "- sma_fast < sma_slow", "next bar open"):
        if required not in b2:
            raise RuntimeError(f"b2: missing canonical rule {required!r}")

    b3 = texts["b3"]
    b3_match = _one_match(
        r"parameters: \{window: (\d+), std_multiplier: ([0-9.]+), ddof: (\d+), source: close\}",
        b3,
        "b3",
    )
    for required in ("- close < lower_band", "- close >= middle_band", "next bar open"):
        if required not in b3:
            raise RuntimeError(f"b3: missing canonical rule {required!r}")
    if int(b3_match.group(3)) != 0:
        raise RuntimeError("b3: canonical population standard deviation must use ddof=0")

    b4 = texts["b4"]
    b4_high = _one_match(
        r"- name: rolling_max\n\s+parameters: \{window: (\d+), shift: (\d+), source: high\}",
        b4,
        "b4 rolling high",
    )
    b4_exit = _one_match(
        r"- name: sma\n\s+parameters: \{window: (\d+), source: close\}\n"
        r"\s+outputs: \[sma_3\]",
        b4,
        "b4 exit SMA",
    )
    for required in ("- close > hh_prev5", "- close < sma_3", "next bar open"):
        if required not in b4:
            raise RuntimeError(f"b4: missing canonical rule {required!r}")
    if int(b4_high.group(2)) != 1:
        raise RuntimeError("b4: rolling high must exclude the current bar with shift=1")

    return {
        "b2": {
            "strategy_id": strategy_ids["b2"],
            "fast": b2_windows["sma_fast"],
            "slow": b2_windows["sma_slow"],
            "spec_file": _relative(paths["b2"]),
        },
        "b3": {
            "strategy_id": strategy_ids["b3"],
            "window": int(b3_match.group(1)),
            "deviation": float(b3_match.group(2)),
            "ddof": int(b3_match.group(3)),
            "spec_file": _relative(paths["b3"]),
        },
        "b4": {
            "strategy_id": strategy_ids["b4"],
            "lookback": int(b4_high.group(1)),
            "exit_window": int(b4_exit.group(1)),
            "shift": int(b4_high.group(2)),
            "spec_file": _relative(paths["b4"]),
        },
    }


def _b3_structurally_impossible(window: int, deviation: float) -> bool:
    # For one observation within a population of n values, the strict maximum
    # standardized distance below the mean is sqrt(n - 1).  At or above that
    # threshold, close < mean - deviation*population_std cannot occur.
    return deviation >= math.sqrt(window - 1)


def build_trial_descriptors(
    specs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, tuple[TrialDescriptor, ...]]:
    specs = specs or load_frozen_specs()
    b2_exact = (int(specs["b2"]["fast"]), int(specs["b2"]["slow"]))
    b2_pairs = [(fast, slow) for fast, slow in product(B2_FAST, B2_SLOW) if fast < slow]
    if b2_exact not in b2_pairs:
        b2_pairs.append(b2_exact)
    b2 = tuple(
        TrialDescriptor(
            family="b2",
            trial_key=f"fast={fast},slow={slow}",
            parameters=(("fast", fast), ("slow", slow)),
            exact_canonical_control=(fast, slow) == b2_exact,
        )
        for fast, slow in b2_pairs
    )

    b3_exact = (int(specs["b3"]["window"]), float(specs["b3"]["deviation"]))
    b3 = tuple(
        TrialDescriptor(
            family="b3",
            trial_key=f"window={window},deviation={deviation:g}",
            parameters=(("window", window), ("deviation", deviation)),
            exact_canonical_control=(window, deviation) == b3_exact,
            structural_zero_trade=_b3_structurally_impossible(window, deviation),
        )
        for window, deviation in product(B3_WINDOW, B3_DEVIATION)
    )

    b4_exact = (int(specs["b4"]["lookback"]), int(specs["b4"]["exit_window"]))
    b4 = tuple(
        TrialDescriptor(
            family="b4",
            trial_key=f"lookback={lookback},exit_window={exit_window}",
            parameters=(("lookback", lookback), ("exit_window", exit_window)),
            exact_canonical_control=(lookback, exit_window) == b4_exact,
        )
        for lookback, exit_window in product(B4_LOOKBACK, B4_EXIT_WINDOW)
    )
    result = {"b2": b2, "b3": b3, "b4": b4}
    if {family: len(items) for family, items in result.items()} != {
        "b2": 35,
        "b3": 16,
        "b4": 16,
    }:
        raise RuntimeError("canonical trial roster must contain 67 trials (35/16/16)")
    return result


def load_candles(dataset_path: Path | str = DATASET) -> pd.DataFrame:
    """Load the frozen numerical candle surface as float64 and validate order."""

    columns = ["timestamp_open_utc", "open", "high", "low", "close"]
    candles = pd.read_parquet(Path(dataset_path), columns=columns).set_index("timestamp_open_utc")
    candles = candles[["open", "high", "low", "close"]].astype("float64")
    if not isinstance(candles.index, pd.DatetimeIndex):
        raise RuntimeError("timestamp_open_utc must be a DatetimeIndex")
    if candles.index.tz is None:
        raise RuntimeError("timestamp_open_utc must be timezone-aware")
    if not candles.index.is_monotonic_increasing or not candles.index.is_unique:
        raise RuntimeError("candles must be unique and strictly time ordered")
    values = candles.to_numpy()
    if len(candles) < 2 or not np.isfinite(values).all() or (values <= 0).any():
        raise RuntimeError("candles must contain at least two finite positive OHLC rows")
    if (candles["high"] < candles[["open", "close", "low"]].max(axis=1)).any():
        raise RuntimeError("candle high is below another OHLC field")
    if (candles["low"] > candles[["open", "close", "high"]].min(axis=1)).any():
        raise RuntimeError("candle low is above another OHLC field")
    return candles


def adjacency_mask(index: pd.DatetimeIndex) -> np.ndarray:
    adjacent = np.zeros(len(index), dtype=np.bool_)
    if len(index) > 1:
        adjacent[1:] = (index[1:] - index[:-1]) == BAR_DELTA
    return adjacent


@nb.njit(cache=False)
def _rolling_mean(values: np.ndarray, adjacent: np.ndarray, window: int) -> np.ndarray:
    result = np.full(values.shape[0], np.nan)
    run_length = 0
    for index in range(values.shape[0]):
        if index == 0 or not adjacent[index]:
            run_length = 1
        else:
            run_length += 1
        if run_length >= window:
            # Windows are at most 60 bars.  Direct summation avoids the
            # long-horizon drift of a years-long add/subtract accumulator.
            total = 0.0
            for offset in range(window):
                total += values[index - offset]
            result[index] = total / window
    return result


@nb.njit(cache=False)
def _rolling_std_population(
    values: np.ndarray, adjacent: np.ndarray, window: int, means: np.ndarray
) -> np.ndarray:
    result = np.full(values.shape[0], np.nan)
    run_length = 0
    for index in range(values.shape[0]):
        if index == 0 or not adjacent[index]:
            run_length = 1
        else:
            run_length += 1
        if run_length >= window:
            squared = 0.0
            for offset in range(window):
                difference = values[index - offset] - means[index]
                squared += difference * difference
            result[index] = math.sqrt(squared / window)
    return result


@nb.njit(cache=False)
def _prior_rolling_max(values: np.ndarray, adjacent: np.ndarray, window: int) -> np.ndarray:
    result = np.full(values.shape[0], np.nan)
    run_length = 0
    for index in range(values.shape[0]):
        if index == 0 or not adjacent[index]:
            run_length = 1
        else:
            run_length += 1
        if run_length >= window + 1:
            maximum = values[index - 1]
            for offset in range(2, window + 1):
                maximum = max(maximum, values[index - offset])
            result[index] = maximum
    return result


def build_raw_signals(
    candles: pd.DataFrame,
    descriptors: Mapping[str, Sequence[TrialDescriptor]] | None = None,
) -> dict[str, SignalBatch]:
    """Build causal close-bar signals, resetting indicator warm-up at every gap."""

    roster = descriptors or build_trial_descriptors()
    close = candles["close"].to_numpy(dtype=np.float64)
    high = candles["high"].to_numpy(dtype=np.float64)
    adjacent = adjacency_mask(candles.index)
    mean_windows = {
        int(value)
        for family in roster.values()
        for item in family
        for name, value in item.parameters
        if name in {"fast", "slow", "window", "exit_window"}
    }
    means = {window: _rolling_mean(close, adjacent, window) for window in mean_windows}
    stds = {
        window: _rolling_std_population(close, adjacent, window, means[window])
        for window in B3_WINDOW
    }
    prior_highs = {
        lookback: _prior_rolling_max(high, adjacent, lookback) for lookback in B4_LOOKBACK
    }

    result: dict[str, SignalBatch] = {}
    for family, family_descriptors in roster.items():
        entries: dict[str, np.ndarray] = {}
        exits: dict[str, np.ndarray] = {}
        for item in family_descriptors:
            parameters = item.parameter_dict()
            if family == "b2":
                fast = means[int(parameters["fast"])]
                slow = means[int(parameters["slow"])]
                # Persistent eligibility state, not a crossover event.
                entries[item.trial_key] = fast > slow
                exits[item.trial_key] = fast < slow
            elif family == "b3":
                window = int(parameters["window"])
                deviation = float(parameters["deviation"])
                middle = means[window]
                if item.structural_zero_trade:
                    entries[item.trial_key] = np.zeros(len(candles), dtype=np.bool_)
                else:
                    lower = middle - deviation * stds[window]
                    entries[item.trial_key] = close < lower
                exits[item.trial_key] = close >= middle
            elif family == "b4":
                lookback = int(parameters["lookback"])
                exit_window = int(parameters["exit_window"])
                entries[item.trial_key] = close > prior_highs[lookback]
                exits[item.trial_key] = close < means[exit_window]
            else:
                raise RuntimeError(f"unknown family {family!r}")
        columns = [item.trial_key for item in family_descriptors]
        result[family] = SignalBatch(
            family=family,
            descriptors=tuple(family_descriptors),
            entries=pd.DataFrame(entries, index=candles.index, columns=columns).fillna(False),
            exits=pd.DataFrame(exits, index=candles.index, columns=columns).fillna(False),
        )
    return result


@nb.njit(cache=False)
def _resolve_transitions(
    raw_entries: np.ndarray,
    raw_exits: np.ndarray,
    adjacent: np.ndarray,
    start_held: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows, columns = raw_entries.shape
    buys = np.zeros((rows, columns), dtype=np.bool_)
    sells = np.zeros((rows, columns), dtype=np.bool_)
    held = start_held.copy()
    # Signal at i-1 may only fill at i.  Hence bar zero cannot fill, a signal on
    # the final bar never fills, and a non-adjacent next row expires the signal.
    for index in range(1, rows):
        if not adjacent[index]:
            continue
        for column in range(columns):
            if held[column]:
                if raw_exits[index - 1, column]:
                    sells[index, column] = True
                    held[column] = False
            elif raw_entries[index - 1, column]:
                buys[index, column] = True
                held[column] = True
    return buys, sells, held


def resolve_transitions(
    batch: SignalBatch,
    *,
    start_held: bool | Sequence[bool] = False,
) -> ExecutionEvents:
    """Resolve raw close signals into mutually exclusive next-open events.

    If entry and exit are simultaneously true, the current state is the tie
    breaker: a flat trial enters and a held trial exits.  Held state carries over
    data gaps, but a pending signal does not.
    """

    column_count = len(batch.descriptors)
    if isinstance(start_held, bool):
        initial = np.full(column_count, start_held, dtype=np.bool_)
    else:
        initial = np.asarray(start_held, dtype=np.bool_)
        if initial.shape != (column_count,):
            raise ValueError("start_held must match the trial count")
    adjacent = adjacency_mask(batch.entries.index)
    buys, sells, ending = _resolve_transitions(
        batch.entries.to_numpy(dtype=np.bool_),
        batch.exits.to_numpy(dtype=np.bool_),
        adjacent,
        initial,
    )
    columns = batch.entries.columns
    return ExecutionEvents(
        entries=pd.DataFrame(buys, index=batch.entries.index, columns=columns),
        exits=pd.DataFrame(sells, index=batch.entries.index, columns=columns),
        ending_held=ending,
    )


def slice_signal_batch(batch: SignalBatch, start: Any, end: Any) -> SignalBatch:
    """Take a raw-signal time slice; callers can then resolve it from flat."""

    return SignalBatch(
        family=batch.family,
        descriptors=batch.descriptors,
        entries=batch.entries.loc[start:end].copy(),
        exits=batch.exits.loc[start:end].copy(),
    )


def simulate_returns(
    candles: pd.DataFrame,
    events: ExecutionEvents,
    scenario: CostScenario = PRIMARY_SCENARIO,
    *,
    include_orders: bool = False,
) -> SimulationResult:
    """Run long-only vectorbt fills at open and value positions at close.

    The last open position is marked at the final close; no synthetic final
    liquidation order is created.  ``events`` should begin flat (the governed
    campaign and all walk-forward tests do).
    """

    if not candles.index.equals(events.entries.index) or not events.entries.index.equals(
        events.exits.index
    ):
        raise ValueError("candles and execution events must share one index")
    portfolio = vbt.Portfolio.from_signals(
        candles["close"],
        events.entries,
        events.exits,
        price=candles["open"],
        open=candles["open"],
        high=candles["high"],
        low=candles["low"],
        fees=scenario.fee_rate_per_side,
        slippage=scenario.slippage_fraction,
        init_cash=INIT_CASH,
        direction="longonly",
        accumulate=False,
        freq=BAR_DELTA,
    )
    returns = pd.DataFrame(portfolio.returns(), index=candles.index)
    returns.columns = events.entries.columns
    totals = pd.Series(portfolio.total_return(), index=events.entries.columns, dtype="float64")
    trades = pd.Series(portfolio.trades.count(), index=events.entries.columns, dtype="int64")
    raw_orders = portfolio.orders.records
    column_count = len(events.entries.columns)
    gross = np.bincount(
        raw_orders["col"].to_numpy(dtype=np.int64),
        weights=(raw_orders["size"] * raw_orders["price"]).to_numpy(dtype=np.float64),
        minlength=column_count,
    )
    sides = raw_orders["side"].to_numpy(dtype=np.int64)
    columns = raw_orders["col"].to_numpy(dtype=np.int64)
    buys = np.bincount(columns[sides == 0], minlength=column_count)
    sells = np.bincount(columns[sides == 1], minlength=column_count)
    gross_notional = pd.Series(gross, index=events.entries.columns, dtype="float64")
    buy_counts = pd.Series(buys, index=events.entries.columns, dtype="int64")
    sell_counts = pd.Series(sells, index=events.entries.columns, dtype="int64")
    orders = pd.DataFrame(portfolio.orders.records_readable) if include_orders else None
    return SimulationResult(
        returns,
        totals,
        trades,
        gross_notional,
        buy_counts,
        sell_counts,
        orders,
    )


def _finite_shape_statistics(series: pd.Series) -> tuple[float, float]:
    deviation = float(series.std(ddof=1))
    if not math.isfinite(deviation) or deviation <= 0:
        return 0.0, 3.0
    skewness = float(series.skew())
    kurtosis = float(series.kurt()) + 3.0
    return skewness, kurtosis


def _statistics_payload(
    returns: pd.DataFrame,
    totals: pd.Series,
    trades: pd.Series,
    descriptors: Sequence[TrialDescriptor],
) -> dict[str, Any]:
    bar_count = len(returns)
    slice_length = bar_count // SLICES
    if slice_length < 2:
        raise RuntimeError(f"at least {SLICES * 2} bars are required for G10 slices")
    used = returns.iloc[: slice_length * SLICES]
    labels = np.arange(len(used)) // slice_length
    slice_sums = used.groupby(labels).sum()
    slice_sums_squared = (used * used).groupby(labels).sum()
    means = returns.mean()
    deviations = returns.std(ddof=1)
    rows: list[dict[str, Any]] = []
    for item in descriptors:
        key = item.trial_key
        deviation = float(deviations[key])
        sharpe = float(means[key]) / deviation if deviation > 0 else 0.0
        skewness, kurtosis = _finite_shape_statistics(returns[key])
        rows.append(
            {
                "trial_key": key,
                "family": item.family,
                "parameters": item.parameter_dict(),
                "exact_canonical_control": item.exact_canonical_control,
                "structural_zero_trade_retained": item.structural_zero_trade,
                "status": "COMPLETED",
                "total_return": float(totals[key]),
                "trades": int(trades[key]),
                "sharpe_per_bar": sharpe,
                "slice_mean_returns": [
                    float(slice_sums.loc[index, key]) / slice_length for index in range(SLICES)
                ],
                "slice_return_statistics": [
                    [
                        slice_length,
                        float(slice_sums.loc[index, key]),
                        float(slice_sums_squared.loc[index, key]),
                    ]
                    for index in range(SLICES)
                ],
                "returns_skewness": skewness,
                "returns_kurtosis": kurtosis,
            }
        )
    correlation = returns.corr()
    correlations = [
        (float(correlation.iloc[left, right]) if pd.notna(correlation.iloc[left, right]) else None)
        for left in range(len(correlation.columns))
        for right in range(left + 1, len(correlation.columns))
    ]
    return {
        "slice_count": SLICES,
        "slice_length_bars": slice_length,
        "bars_total": bar_count,
        "bars_excluded_tail": bar_count - slice_length * SLICES,
        "sample_count": bar_count,
        "return_correlation_observation_count": bar_count,
        "return_correlations_upper_triangle": correlations,
        "trials": rows,
    }


def _execution_audit(
    candles: pd.DataFrame, batch: SignalBatch, events: ExecutionEvents
) -> dict[str, Any]:
    adjacent = adjacency_mask(candles.index)
    deltas = candles.index[1:] - candles.index[:-1]
    missing_bars = sum(max(int(delta / BAR_DELTA) - 1, 0) for delta in deltas)
    rows = []
    for column, item in enumerate(batch.descriptors):
        raw_entry = batch.entries.iloc[:, column]
        raw_exit = batch.exits.iloc[:, column]
        rows.append(
            {
                "trial_key": item.trial_key,
                "raw_entry_signals": int(raw_entry.sum()),
                "raw_exit_signals": int(raw_exit.sum()),
                "raw_conflicts": int((raw_entry & raw_exit).sum()),
                "buy_orders": int(events.entries.iloc[:, column].sum()),
                "sell_orders": int(events.exits.iloc[:, column].sum()),
                "ending_open_position": bool(events.ending_held[column]),
                "final_bar_entry_signal_unfilled": bool(raw_entry.iloc[-1]),
                "final_bar_exit_signal_unfilled": bool(raw_exit.iloc[-1]),
            }
        )
    return {
        "bar_interval": "5m",
        "non_adjacent_transitions": int((~adjacent[1:]).sum()),
        "estimated_missing_bars": missing_bars,
        "signal_time": "bar_close",
        "fill_time": "next_exact_adjacent_bar_open",
        "gap_policy": "pending_signal_expires; indicator_warmup_resets; held_position_carries",
        "conflict_policy": "flat_entry; held_exit",
        "final_position_policy": "mark_at_final_close_without_forced_liquidation",
        "float_policy": "source decimal strings converted to float64 in frozen vectorbt lane",
        "trials": rows,
    }


def _cost_cell(
    scenario: CostScenario,
    simulation: SimulationResult,
    descriptors: Sequence[TrialDescriptor],
) -> dict[str, Any]:
    return {
        "scenario": scenario.scenario,
        "fee_rate_per_side": scenario.fee_rate_per_side,
        "slippage_bps_per_side": scenario.slippage_bps_per_side,
        "slippage_application": "adverse_by_order_side_at_next_bar_open",
        "diagnostic_only": scenario.diagnostic_only,
        "capacity_estimation": "NOT_ESTIMATED_FROM_5M_OHLCV",
        "trials": [
            {
                "trial_key": item.trial_key,
                "total_return": float(simulation.total_returns[item.trial_key]),
                "trades": int(simulation.trade_counts[item.trial_key]),
                "gross_executed_notional": float(
                    simulation.gross_executed_notional[item.trial_key]
                ),
                "turnover_on_initial_cash": float(
                    simulation.gross_executed_notional[item.trial_key] / INIT_CASH
                ),
                "executed_sides": int(
                    simulation.buy_order_counts[item.trial_key]
                    + simulation.sell_order_counts[item.trial_key]
                ),
                "buy_orders": int(simulation.buy_order_counts[item.trial_key]),
                "sell_orders": int(simulation.sell_order_counts[item.trial_key]),
            }
            for item in descriptors
        ],
    }


def _per_bar_sharpes(returns: pd.DataFrame) -> pd.Series:
    deviations = returns.std(ddof=1)
    result = returns.mean().divide(deviations.where(deviations > 0)).fillna(0.0)
    return result.astype("float64")


def _single_trial_batch(batch: SignalBatch, key: str, start: Any, end: Any) -> SignalBatch:
    index = [item.trial_key for item in batch.descriptors].index(key)
    item = batch.descriptors[index]
    return SignalBatch(
        family=batch.family,
        descriptors=(item,),
        entries=batch.entries.loc[start:end, [key]].copy(),
        exits=batch.exits.loc[start:end, [key]].copy(),
    )


def build_walk_forward(
    candles: pd.DataFrame,
    batch: SignalBatch,
    primary_returns: pd.DataFrame,
) -> dict[str, Any]:
    """Run frozen expanding yearly pseudo-OOS selection at F1/S1."""

    required_test_years = (2022, 2023, 2024, 2025, 2026)
    index = candles.index
    expected_first = pd.Timestamp("2021-01-01T00:00:00Z")
    if index[0] != expected_first or any(
        pd.Timestamp(f"{year}-01-01T00:00:00Z") not in index for year in required_test_years
    ):
        return {
            "status": "NOT_AVAILABLE_REQUIRED_CALENDAR_BOUNDARIES_MISSING",
            "classification": "HISTORICAL_PSEUDO_OOS",
            "winner_selected": False,
            "folds": [],
        }

    folds: list[dict[str, Any]] = []
    stitched: list[pd.Series] = []
    for year in required_test_years:
        test_start = pd.Timestamp(f"{year}-01-01T00:00:00Z")
        gap_bar = test_start - BAR_DELTA
        train_end = test_start - 2 * BAR_DELTA
        if gap_bar not in index or train_end not in index:
            raise RuntimeError(f"walk-forward boundary before {year} is not contiguous")
        nominal_end = pd.Timestamp(f"{year + 1}-01-01T00:00:00Z") - BAR_DELTA
        test_end = min(nominal_end, index[-1])
        train = primary_returns.loc[index[0] : train_end]
        scores = _per_bar_sharpes(train)
        # Stable descriptor order is the predeclared tie breaker.
        selection = max(
            range(len(scores)), key=lambda offset: (float(scores.iloc[offset]), -offset)
        )
        key = str(scores.index[selection])
        selected_batch = _single_trial_batch(batch, key, test_start, test_end)
        test_candles = candles.loc[test_start:test_end]
        test_events = resolve_transitions(selected_batch, start_held=False)
        simulation = simulate_returns(test_candles, test_events, PRIMARY_SCENARIO)
        test_returns = simulation.returns[key]
        stitched.append(test_returns)
        test_sharpe = float(_per_bar_sharpes(simulation.returns)[key])
        folds.append(
            {
                "fold_id": f"WF-{year}" if year < 2026 else "WF-2026-H1",
                "fold": f"{year}" if year < 2026 else "2026H1",
                "train_start": index[0].isoformat(),
                "train_end": train_end.isoformat(),
                "gap_bar": gap_bar.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
                "test_bars": len(test_candles),
                "selected_trial_key": key,
                "selected_train_sharpe_per_bar": float(scores[key]),
                "test_total_return": float(simulation.total_returns[key]),
                "test_sharpe_per_bar": test_sharpe,
                "test_trades": int(simulation.trade_counts[key]),
                "test_ending_open_position": bool(test_events.ending_held[0]),
            }
        )
        del simulation
        gc.collect()

    stitched_returns = pd.concat(stitched, ignore_index=True)
    deviation = float(stitched_returns.std(ddof=1))
    stitched_sharpe = float(stitched_returns.mean()) / deviation if deviation > 0 else 0.0
    return {
        "status": "COMPLETED",
        "classification": "HISTORICAL_PSEUDO_OOS",
        "scenario": PRIMARY_SCENARIO.scenario,
        "selection_metric": "max expanding-train non_annualized_per_bar_sharpe",
        "selection_tie_breaker": "frozen trial order",
        "gap": "one complete 5m bar",
        "indicator_warmup": "trailing history only; no pre-test signal or position imported",
        "test_initial_position": "FLAT",
        "first_possible_test_fill": "second exact-adjacent test bar",
        "winner_selected": False,
        "folds": folds,
        "stitched_test_bars": len(stitched_returns),
        "stitched_test_total_return_compounded": float((1.0 + stitched_returns).prod() - 1.0),
        "stitched_test_sharpe_per_bar": stitched_sharpe,
    }


def combine_signal_batches(batches: Mapping[str, SignalBatch]) -> SignalBatch:
    """Combine families with prefixed keys for campaign-wide diagnostics."""

    descriptors: list[TrialDescriptor] = []
    entries: list[pd.DataFrame] = []
    exits: list[pd.DataFrame] = []
    for family in ("b2", "b3", "b4"):
        batch = batches[family]
        renames = {key: f"{family}:{key}" for key in batch.entries.columns}
        entries.append(batch.entries.rename(columns=renames))
        exits.append(batch.exits.rename(columns=renames))
        descriptors.extend(
            replace(item, trial_key=f"{family}:{item.trial_key}") for item in batch.descriptors
        )
    return SignalBatch(
        family="all",
        descriptors=tuple(descriptors),
        entries=pd.concat(entries, axis=1),
        exits=pd.concat(exits, axis=1),
    )


def _run_family(
    candles: pd.DataFrame,
    batch: SignalBatch,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, dict[str, Any]]]:
    events = resolve_transitions(batch)
    cost_cells: list[dict[str, Any]] = []
    primary_statistics: dict[str, Any] | None = None
    primary_returns: pd.DataFrame | None = None
    cost_by_id: dict[str, dict[str, Any]] = {}
    for scenario in COST_SCENARIOS:
        simulation = simulate_returns(candles, events, scenario)
        cell = _cost_cell(scenario, simulation, batch.descriptors)
        cost_cells.append(cell)
        cost_by_id[scenario.scenario] = cell
        if scenario == PRIMARY_SCENARIO:
            primary_statistics = _statistics_payload(
                simulation.returns,
                simulation.total_returns,
                simulation.trade_counts,
                batch.descriptors,
            )
            primary_returns = simulation.returns.copy()
        del simulation
        gc.collect()
    if primary_statistics is None or primary_returns is None:
        raise RuntimeError("primary F1/S1 cell was not run")
    payload = {
        **primary_statistics,
        "cost_surface": {
            "primary_statistical_cell": PRIMARY_SCENARIO.scenario,
            "cells": cost_cells,
        },
        "execution_audit": _execution_audit(candles, batch, events),
        "walk_forward": build_walk_forward(candles, batch, primary_returns),
    }
    return payload, primary_returns, cost_by_id


def _campaign_cost_surface(
    family_cells: Mapping[str, Mapping[str, dict[str, Any]]],
) -> dict[str, Any]:
    cells = []
    for scenario in COST_SCENARIOS:
        trials = []
        for family in ("b2", "b3", "b4"):
            for row in family_cells[family][scenario.scenario]["trials"]:
                trials.append(
                    {
                        **row,
                        "family": family,
                        "trial_key": f"{family}:{row['trial_key']}",
                    }
                )
        cells.append(
            {
                "scenario": scenario.scenario,
                "fee_rate_per_side": scenario.fee_rate_per_side,
                "slippage_bps_per_side": scenario.slippage_bps_per_side,
                "slippage_application": "adverse_by_order_side_at_next_bar_open",
                "diagnostic_only": scenario.diagnostic_only,
                "capacity_estimation": "NOT_ESTIMATED_FROM_5M_OHLCV",
                "trials": trials,
            }
        )
    return {"primary_statistical_cell": PRIMARY_SCENARIO.scenario, "cells": cells}


def build_payloads(
    candles: pd.DataFrame,
    *,
    dataset_file: str,
    generated_at: str,
    specs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the three family payloads and one 67-trial campaign payload."""

    parsed_specs = dict(specs or load_frozen_specs())
    batches = build_raw_signals(candles, build_trial_descriptors(parsed_specs))
    base_returns: dict[str, pd.DataFrame] = {}
    cost_cells: dict[str, dict[str, dict[str, Any]]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    common = {
        "schema": "tios-canonical-baseline-returns-v1",
        "purpose": "preregistered canonical B2/B3/B4 G10 and cost diagnostics",
        "engine": f"vectorbt {vbt.__version__}",
        "dataset_file": Path(dataset_file).name,
        "generated_at_utc": generated_at,
        "primary_scenario": PRIMARY_SCENARIO.scenario,
        "initial_cash": INIT_CASH,
        "execution_authority": "NONE",
        "promotion_eligible": False,
        "winner_selected": False,
    }
    for family in ("b2", "b3", "b4"):
        body, returns, cells = _run_family(candles, batches[family])
        base_returns[family] = returns
        cost_cells[family] = cells
        payloads[family] = {
            **common,
            "baseline": family,
            "canonical_spec": parsed_specs[family],
            **body,
        }

    all_batch = combine_signal_batches(batches)
    all_returns = pd.concat(
        [base_returns[family].add_prefix(f"{family}:") for family in ("b2", "b3", "b4")],
        axis=1,
    )
    totals = pd.Series(
        {
            f"{family}:{row['trial_key']}": row["total_return"]
            for family in ("b2", "b3", "b4")
            for row in cost_cells[family][PRIMARY_SCENARIO.scenario]["trials"]
        },
        dtype="float64",
    )
    trades = pd.Series(
        {
            f"{family}:{row['trial_key']}": row["trades"]
            for family in ("b2", "b3", "b4")
            for row in cost_cells[family][PRIMARY_SCENARIO.scenario]["trials"]
        },
        dtype="int64",
    )
    all_events = resolve_transitions(all_batch)
    payloads["all"] = {
        **common,
        "baseline": "all",
        "canonical_specs": parsed_specs,
        **_statistics_payload(all_returns, totals, trades, all_batch.descriptors),
        "cost_surface": _campaign_cost_surface(cost_cells),
        "execution_audit": _execution_audit(candles, all_batch, all_events),
        "walk_forward": build_walk_forward(candles, all_batch, all_returns),
    }
    return payloads


def main(
    dataset_path: Path | str = DATASET,
    out: Path | str = VALIDATION_OUT,
    *,
    generated_at: str | None = None,
) -> dict[str, Path]:
    timestamp = generated_at or datetime.now(tz=UTC).isoformat()
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("generated_at must be an ISO-8601 UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != pd.Timedelta(0):
        raise ValueError("generated_at must be timezone-aware UTC")
    candles = load_candles(dataset_path)
    payloads = build_payloads(
        candles,
        dataset_file=Path(dataset_path).name,
        generated_at=timestamp,
    )
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        family: output / f"canonical_returns_{family}.json" for family in ("b2", "b3", "b4", "all")
    }
    for family, path in paths.items():
        path.write_text(
            json.dumps(payloads[family], indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "bars": len(candles),
                "trials": {family: len(payloads[family]["trials"]) for family in paths},
                "outputs": {family: path.name for family, path in paths.items()},
            },
            sort_keys=True,
        )
    )
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path, default=VALIDATION_OUT)
    parser.add_argument(
        "--generated-at",
        help="fixed UTC ISO-8601 timestamp for byte-identical governed reruns",
    )
    arguments = parser.parse_args()
    main(arguments.dataset, arguments.out, generated_at=arguments.generated_at)
