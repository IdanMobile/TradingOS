"""Extract per-trial sliced returns for candidate-specific G10 (T-009-04 / RG-07).

Rebuilds the exact retained B2/B3/B4 sweep populations (same signal expressions,
portfolio settings, and fee model as `probe_sweep.py`) and emits, per baseline
family, the per-trial time-slice mean returns, per-trial full-sample per-bar
Sharpe, and parity fields (`total_return`, `trades`). The caller must verify the
parity fields against the retained research-lab Parquet before using any G10
statistic; that runtime check is what guarantees this file's signal expressions
stayed identical to the retained sweep.

Offline research only: no venue, credential, order, or network path.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"
VALIDATION_OUT = ROOT / "artifacts" / "validation"
FEES = 0.001  # must match probe_sweep.FEES
INIT_CASH = 1000.0  # must match probe_sweep._run_portfolio_batch
SLICES = 16  # even, required by CSCV
B2_FAST = (2, 3, 5, 8, 10, 15)
B2_SLOW = (10, 20, 30, 40, 50, 60)
B3_WINDOW = (3, 5, 10, 20)
B3_DEVIATION = (0.5, 1.0, 1.5, 2.0)
B4_LOOKBACK = (3, 5, 10, 20)
B4_EXIT_WINDOW = (2, 3, 5, 10)


def _confined(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must be within {root}")
    return resolved


def _signals(candles: pd.DataFrame) -> dict[str, dict[str, tuple[pd.Series, pd.Series]]]:
    """Same signal expressions as probe_sweep.sweep_b2/b3/b4 — keep in sync."""
    close = candles["close"]
    high = candles["high"]
    families: dict[str, dict[str, tuple[pd.Series, pd.Series]]] = {"b2": {}, "b3": {}, "b4": {}}
    for fast, slow in product(B2_FAST, B2_SLOW):
        if fast >= slow:
            continue
        fast_ma = close.rolling(fast).mean()
        slow_ma = close.rolling(slow).mean()
        families["b2"][f"fast={fast},slow={slow}"] = (
            (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1)),
            (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1)),
        )
    for window, deviation in product(B3_WINDOW, B3_DEVIATION):
        middle = close.rolling(window).mean()
        lower = middle - deviation * close.rolling(window).std(ddof=0)
        families["b3"][f"window={window},deviation={deviation:g}"] = (
            close < lower,
            close >= middle,
        )
    for lookback, exit_window in product(B4_LOOKBACK, B4_EXIT_WINDOW):
        prior_high = high.rolling(lookback).max().shift(1)
        exit_average = close.rolling(exit_window).mean()
        families["b4"][f"lookback={lookback},exit_window={exit_window}"] = (
            close > prior_high,
            close < exit_average,
        )
    return families


def _family_payload(
    close: pd.Series, trials: dict[str, tuple[pd.Series, pd.Series]]
) -> dict[str, object]:
    entry_frame = pd.DataFrame(
        {key: value[0] for key, value in trials.items()}, index=close.index
    ).fillna(False)
    exit_frame = pd.DataFrame(
        {key: value[1] for key, value in trials.items()}, index=close.index
    ).fillna(False)
    prices = pd.concat({name: close for name in entry_frame.columns}, axis=1)
    portfolio = vbt.Portfolio.from_signals(
        prices, entry_frame, exit_frame, fees=FEES, init_cash=INIT_CASH
    )
    returns = pd.DataFrame(portfolio.returns())
    returns.columns = list(entry_frame.columns)
    bar_count = len(returns)
    slice_length = bar_count // SLICES
    used = returns.iloc[: slice_length * SLICES]
    slice_labels = pd.Series(range(len(used)), index=used.index) // slice_length
    slice_means = used.groupby(slice_labels.to_numpy()).mean()
    means = returns.mean()
    deviations = returns.std(ddof=1)
    totals = portfolio.total_return()
    totals.index = list(entry_frame.columns)
    trade_counts = portfolio.trades.count()
    trade_counts.index = list(entry_frame.columns)
    rows = []
    for key in entry_frame.columns:
        deviation = float(deviations[key])
        rows.append(
            {
                "trial_key": key,
                "status": "COMPLETED",
                "total_return": float(totals[key]),
                "trades": int(trade_counts[key]),
                "sharpe_per_bar": (float(means[key]) / deviation) if deviation > 0 else 0.0,
                "slice_mean_returns": [float(value) for value in slice_means[key]],
                "returns_skewness": float(returns[key].skew()),
                # pandas kurt() is Fisher (excess); DSR expects raw kurtosis (normal = 3).
                "returns_kurtosis": float(returns[key].kurt()) + 3.0,
            }
        )
    return {
        "slice_count": SLICES,
        "slice_length_bars": slice_length,
        "bars_total": bar_count,
        "bars_excluded_tail": bar_count - slice_length * SLICES,
        "sample_count": bar_count,
        "trials": rows,
    }


def main(dataset_path: Path | str = DATASET, out: Path | str = VALIDATION_OUT) -> None:
    dataset_path = _confined(Path(dataset_path), ROOT / "data/normalized", "dataset")
    out = _confined(Path(out), VALIDATION_OUT, "output")
    candles = (
        pd.read_parquet(dataset_path, columns=["timestamp_open_utc", "close", "high"])
        .set_index("timestamp_open_utc")
        .astype("float64")
    )
    out.mkdir(parents=True, exist_ok=True)
    families = _signals(candles)
    for baseline, trials in families.items():
        payload = {
            "schema": "tios-g10-returns-v1",
            "purpose": "candidate-specific G10 PBO/DSR inputs (T-009-04 / RG-07)",
            "engine": f"vectorbt {vbt.__version__}",
            "dataset_file": dataset_path.name,
            "fees_per_side": FEES,
            "init_cash": INIT_CASH,
            "generated_at_utc": datetime.now(tz=UTC).isoformat(),
            "baseline": baseline,
            **_family_payload(candles["close"], trials),
        }
        (out / f"g10_returns_{baseline}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{baseline}: {len(trials)} trials, {payload['slice_count']} slices")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path, default=VALIDATION_OUT)
    args = parser.parse_args()
    main(args.dataset, args.out)
