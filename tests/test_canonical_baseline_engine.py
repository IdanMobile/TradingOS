"""Focused contract tests for the isolated canonical vectorbt extractor."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"


@pytest.fixture(scope="module")
def probe() -> dict[str, object]:
    """Exercise all numerical contracts once inside the frozen engine environment."""

    code = r"""
import json
import numpy as np
import pandas as pd

import engines.vectorbt.canonical_baseline_returns as canonical


def candles(close, *, index=None, high=None, open_=None):
    close = np.asarray(close, dtype=float)
    if index is None:
        index = pd.date_range("2024-01-01", periods=len(close), freq="5min", tz="UTC")
    if high is None:
        high = close + 1.0
    high = np.asarray(high, dtype=float)
    if open_ is None:
        open_ = close
    open_ = np.asarray(open_, dtype=float)
    low = np.minimum(open_, close) - 1.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=index,
    )


def one_batch(index, entries, exits, *, key="trial"):
    descriptor = canonical.TrialDescriptor("test", key, (), False)
    return canonical.SignalBatch(
        "test",
        (descriptor,),
        pd.DataFrame({key: entries}, index=index, dtype=bool),
        pd.DataFrame({key: exits}, index=index, dtype=bool),
    )


specs = canonical.load_frozen_specs()
descriptors = canonical.build_trial_descriptors(specs)

# Canonical B2 is persistent eligibility and can enter on its first defined bar.
b2_candles = candles([1, 1, 1, 2, 3] + [3] * 35)
b2 = canonical.build_raw_signals(b2_candles, descriptors)["b2"]
b2_key = "fast=3,slow=5"
b2_offset = [item.trial_key for item in b2.descriptors].index(b2_key)
b2_one = canonical.SignalBatch(
    "b2",
    (b2.descriptors[b2_offset],),
    b2.entries[[b2_key]],
    b2.exits[[b2_key]],
)
b2_events = canonical.resolve_transitions(b2_one)

# Conflict policy is state-aware: flat enters, then held exits.
conflict_index = pd.date_range("2024-02-01", periods=3, freq="5min", tz="UTC")
conflict = canonical.resolve_transitions(
    one_batch(conflict_index, [True, True, False], [True, True, False])
)

# Next-open timing, exact adjacency, final-signal expiry, and held-state carry.
timing_index = pd.date_range("2024-03-01", periods=4, freq="5min", tz="UTC")
timing = canonical.resolve_transitions(
    one_batch(timing_index, [True, False, False, True], [False, True, False, False])
)
gap_index = pd.DatetimeIndex(
    [
        "2024-04-01T00:00:00Z",
        "2024-04-01T00:05:00Z",
        "2024-04-01T00:10:00Z",
        "2024-04-01T00:30:00Z",
        "2024-04-01T00:35:00Z",
    ]
)
gap_events = canonical.resolve_transitions(
    one_batch(gap_index, [True, False, False, False, False], [False, False, True, False, False])
)
gap_warm_index = pd.DatetimeIndex(
    list(pd.date_range("2024-05-01", periods=5, freq="5min", tz="UTC"))
    + list(pd.date_range("2024-05-01T00:40:00Z", periods=5, freq="5min", tz="UTC"))
)
gap_warm = candles([1, 1, 1, 2, 3, 1, 1, 1, 2, 3], index=gap_warm_index)
gap_b2 = canonical.build_raw_signals(gap_warm, descriptors)["b2"].entries[b2_key]

# B4 must compare close with prior highs, excluding a huge current high.
b4_close = [9, 10, 11, 12, 13, 15] + [15] * 34
b4_high = [10, 11, 12, 13, 14, 100] + [16] * 34
b4 = canonical.build_raw_signals(
    candles(b4_close, high=b4_high), descriptors
)["b4"]

# Structurally impossible population-z cells remain in the roster as zero-entry trials.
b3_close = [100 + (offset % 7) * (-1 if offset % 2 else 1) for offset in range(40)]
b3 = canonical.build_raw_signals(candles(b3_close), descriptors)["b3"]
structural_keys = [item.trial_key for item in b3.descriptors if item.structural_zero_trade]

