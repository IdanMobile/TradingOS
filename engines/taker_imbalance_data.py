"""Read the frozen BTC Spot taker-imbalance package inside engine environments."""

from __future__ import annotations

import base64
import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]


def trial_name(interpretation: str, baseline_hours: int, threshold: float) -> str:
    return (
        f"interpretation={interpretation}|baseline_hours={baseline_hours}|threshold={threshold:.1f}"
    )


def load_spot(root: Path, package_path: str) -> pd.DataFrame:
    package: dict[str, Any] = json.loads((root / package_path).read_text())
    spot = package["spot_data"]
    early: list[list[str]] = []
    for archive in spot["early_archives"]:
        encoded = (root / archive["base64_path"]).read_bytes()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as zipped:
            early.extend(csv.reader(io.TextIOWrapper(zipped.open(zipped.namelist()[0]))))
    frame = pd.DataFrame(
        {
            "timestamp_open_utc": pd.to_datetime(
                [int(row[0]) for row in early], unit="ms", utc=True
            ),
            "open": [float(row[1]) for row in early],
            "close": [float(row[4]) for row in early],
            "close_timestamp_utc": pd.to_datetime(
                [int(row[6]) for row in early], unit="ms", utc=True
            ),
            "quote_volume": [float(row[7]) for row in early],
            "taker_buy_quote_volume": [float(row[10]) for row in early],
        }
    )
    existing = pd.read_parquet(
        root / spot["existing_normalized_path"],
        columns=[
            "timestamp_open_utc",
            "open",
            "close",
            "close_timestamp_utc",
            "quote_volume",
            "taker_buy_quote_volume",
        ],
    )
    for column in ("open", "close", "quote_volume", "taker_buy_quote_volume"):
        existing[column] = existing[column].astype(float)
    combined = pd.concat([frame, existing], ignore_index=True).sort_values("timestamp_open_utc")
    return combined.set_index("timestamp_open_utc", drop=False)
