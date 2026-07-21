"""Verify the frozen BTCUSDT 1h calendar-family data package offline."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.dataset.arrow_time import utc_datetimes
from tios.dataset.normalize import content_sha256

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/CALENDAR_UTC_DATA_PACKAGE_V1.json"


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
    package = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-calendar-utc-data-package-v1":
        raise ValueError("unsupported calendar data package")
    if package.get("execution_authority") != "NONE" or package.get("venue_connection") != "NONE":
        raise ValueError("calendar data package cannot contain trading authority")
    return package


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    base = package["base_dataset"]

    verify_file(root / base["manifest_path"], base["manifest_sha256"])
    verify_file(root / base["raw_manifest_path"], base["raw_manifest_sha256"])
    for source in package["source_documentation"]:
        verify_file(root / source["snapshot_path"], source["snapshot_sha256"])

    raw_manifest = json.loads((root / base["raw_manifest_path"]).read_text(encoding="utf-8"))
    archives = [
        item
        for item in raw_manifest["files"]
        if item["file"].startswith(base["raw_archive_selector"])
    ]
    if len(archives) != base["raw_archive_count"]:
        raise RuntimeError("raw archive count differs from the frozen calendar package")
    if sum(item["size"] for item in archives) != base["raw_archive_total_bytes"]:
        raise RuntimeError("raw archive byte total differs from the frozen calendar package")
    raw_root = root / base["raw_root"]
    for item in archives:
        path = raw_root / item["file"]
        if path.stat().st_size != item["size"]:
            raise RuntimeError(f"size mismatch for {path}")
        verify_file(path, item["sha256"])

    normalized = root / base["normalized_path"]
    verify_file(normalized, base["normalized_parquet_sha256"])
    table = pq.read_table(normalized).combine_chunks()
    if table.num_rows != base["rows"]:
        raise RuntimeError("normalized row count differs from the frozen calendar package")
    if content_sha256(table) != base["logical_content_sha256"]:
        raise RuntimeError("normalized logical content differs from the frozen calendar package")

    opens = utc_datetimes(table.column("timestamp_open_utc"))
    if str(opens[0]) != base["coverage_start_utc"] or str(opens[-1]) != base["coverage_end_utc"]:
        raise RuntimeError("normalized coverage differs from the frozen calendar package")
    if opens[0].weekday() != 4 or (opens[0] + timedelta(hours=1)).weekday() != 4:
        raise RuntimeError("UTC weekday derivation anchor failed")
    if (opens[71] + timedelta(hours=1)).weekday() != 0:  # Sunday 23:00 -> Monday 00:00
        raise RuntimeError("UTC week-boundary derivation anchor failed")

    non_adjacent = sum(right - left != timedelta(hours=1) for left, right in pairwise(opens))
    if non_adjacent != package["known_gaps"]["gap_count"]:
        raise RuntimeError("gap count differs from the frozen calendar package")

    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "raw_archives": len(archives),
        "rows": table.num_rows,
        "gaps": non_adjacent,
        "calendar_timezone": "UTC",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
