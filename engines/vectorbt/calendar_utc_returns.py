"""Vectorbt accelerator for the frozen seven-trial UTC-weekday campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/normalized/BTCUSDT_1h.parquet"
INITIAL_CASH = 1000.0
BAR_DELTA = pd.Timedelta(hours=1)
WEEKDAYS = tuple(range(7))


@dataclass(frozen=True)
class CostScenario:
    scenario: str
    fee_rate_per_side: float
    slippage_bps_per_side: float

    @property
    def slippage_fraction(self) -> float:
        return self.slippage_bps_per_side / 10_000.0


COST_SCENARIOS = (
    CostScenario("F0/S0", 0.0, 0.0),
    CostScenario("F1/S1", 0.001, 1.0),
    CostScenario("F1/S2", 0.001, 5.0),
    CostScenario("F1/S3", 0.001, 10.0),
    CostScenario("F2/S2", 0.0015, 5.0),
    CostScenario("F2/S3", 0.0015, 10.0),
)


def load_candles(path: Path | str = DATASET) -> pd.DataFrame:
    candles = pd.read_parquet(path, columns=["timestamp_open_utc", "open", "close"])
    candles = candles.set_index("timestamp_open_utc")[["open", "close"]].astype("float64")
    if not isinstance(candles.index, pd.DatetimeIndex) or candles.index.tz is None:
        raise RuntimeError("timestamp_open_utc must be a timezone-aware DatetimeIndex")
    if not candles.index.is_monotonic_increasing or not candles.index.is_unique:
        raise RuntimeError("candles must be unique and strictly ordered")
    if len(candles) < 2 or not np.isfinite(candles.to_numpy()).all():
        raise RuntimeError("candles must contain finite prices")
    if (candles <= 0).any().any():
        raise RuntimeError("prices must be positive")
    return candles


def build_events(candles: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build position-aware next-open fills for all seven weekdays."""
    index = candles.index
    adjacent = np.zeros(len(index), dtype=np.bool_)
    adjacent[1:] = (index[1:] - index[:-1]) == BAR_DELTA
    entries = np.zeros((len(index), len(WEEKDAYS)), dtype=np.bool_)
    exits = np.zeros_like(entries)
    held = np.zeros(len(WEEKDAYS), dtype=np.bool_)
    for row in range(1, len(index)):
        previous = index[row - 1]
        if not adjacent[row]:
            exits[row, held] = True
            held[:] = False
            continue
        if previous.hour != 23:
            continue
        for column, weekday in enumerate(WEEKDAYS):
            if held[column] and previous.weekday() == weekday:
                exits[row, column] = True
                held[column] = False
            elif not held[column] and index[row].weekday() == weekday:
                entries[row, column] = True
                held[column] = True
    columns = [f"weekday={weekday}" for weekday in WEEKDAYS]
    return (
        pd.DataFrame(entries, index=index, columns=columns),
        pd.DataFrame(exits, index=index, columns=columns),
    )


def simulate(
    candles: pd.DataFrame, scenario: CostScenario
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    entries, exits = build_events(candles)
    portfolio = vbt.Portfolio.from_signals(
        candles["close"],
        entries,
        exits,
        price=candles["open"],
        fees=scenario.fee_rate_per_side,
        slippage=scenario.slippage_fraction,
        init_cash=INITIAL_CASH,
        direction="longonly",
        accumulate=False,
        freq=BAR_DELTA,
    )
    returns = pd.DataFrame(portfolio.returns(), index=candles.index, columns=entries.columns)
    totals = pd.Series(portfolio.total_return(), index=entries.columns, dtype="float64")
    orders = pd.DataFrame(portfolio.orders.records_readable)
    return returns, totals, orders


def _return_hash(values: pd.Series) -> str:
    canonical = np.round(values.to_numpy(dtype="float64"), 12).astype("<f8", copy=False)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def _max_drawdown(values: pd.Series) -> float:
    equity = (1.0 + values).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def campaign_payload(candles: pd.DataFrame, segments: dict[str, tuple[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for segment, (start, end) in segments.items():
        lower, upper = pd.Timestamp(start), pd.Timestamp(end)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        selected = candles.loc[lower:upper]
        if selected.empty:
            raise RuntimeError(f"segment {segment!r} is empty")
        result[segment] = {}
        for scenario in COST_SCENARIOS:
            returns, totals, orders = simulate(selected, scenario)
            rows = {}
            for trial in returns.columns:
                series = returns[trial]
                deviation = float(series.std(ddof=1))
                trial_orders = orders[orders["Column"] == trial]
                sides = trial_orders["Side"].value_counts()
                rows[trial] = {
                    "total_return": float(totals[trial]),
                    "sharpe_per_bar": float(series.mean()) / deviation if deviation > 0 else 0.0,
                    "max_drawdown": _max_drawdown(series),
                    "buy_count": int(sides.get("Buy", 0)),
                    "sell_count": int(sides.get("Sell", 0)),
                    "return_hash_12dp": _return_hash(series),
                }
            result[segment][scenario.scenario] = rows
    return {
        "schema": "tios-calendar-utc-vectorbt-results-v1",
        "numeric_representation": "FLOAT64_ROUNDED_12DP_FOR_PARITY_HASH",
        "segments": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    segments = {key: tuple(value) for key, value in request["segments"].items()}
    payload = campaign_payload(load_candles(args.dataset), segments)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
