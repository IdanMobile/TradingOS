"""Run retained B2/B3/B4 vectorbt accelerator sweeps on frozen BTC candles."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "bakeoff" / "vectorbt"
RESEARCH_OUT = ROOT / "artifacts" / "research_lab" / "v0"
DATASET = ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"
FEES = 0.001
B2_FAST = (2, 3, 5, 8, 10, 15)
B2_SLOW = (10, 20, 30, 40, 50, 60)
B3_WINDOW = (3, 5, 10, 20)
B3_DEVIATION = (0.5, 1.0, 1.5, 2.0)
B4_LOOKBACK = (3, 5, 10, 20)
B4_EXIT_WINDOW = (2, 3, 5, 10)
SWEEP_CONFIG = {
    "b2": {"fast": B2_FAST, "slow": B2_SLOW},
    "b3": {"window": B3_WINDOW, "deviation": B3_DEVIATION},
    "b4": {"lookback": B4_LOOKBACK, "exit_window": B4_EXIT_WINDOW},
}


def _confined(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must be within {root}")
    return resolved


def _confined_output(path: Path) -> Path:
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in (OUT, RESEARCH_OUT)):
        raise ValueError(f"output must be within {OUT} or {RESEARCH_OUT}")
    return resolved


def _failure_reason(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def _failed_row(key: str, error: Exception) -> dict[str, object]:
    return {
        "trial_key": key,
        "status": "FAILED",
        "failure_reason": _failure_reason(error),
        "total_return": None,
        "trades": None,
    }


def _run_portfolio_batch(
    close: pd.Series, entries: dict[str, pd.Series], exits: dict[str, pd.Series]
) -> pd.DataFrame:
    entry_frame = pd.DataFrame(entries, index=close.index).fillna(False)
    exit_frame = pd.DataFrame(exits, index=close.index).fillna(False)
    prices = pd.concat({name: close for name in entry_frame.columns}, axis=1)
    portfolio = vbt.Portfolio.from_signals(
        prices,
        entry_frame,
        exit_frame,
        fees=FEES,
        init_cash=1000.0,
    )
    return pd.DataFrame(
        {
            "trial_key": entry_frame.columns,
            "status": "COMPLETED",
            "failure_reason": None,
            "total_return": list(portfolio.total_return()),
            "trades": list(portfolio.trades.count()),
        }
    )


def run_portfolio(
    close: pd.Series, entries: dict[str, pd.Series], exits: dict[str, pd.Series]
) -> pd.DataFrame:
    """Run vectorized, bisecting only on errors to retain per-trial failures."""
    if not entries:
        return pd.DataFrame()
    try:
        return _run_portfolio_batch(close, entries, exits)
    except Exception as error:
        keys = list(entries)
        if len(keys) == 1:
            return pd.DataFrame([_failed_row(keys[0], error)])
        midpoint = len(keys) // 2
        halves = (keys[:midpoint], keys[midpoint:])
        return pd.concat(
            [
                run_portfolio(
                    close,
                    {key: entries[key] for key in half},
                    {key: exits[key] for key in half},
                )
                for half in halves
            ],
            ignore_index=True,
        )


def _finish(
    result: pd.DataFrame,
    failures: list[dict[str, object]],
    parameters: Mapping[str, Sequence[int | float]],
    names: list[str],
) -> pd.DataFrame:
    if failures:
        result = pd.concat([result, pd.DataFrame(failures)], ignore_index=True)
    result[names] = result["trial_key"].map(parameters).tolist()
    order = {key: index for index, key in enumerate(parameters)}
    result["_order"] = result["trial_key"].map(order)
    return result.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def sweep_b2(close: pd.Series) -> tuple[pd.DataFrame, int]:
    combos = [(fast, slow) for fast, slow in product(B2_FAST, B2_SLOW) if fast < slow]
    entries: dict[str, pd.Series] = {}
    exits: dict[str, pd.Series] = {}
    parameters: dict[str, tuple[int, int]] = {}
    failures: list[dict[str, object]] = []
    for fast, slow in combos:
        key = f"fast={fast},slow={slow}"
        parameters[key] = (fast, slow)
        try:
            fast_ma = close.rolling(fast).mean()
            slow_ma = close.rolling(slow).mean()
            entries[key] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            exits[key] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
        except Exception as error:
            failures.append(_failed_row(key, error))
    result = _finish(run_portfolio(close, entries, exits), failures, parameters, ["fast", "slow"])
    return result[
        ["trial_key", "fast", "slow", "status", "failure_reason", "total_return", "trades"]
    ], len(combos)


def sweep_b3(close: pd.Series) -> tuple[pd.DataFrame, int]:
    combos = list(product(B3_WINDOW, B3_DEVIATION))
    entries: dict[str, pd.Series] = {}
    exits: dict[str, pd.Series] = {}
    parameters: dict[str, tuple[int, float]] = {}
    failures: list[dict[str, object]] = []
    for window, deviation in combos:
        key = f"window={window},deviation={deviation:g}"
        parameters[key] = (window, deviation)
        try:
            middle = close.rolling(window).mean()
            lower = middle - deviation * close.rolling(window).std(ddof=0)
            entries[key] = close < lower
            exits[key] = close >= middle
        except Exception as error:
            failures.append(_failed_row(key, error))
    result = _finish(
        run_portfolio(close, entries, exits), failures, parameters, ["window", "deviation"]
    )
    return result[
        ["trial_key", "window", "deviation", "status", "failure_reason", "total_return", "trades"]
    ], len(combos)


def sweep_b4(close: pd.Series, high: pd.Series) -> tuple[pd.DataFrame, int]:
    combos = [
        (lookback, exit_window) for lookback, exit_window in product(B4_LOOKBACK, B4_EXIT_WINDOW)
    ]
    entries: dict[str, pd.Series] = {}
    exits: dict[str, pd.Series] = {}
    parameters: dict[str, tuple[int, int]] = {}
    failures: list[dict[str, object]] = []
    for lookback, exit_window in combos:
        key = f"lookback={lookback},exit_window={exit_window}"
        parameters[key] = (lookback, exit_window)
        try:
            prior_high = high.rolling(lookback).max().shift(1)
            exit_average = close.rolling(exit_window).mean()
            entries[key] = close > prior_high
            exits[key] = close < exit_average
        except Exception as error:
            failures.append(_failed_row(key, error))
    result = _finish(
        run_portfolio(close, entries, exits),
        failures,
        parameters,
        ["lookback", "exit_window"],
    )
    return result[
        [
            "trial_key",
            "lookback",
            "exit_window",
            "status",
            "failure_reason",
            "total_return",
            "trades",
        ]
    ], len(combos)


def main(dataset_path: Path | str = DATASET, out: Path | str = OUT) -> dict[str, dict[str, object]]:
    dataset_path = Path(dataset_path)
    out = Path(out)
    dataset_path = _confined(dataset_path, ROOT / "data/normalized", "dataset")
    out = _confined_output(out)
    candles = (
        pd.read_parquet(
            dataset_path,
            columns=["timestamp_open_utc", "close", "high"],
        )
        .set_index("timestamp_open_utc")
        .astype("float64")
    )
    out.mkdir(parents=True, exist_ok=True)
    runners: dict[str, Callable[[], tuple[pd.DataFrame, int]]] = {
        "b2": lambda: sweep_b2(candles["close"]),
        "b3": lambda: sweep_b3(candles["close"]),
        "b4": lambda: sweep_b4(candles["close"], candles["high"]),
    }
    summary: dict[str, dict[str, object]] = {}
    for baseline, runner in runners.items():
        started_at = datetime.now(tz=UTC)
        started = time.perf_counter()
        results, combinations = runner()
        elapsed = time.perf_counter() - started
        finished_at = datetime.now(tz=UTC)
        results.to_parquet(out / f"{baseline}_sweep_all_trials.parquet", index=False)
        meta = {
            "probe": f"T-006-06 vectorbt {baseline.upper()} retained sweep",
            "engine": f"vectorbt {vbt.__version__}",
            "dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1 BTCUSDT_5m (577,803 bars)",
            "fees_per_side": FEES,
            "combos": combinations,
            "elapsed_seconds": round(elapsed, 3),
            "bars_x_combos_per_second": round(len(candles) * combinations / elapsed),
            "all_trials_retained": len(results) == combinations,
            "started_at_utc": started_at.isoformat(),
            "finished_at_utc": finished_at.isoformat(),
            "ran_utc": finished_at.isoformat(),
            "note": "accelerator probe; in-sample return is never a promotion criterion",
        }
        (out / f"{baseline}_sweep_meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        summary[baseline] = meta
    print(json.dumps(summary, indent=2))
    return summary


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    main(args.dataset, args.out)


if __name__ == "__main__":
    cli()
