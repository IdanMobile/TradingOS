"""Read the frozen D-075 normalized data inside engine environments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]


def trial_name(interpretation: str, baseline_hours: int, threshold: float) -> str:
    return (
        f"interpretation={interpretation}|baseline_hours={baseline_hours}|threshold={threshold:.1f}"
    )


def load_cross_venue(root: Path, package_path: str) -> pd.DataFrame:
    package: dict[str, Any] = json.loads((root / package_path).read_text())
    frame = pd.read_parquet(root / package["normalized"]["path"])
    for column in (
        "coinbase_btcusd_close",
        "coinbase_usdtusd_close",
        "binance_btcusdt_open",
        "binance_btcusdt_close",
        "coinbase_implied_btcusdt",
        "log_premium",
    ):
        frame[column] = frame[column].astype(float)
    return frame.set_index("timestamp_open_utc", drop=False).sort_index()
