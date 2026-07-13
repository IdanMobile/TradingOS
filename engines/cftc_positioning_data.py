"""Read-only frozen inputs shared by CFTC-positioning engine harnesses."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import timedelta
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]


def _decoded(root: Path, relative: str) -> bytes:
    return base64.b64decode((root / relative).read_bytes())


def load_positioning(root: Path, package_path: str) -> pd.DataFrame:
    package = json.loads((root / package_path).read_text())
    feature = package["cftc_feature"]
    rows = pd.read_csv(io.BytesIO(_decoded(root, feature["sources"][0]["base64_path"])))
    rows = rows[rows["cftc_contract_market_code"].astype(str) == "133741"].copy()
    rows["report_date"] = pd.to_datetime(rows["report_date_as_yyyy_mm_dd"], utc=True)
    exceptions = json.loads((root / feature["publication_exceptions_path"]).read_text())[
        "exceptions"
    ]
    rows["available_at"] = rows["report_date"] + pd.Timedelta(days=8)
    for report, published in exceptions.items():
        mask = rows["report_date"].eq(pd.Timestamp(report, tz="UTC"))
        exceptional = pd.Timestamp(published, tz="UTC") + pd.Timedelta(days=1)
        rows.loc[mask, "available_at"] = rows.loc[mask, "available_at"].clip(lower=exceptional)
    rows["net_share"] = (
        rows["noncomm_positions_long_all"] - rows["noncomm_positions_short_all"]
    ) / rows["open_interest_all"]
    frame = rows[["report_date", "available_at", "net_share"]].reset_index(drop=True)
    if not frame["report_date"].is_monotonic_increasing or not frame["report_date"].is_unique:
        raise RuntimeError("CFTC reports must be unique and ordered")
    if (
        not frame["available_at"].is_monotonic_increasing
        or not frame["net_share"].between(-1, 1).all()
    ):
        raise RuntimeError("CFTC availability or feature values violate the frozen contract")
    return frame


def _early_spot(root: Path, archives: list[dict[str, object]]) -> pd.DataFrame:
    frames = []
    names = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "count",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]
    for archive in archives:
        payload = _decoded(root, str(archive["base64_path"]))
        with zipfile.ZipFile(io.BytesIO(payload)) as zipped:
            raw = pd.read_csv(zipped.open(zipped.namelist()[0]), header=None, names=names)
        raw["timestamp_open_utc"] = pd.to_datetime(raw["open_time"], unit="ms", utc=True)
        frames.append(raw.set_index("timestamp_open_utc")[["open", "close"]])
    return pd.concat(frames).astype("float64")


def load_spot(root: Path, package_path: str) -> pd.DataFrame:
    package = json.loads((root / package_path).read_text())
    spot = package["spot_execution"]
    early = _early_spot(root, spot["early_archives"])
    existing = pd.read_parquet(
        root / spot["existing_normalized_path"],
        columns=["timestamp_open_utc", "open", "close"],
    ).set_index("timestamp_open_utc")[["open", "close"]]
    frame = pd.concat([early, existing]).sort_index().astype("float64")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise RuntimeError("Spot timestamps must be timezone-aware")
    if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise RuntimeError("Spot timestamps must be unique and ordered")
    if any(
        right - left <= timedelta(0)
        for left, right in zip(frame.index, frame.index[1:], strict=False)
    ):
        raise RuntimeError("Spot timestamps must increase")
    return frame


def trial_name(interpretation: str, baseline_weeks: int, threshold: float) -> str:
    return (
        f"interpretation={interpretation}|baseline_weeks={baseline_weeks}|threshold={threshold:.1f}"
    )