# Causal indicators cannot change when only future candles are mutated.
causal_close = [100 + np.sin(offset / 3) * 5 + offset / 10 for offset in range(60)]
causal_a = candles(causal_close)
causal_b = causal_a.copy()
causal_b.iloc[40:, causal_b.columns.get_loc("close")] *= 2
causal_b.iloc[40:, causal_b.columns.get_loc("open")] *= 2
causal_b.iloc[40:, causal_b.columns.get_loc("high")] = (
    causal_b.iloc[40:][["open", "close"]].max(axis=1) + 1
)
causal_b.iloc[40:, causal_b.columns.get_loc("low")] = (
    causal_b.iloc[40:][["open", "close"]].min(axis=1) - 1
)
signals_a = canonical.build_raw_signals(causal_a, descriptors)
signals_b = canonical.build_raw_signals(causal_b, descriptors)
causal_equal = all(
    signals_a[family].entries.iloc[:40].equals(signals_b[family].entries.iloc[:40])
    and signals_a[family].exits.iloc[:40].equals(signals_b[family].exits.iloc[:40])
    for family in ("b2", "b3", "b4")
)

# vectorbt applies adverse per-side slippage and fees at open.
cost_candles = candles([100, 100, 100, 100], open_=[100, 100, 100, 100])
cost_events = canonical.resolve_transitions(
    one_batch(cost_candles.index, [True, False, False, False], [False, False, True, False])
)
free = canonical.simulate_returns(
    cost_candles, cost_events, canonical.COST_SCENARIOS[0], include_orders=True
)
costed = canonical.simulate_returns(
    cost_candles, cost_events, canonical.PRIMARY_SCENARIO, include_orders=True
)
buy = costed.order_records.loc[costed.order_records["Side"] == "Buy"].iloc[0]
sell = costed.order_records.loc[costed.order_records["Side"] == "Sell"].iloc[0]

# An unclosed position is marked at final close, with no forced sell order.
mark_candles = candles([100, 100, 105, 110], open_=[100, 100, 100, 100])
mark_events = canonical.resolve_transitions(
    one_batch(mark_candles.index, [True, False, False, False], [False] * 4)
)
marked = canonical.simulate_returns(
    mark_candles, mark_events, canonical.COST_SCENARIOS[0], include_orders=True
)

# Exact controls must match the repository's independently hand-derived micro goldens.
micro = pd.read_csv(
    canonical.ROOT / "fixtures/micro/bars.csv",
    parse_dates=["timestamp_open_utc"],
).set_index("timestamp_open_utc")
micro = micro[["open", "high", "low", "close"]].astype("float64")
micro_batches = canonical.build_raw_signals(micro, descriptors)
exact_keys = {
    "b2": "fast=3,slow=5",
    "b3": "window=3,deviation=1",
    "b4": "lookback=5,exit_window=3",
}
micro_exact = {
    family: [
        [bool(entry), bool(exit_)]
        for entry, exit_ in zip(
            micro_batches[family].entries[key],
            micro_batches[family].exits[key],
            strict=True,
        )
    ]
    for family, key in exact_keys.items()
}

