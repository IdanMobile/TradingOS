"""Read-only retained inputs shared by funding-pressure engine harnesses."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pandas as pd


def load_spot(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["timestamp_open_utc", "open", "close"])
    frame = frame.set_index("timestamp_open_utc")[["open", "close"]].astype("float64")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise RuntimeError("Spot timestamps must be timezone-aware")
    if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise RuntimeError("Spot timestamps must be unique and ordered")
    return frame


def load_funding(root: Path) -> pd.DataFrame:
    records = []
    for path in sorted(root.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            member = archive.namelist()[0]
            reader = csv.DictReader(
                io.TextIOWrapper(archive.open(member), encoding="utf-8", newline="")
            )
            records.extend(reader)
    frame = pd.DataFrame.from_records(records)
    frame["calc_time"] = pd.to_datetime(frame["calc_time"].astype("int64"), unit="ms", utc=True)
    frame["last_funding_rate"] = frame["last_funding_rate"].astype("float64")
    frame["funding_interval_hours"] = frame["funding_interval_hours"].astype("int64")
    if not frame["calc_time"].is_monotonic_increasing or not frame["calc_time"].is_unique:
        raise RuntimeError("funding timestamps must be unique and ordered")
    return frame


def trial_name(polarity: str, lookback: int, threshold: float) -> str:
    return f"polarity={polarity}|lookback={lookback}|threshold={threshold:.4f}"
