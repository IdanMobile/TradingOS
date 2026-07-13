"""Verify the frozen funding-feature plus Spot-execution package offline."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.dataset.normalize import content_sha256

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/FUNDING_PRESSURE_SPOT_DATA_PACKAGE_V1.json"


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


def _months(first: str, last: str) -> list[str]:
    year, month = map(int, first.split("-"))
    final = tuple(map(int, last.split("-")))
    result = []
    while (year, month) <= final:
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def load_package(path: Path = PACKAGE) -> dict[str, Any]:
    package = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-funding-pressure-spot-data-package-v1":
        raise ValueError("unsupported funding-pressure data package")
    if package.get("execution_authority") != "NONE" or package.get("venue_connection") != "NONE":
        raise ValueError("funding-pressure package cannot contain trading authority")
    return package


def _verify_funding(package: dict[str, Any], root: Path) -> tuple[list[int], int]:
    feature = package["funding_feature"]
    raw_root = root / feature["raw_root"]
    months = _months(feature["coverage_first_month"], feature["coverage_last_month"])
    expected_names = [
        feature["archive_name_template"].replace("YYYY-MM", month) for month in months
    ]
    paths = sorted(raw_root.glob("*.zip"))
    if [path.name for path in paths] != expected_names:
        raise RuntimeError("funding archive month/name set differs from frozen package")

    manifest = [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != feature["archive_manifest_sha256"]:
        raise RuntimeError("funding archive manifest root differs from frozen package")
    byte_total = sum(path.stat().st_size for path in paths)
    if len(paths) != feature["archive_count"] or byte_total != feature["archive_total_bytes"]:
        raise RuntimeError("funding archive count or byte total differs from frozen package")

    timestamps: list[int] = []
    logical = hashlib.sha256()
    intervals: set[int] = set()
    expected_header = feature["csv_header"]
    for path, month in zip(paths, months, strict=True):
        with zipfile.ZipFile(path) as archive:
            expected_member = f"BTCUSDT-fundingRate-{month}.csv"
            if archive.namelist() != [expected_member]:
                raise RuntimeError(f"unexpected ZIP member set in {path}")
            stream = io.TextIOWrapper(archive.open(expected_member), encoding="utf-8", newline="")
            reader = csv.DictReader(stream)
            if reader.fieldnames != expected_header:
                raise RuntimeError(f"funding schema drift in {path}")
            for row in reader:
                try:
                    calc_time = int(row["calc_time"])
                    interval = int(row["funding_interval_hours"])
                    rate = Decimal(row["last_funding_rate"])
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise RuntimeError(f"invalid funding record in {path}") from exc
                if not rate.is_finite() or not math.isfinite(float(rate)):
                    raise RuntimeError(f"non-finite funding rate in {path}")
                observed_month = datetime.fromtimestamp(calc_time / 1000, UTC).strftime("%Y-%m")
                if observed_month != month:
                    raise RuntimeError(f"funding record outside archive month in {path}")
                timestamps.append(calc_time)
                intervals.add(interval)
                logical.update(f"{calc_time},{interval},{row['last_funding_rate']}\n".encode())

    if len(timestamps) != feature["observations"]:
        raise RuntimeError("funding observation count differs from frozen package")
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise RuntimeError("duplicate or non-monotone funding calc_time")
    endpoints = (timestamps[0], timestamps[-1])
    expected_endpoints = (feature["first_calc_time_ms"], feature["last_calc_time_ms"])
    if endpoints != expected_endpoints:
        raise RuntimeError("funding timestamp coverage differs from frozen package")
    if sorted(intervals) != feature["observed_interval_hours"]:
        raise RuntimeError("funding interval set differs from frozen package")
    if logical.hexdigest() != feature["logical_records_sha256"]:
        raise RuntimeError("funding logical records differ from frozen package")
    return timestamps, len(paths)


def _verify_spot(package: dict[str, Any], timestamps: list[int], root: Path) -> tuple[int, int]:
    spot = package["spot_execution"]
    verify_file(root / spot["manifest_path"], spot["manifest_sha256"])
    parquet = root / spot["normalized_path"]
    verify_file(parquet, spot["normalized_parquet_sha256"])
    table = pq.read_table(parquet).combine_chunks()
    if table.num_rows != spot["rows"] or content_sha256(table) != spot["logical_content_sha256"]:
        raise RuntimeError("Spot normalized content differs from frozen package")
    opens = table.column("timestamp_open_utc").to_pylist()
    if str(opens[0]) != spot["coverage_start_utc"] or str(opens[-1]) != spot["coverage_end_utc"]:
        raise RuntimeError("Spot coverage differs from frozen package")
    open_set = set(opens)
    missing = 0
    for value in timestamps:
        available = datetime.fromtimestamp(value / 1000, UTC)
        expected = available.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if expected <= available:
            raise RuntimeError("same-open funding mapping detected")
        missing += expected not in open_set
    if missing != spot["missing_expected_entry_opens"]:
        raise RuntimeError("funding-to-Spot expected-open mapping differs from frozen package")
    return table.num_rows, missing


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    for source in package["source_documentation"]:
        verify_file(root / source["snapshot_path"], source["snapshot_sha256"])
    timestamps, archive_count = _verify_funding(package, root)
    rows, missing = _verify_spot(package, timestamps, root)
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "funding_archives": archive_count,
        "funding_observations": len(timestamps),
        "spot_rows": rows,
        "missing_expected_entry_opens": missing,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
