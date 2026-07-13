"""Read-only retained inputs shared by transaction-activity engine harnesses."""

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


def load_activity(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text())
    frame = pd.DataFrame.from_records(payload["values"])
    frame["source_day"] = pd.to_datetime(frame.pop("x"), unit="s", utc=True)
    counts = frame.pop("y").astype("float64")
    if not (counts > 0).all() or not (counts == counts.astype("int64")).all():
        raise RuntimeError("activity counts must be positive integers")
    frame["count"] = counts.astype("int64")
    if not frame["source_day"].is_monotonic_increasing or not frame["source_day"].is_unique:
        raise RuntimeError("activity source days must be unique and ordered")
    if not (frame["source_day"].dt.time == pd.Timestamp(0).time()).all():
        raise RuntimeError("activity source days must be UTC midnights")
    return frame


def trial_name(side: str, window: int, holding_days: int) -> str:
    return f"side={side}|window={window}|holding_days={holding_days}"
