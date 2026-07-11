"""Reproduce the canonical B2 spec (SMA3/SMA5 crossover) through vectorbt.

Cross-engine reproduction input (T-006-07 follow-up / research-lab
`cross_engine_reproduction` dimension): runs the exact canonical B2 parameters
— not the sweep grid — through the accelerator engine and emits entry/exit
signal timestamps plus portfolio outcome for reconciliation against the
retained Freqtrade event-lane run and an engine-independent core derivation.

Offline research only: no venue, credential, order, or network path.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"
VALIDATION_OUT = ROOT / "artifacts" / "validation"
FEES = 0.001
INIT_CASH = 1000.0
FAST = 3  # canonical B2 spec: sma_fast window
SLOW = 5  # canonical B2 spec: sma_slow window


def _confined(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must be within {root}")
    return resolved


def main(dataset_path: Path | str = DATASET, out: Path | str = VALIDATION_OUT) -> None:
    dataset_path = _confined(Path(dataset_path), ROOT / "data/normalized", "dataset")
    out = _confined(Path(out), VALIDATION_OUT, "output")
    close = (
        pd.read_parquet(dataset_path, columns=["timestamp_open_utc", "close"])
        .set_index("timestamp_open_utc")["close"]
        .astype("float64")
    )
    fast_ma = close.rolling(FAST).mean()
    slow_ma = close.rolling(SLOW).mean()
    entries = ((fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))).fillna(False)
    exits = ((fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))).fillna(False)
    portfolio = vbt.Portfolio.from_signals(
        close, entries, exits, fees=FEES, init_cash=INIT_CASH
    )
    payload = {
        "schema": "tios-b2-repro-v1",
        "engine": f"vectorbt {vbt.__version__}",
        "dataset_file": dataset_path.name,
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "parameters": {"fast": FAST, "slow": SLOW},
        "fees_per_side": FEES,
        "init_cash": INIT_CASH,
        "bars": int(len(close)),
        "entry_signal_bar_opens_utc": [
            index.isoformat() for index in close.index[entries.to_numpy()]
        ],
        "exit_signal_count": int(exits.sum()),
        "total_return": float(portfolio.total_return()),
        "trades": int(portfolio.trades.count()),
        "timing_note": (
            "vectorbt fills on the signal bar close; the Freqtrade event lane fills "
            "on the next candle open — signal bars, not fill prices, are the "
            "reproduction contract"
        ),
    }
    (out / "b2_repro_vectorbt.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "entries": len(payload["entry_signal_bar_opens_utc"]),
                "exits": payload["exit_signal_count"],
                "total_return": payload["total_return"],
                "trades": payload["trades"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path, default=VALIDATION_OUT)
    args = parser.parse_args()
    main(args.dataset, args.out)
