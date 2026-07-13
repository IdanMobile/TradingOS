"""Read-only retained inputs shared by MVRV engine harnesses."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]


def load_spot(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["timestamp_open_utc", "open", "close"])
    frame = frame.set_index("timestamp_open_utc")[["open", "close"]].astype("float64")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise RuntimeError("Spot timestamps must be timezone-aware")
    if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise RuntimeError("Spot timestamps must be unique and ordered")
    return frame


def load_mvrv(path: Path) -> pd.DataFrame:
    rows = json.loads(path.read_text())["data"]
    frame = pd.DataFrame.from_records(rows)
    frame["source_day"] = pd.to_datetime(frame.pop("time"), utc=True)
    frame["mvrv"] = frame.pop("CapMVRVCur").astype("float64")
    if set(frame.pop("asset")) != {"btc"} or not frame["mvrv"].gt(0).all():
        raise RuntimeError("MVRV asset or values differ from the frozen contract")
    if not frame["source_day"].is_monotonic_increasing or not frame["source_day"].is_unique:
        raise RuntimeError("MVRV source days must be unique and ordered")
    return frame


def trial_name(side: str, window: int, holding_days: int) -> str:
    return f"side={side}|window={window}|holding_days={holding_days}"
