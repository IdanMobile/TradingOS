"""Verify the frozen BTC MVRV plus Spot data package offline."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.dataset.normalize import content_sha256

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/BTC_MVRV_DATA_PACKAGE_V1.json"


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
    if package.get("schema") != "tios-btc-mvrv-data-package-v1":
        raise ValueError("unsupported MVRV data package")
    if package.get("execution_authority") != "NONE" or package.get("venue_connection") != "NONE":
        raise ValueError("MVRV package cannot contain trading authority")
    return package


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise RuntimeError("package timestamp must be UTC-aware")
    return parsed


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    feature = package["mvrv_feature"]
    raw = root / feature["raw_path"]
    verify_file(raw, feature["tracked_raw_sha256"])
    raw_bytes = raw.read_bytes()
    if len(raw_bytes) != feature["tracked_raw_bytes"] or not raw_bytes.endswith(b"\n"):
        raise RuntimeError("tracked MVRV archive transform differs from frozen package")
    retrieved = raw_bytes[:-1]
    if (
        len(retrieved) != feature["retrieved_http_body_bytes"]
        or hashlib.sha256(retrieved).hexdigest() != feature["retrieved_http_body_sha256"]
    ):
        raise RuntimeError("retrieved MVRV HTTP body differs from frozen package")

    catalog_path = root / feature["catalog_entry_path"]
    verify_file(catalog_path, feature["catalog_entry_sha256"])
    if catalog_path.stat().st_size != feature["catalog_entry_bytes"]:
        raise RuntimeError("MVRV catalog entry byte size differs from frozen package")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    contract = feature["metric_contract"]
    for key in ("metric", "full_name", "description", "unit", "data_type", "type"):
        if catalog.get(key) != contract[key]:
            raise RuntimeError(f"MVRV catalog contract drift: {key}")
    frequencies = catalog.get("frequencies")
    if not any(
        item.get("frequency") == contract["frequency"]
        and contract["asset"] in item.get("assets", [])
        for item in frequencies
    ):
        raise RuntimeError("MVRV catalog frequency or asset support drift")

    payload = json.loads(raw_bytes)
    values = payload.get("data")
    if not isinstance(values, list) or len(values) != feature["observations"]:
        raise RuntimeError("MVRV observation count differs from frozen package")
    timestamps: list[datetime] = []
    logical = hashlib.sha256()
    metric = contract["metric"]
    for index, row in enumerate(values):
        if not isinstance(row, dict) or set(row) != {"asset", "time", metric}:
            raise RuntimeError(f"MVRV row schema drift at index {index}")
        if row["asset"] != contract["asset"]:
            raise RuntimeError("MVRV asset drift")
        timestamp = _parse_utc(row["time"])
        value = Decimal(row[metric])
        if timestamp.time() != datetime.min.time():
            raise RuntimeError("MVRV timestamp is not UTC midnight")
        if not value.is_finite() or value <= 0:
            raise RuntimeError("MVRV value must be positive and finite")
        timestamps.append(timestamp)
        logical.update(f"{row['time']},{row[metric]}\n".encode())
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise RuntimeError("MVRV timestamps are duplicate or non-monotone")
    if logical.hexdigest() != feature["logical_records_sha256"]:
        raise RuntimeError("MVRV logical records differ from frozen package")
    if (
        timestamps[0].isoformat() != feature["coverage_start_utc"]
        or timestamps[-1].isoformat() != feature["coverage_end_utc"]
    ):
        raise RuntimeError("MVRV coverage differs from frozen package")
    gaps = [
        {"left_utc": left.isoformat(), "right_utc": right.isoformat()}
        for left, right in zip(timestamps, timestamps[1:], strict=False)
        if right - left != timedelta(days=1)
    ]
    if gaps != feature["known_gaps"]:
        raise RuntimeError("MVRV gap set differs from frozen package")

    start = _parse_utc(feature["campaign_source_start_utc"])
    end = _parse_utc(feature["campaign_source_end_utc"])
    campaign = [value for value in timestamps if start <= value <= end]
    if len(campaign) != feature["campaign_observations"]:
        raise RuntimeError("campaign MVRV count differs from frozen package")
    if feature["availability_lag_full_utc_days"] != 2:
        raise RuntimeError("MVRV availability lag differs from frozen contract")

    spot = package["spot_execution"]
    verify_file(root / spot["manifest_path"], spot["manifest_sha256"])
    parquet = root / spot["normalized_path"]
    verify_file(parquet, spot["normalized_parquet_sha256"])
    table = pq.read_table(parquet).combine_chunks()
    if table.num_rows != spot["rows"] or content_sha256(table) != spot["logical_content_sha256"]:
        raise RuntimeError("Spot normalized content differs from frozen package")
    opens = set(table.column("timestamp_open_utc").to_pylist())
    lag = timedelta(days=2, hours=1)
    missing = sum(value + lag not in opens for value in campaign)
    if missing != spot["missing_expected_entry_opens"]:
        raise RuntimeError("MVRV-to-Spot expected-open mapping differs from frozen package")
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "mvrv_observations": len(values),
        "campaign_observations": len(campaign),
        "known_gap_count": len(gaps),
        "spot_rows": table.num_rows,
        "missing_expected_entry_opens": missing,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