print(json.dumps({
    "specs": specs,
    "counts": {family: len(items) for family, items in descriptors.items()},
    "canonical_counts": {
        family: sum(item.exact_canonical_control for item in items)
        for family, items in descriptors.items()
    },
    "b2_first_defined_entry": bool(b2.entries[b2_key].iloc[4]),
    "b2_first_fill_next_open": bool(b2_events.entries[b2_key].iloc[5]),
    "conflict_buys": conflict.entries["trial"].tolist(),
    "conflict_sells": conflict.exits["trial"].tolist(),
    "timing_buys": timing.entries["trial"].tolist(),
    "timing_sells": timing.exits["trial"].tolist(),
    "gap_sell_expired": not bool(gap_events.exits["trial"].any()),
    "gap_position_carried": bool(gap_events.ending_held[0]),
    "gap_warmup_reset": not bool(gap_b2.iloc[5:9].any()),
    "b4_prior_high_entry": bool(b4.entries["lookback=5,exit_window=3"].iloc[5]),
    "structural_keys": structural_keys,
    "structural_entries": int(b3.entries[structural_keys].to_numpy().sum()),
    "causal_equal": causal_equal,
    "free_total_return": float(free.total_returns["trial"]),
    "costed_total_return": float(costed.total_returns["trial"]),
    "costed_buy_price": float(buy["Price"]),
    "costed_sell_price": float(sell["Price"]),
    "costed_fees_positive": bool((costed.order_records["Fees"] > 0).all()),
    "costed_turnover": float(costed.gross_executed_notional["trial"] / canonical.INIT_CASH),
    "costed_executed_sides": int(
        costed.buy_order_counts["trial"] + costed.sell_order_counts["trial"]
    ),
    "marked_total_return": float(marked.total_returns["trial"]),
    "marked_order_sides": marked.order_records["Side"].tolist(),
    "micro_exact": micro_exact,
}))
"""
    completed = subprocess.run(
        [str(ENGINE_PYTHON), "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_frozen_specs_and_complete_roster(probe: dict[str, object]) -> None:
    assert probe["counts"] == {"b2": 35, "b3": 16, "b4": 16}
    assert probe["canonical_counts"] == {"b2": 1, "b3": 1, "b4": 1}
    assert probe["specs"]["b3"]["ddof"] == 0  # type: ignore[index]


def test_b2_can_enter_on_first_defined_eligibility_bar(probe: dict[str, object]) -> None:
    assert probe["b2_first_defined_entry"] is True
    assert probe["b2_first_fill_next_open"] is True


def test_conflicts_resolve_from_position_state(probe: dict[str, object]) -> None:
    assert probe["conflict_buys"] == [False, True, False]
    assert probe["conflict_sells"] == [False, False, True]


def test_pending_signals_require_exact_next_bar_and_final_signal_expires(
    probe: dict[str, object],
) -> None:
    assert probe["timing_buys"] == [False, True, False, False]
    assert probe["timing_sells"] == [False, False, True, False]
    assert probe["gap_sell_expired"] is True
    assert probe["gap_position_carried"] is True
    assert probe["gap_warmup_reset"] is True


def test_b4_uses_prior_high_excluding_current_bar(probe: dict[str, object]) -> None:
    assert probe["b4_prior_high_entry"] is True


def test_exact_controls_match_independent_micro_goldens(probe: dict[str, object]) -> None:
    for family in ("b2", "b3", "b4"):
        path = ROOT / f"fixtures/micro/expected_signals_{family.upper()}.csv"
        with path.open(newline="") as handle:
            expected = [
                [row["entry"] == "true", row["exit"] == "true"] for row in csv.DictReader(handle)
            ]
        assert probe["micro_exact"][family] == expected  # type: ignore[index]


def test_structurally_impossible_b3_cells_are_retained_and_inactive(
    probe: dict[str, object],
) -> None:
    assert probe["structural_keys"] == [
        "window=3,deviation=1.5",
        "window=3,deviation=2",
        "window=5,deviation=2",
    ]
    assert probe["structural_entries"] == 0


def test_signal_construction_is_invariant_to_future_mutation(probe: dict[str, object]) -> None:
    assert probe["causal_equal"] is True


def test_vectorbt_applies_adverse_slippage_and_fees_at_open(probe: dict[str, object]) -> None:
    assert probe["free_total_return"] == pytest.approx(0.0)
    assert probe["costed_total_return"] < probe["free_total_return"]  # type: ignore[operator]
    assert probe["costed_buy_price"] == pytest.approx(100.01)
    assert probe["costed_sell_price"] == pytest.approx(99.99)
    assert probe["costed_fees_positive"] is True
    assert probe["costed_turnover"] > 1.9  # type: ignore[operator]
    assert probe["costed_executed_sides"] == 2


def test_open_final_position_is_marked_without_forced_liquidation(
    probe: dict[str, object],
) -> None:
    assert probe["marked_total_return"] == pytest.approx(0.10)
    assert probe["marked_order_sides"] == ["Buy"]
