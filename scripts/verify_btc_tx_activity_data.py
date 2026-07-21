"""Verify the frozen confirmed-transaction plus Spot data package offline."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.dataset.arrow_time import utc_datetimes
from tios.dataset.normalize import content_sha256

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/BTC_TX_ACTIVITY_DATA_PACKAGE_V1.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing pinned file: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}: expected {expected}, found {actual}")


def load_package(path: Path = PACKAGE) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-btc-tx-activity-data-package-v1":
        raise ValueError("unsupported transaction-activity data package")
    if package.get("execution_authority") != "NONE" or package.get("venue_connection") != "NONE":
        raise ValueError("transaction-activity package cannot contain trading authority")
    return package


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise RuntimeError("package timestamp must be UTC-aware")
    return parsed


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    feature = package["activity_feature"]
    raw = root / feature["raw_path"]
    verify_file(raw, feature["raw_sha256"])
    if raw.stat().st_size != feature["raw_bytes"]:
        raise RuntimeError("activity response byte size differs from frozen package")
    payload = json.loads(raw.read_text(encoding="utf-8"))
    for key, expected in feature["response_contract"].items():
        if payload.get(key) != expected:
            raise RuntimeError(f"activity response metadata drift: {key}")
    values = payload.get("values")
    if not isinstance(values, list) or len(values) != feature["observations"]:
        raise RuntimeError("activity observation count differs from frozen package")

    timestamps: list[datetime] = []
    logical = hashlib.sha256()
    for index, row in enumerate(values):
        if not isinstance(row, dict) or set(row) != {"x", "y"}:
            raise RuntimeError(f"activity row schema drift at index {index}")
        timestamp = datetime.fromtimestamp(int(row["x"]), UTC)
        count = float(row["y"])
        if timestamp.time() != datetime.min.time():
            raise RuntimeError("activity timestamp is not UTC midnight")
        if not math.isfinite(count) or count <= 0 or not count.is_integer():
            raise RuntimeError("activity count must be a positive finite integer value")
        timestamps.append(timestamp)
        logical.update(f"{int(row['x'])},{count:.1f}\n".encode())
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise RuntimeError("activity timestamps are duplicate or non-monotone")
    if logical.hexdigest() != feature["logical_records_sha256"]:
        raise RuntimeError("activity logical records differ from frozen package")
    if (
        timestamps[0].isoformat() != feature["coverage_start_utc"]
        or timestamps[-1].isoformat() != feature["coverage_end_utc"]
    ):
        raise RuntimeError("activity coverage differs from frozen package")

    gaps = []
    for left, right in zip(timestamps, timestamps[1:], strict=False):
        if right - left != timedelta(days=1):
            gaps.append(
                {
                    "left_utc": left.isoformat(),
                    "right_utc": right.isoformat(),
                    "missing_daily_observations": (right - left).days - 1,
                }
            )
    if gaps != feature["known_gaps"]:
        raise RuntimeError("activity gap set differs from frozen package")

    start = _parse_utc(feature["campaign_source_start_utc"])
    end = _parse_utc(feature["campaign_source_end_utc"])
    campaign = [value for value in timestamps if start <= value <= end]
    if len(campaign) != feature["campaign_observations"]:
        raise RuntimeError("campaign activity count differs from frozen package")
    if feature["availability_lag_full_utc_days"] != 2:
        raise RuntimeError("activity availability lag differs from frozen contract")

    spot = package["spot_execution"]
    verify_file(root / spot["manifest_path"], spot["manifest_sha256"])
    parquet = root / spot["normalized_path"]
    verify_file(parquet, spot["normalized_parquet_sha256"])
    table = pq.read_table(parquet).combine_chunks()
    if table.num_rows != spot["rows"] or content_sha256(table) != spot["logical_content_sha256"]:
        raise RuntimeError("Spot normalized content differs from frozen package")
    opens = set(utc_datetimes(table.column("timestamp_open_utc")))
    lag = timedelta(days=2, hours=1)
    missing = sum(value + lag not in opens for value in campaign)
    if missing != spot["missing_expected_entry_opens"]:
        raise RuntimeError("activity-to-Spot expected-open mapping differs from frozen package")
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "activity_observations": len(values),
        "campaign_observations": len(campaign),
        "known_gap_count": len(gaps),
        "spot_rows": table.num_rows,
        "missing_expected_entry_opens": missing,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
