"""Verify or restore the frozen canonical BTCUSDT 5-minute dataset.

The default mode is strictly offline and read-only. ``--rebuild`` recreates the
normalized Parquet from already-present pinned archives. Network access is only
possible when the operator explicitly supplies ``--fetch``; fetched bytes must
match the tracked source manifest before they are installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.dataset.download import fetch  # noqa: E402
from tios.dataset.normalize import (  # noqa: E402
    content_sha256,
    dedup_sorted,
    parse_zip,
    to_canonical,
)

DEFAULT_MANIFEST = ROOT / "data/raw/manifests/DS-CRYPTO-SPOT-BTCUSDT-5M-V1.source.json"
SCHEMA = "tios-canonical-source-manifest-v1"
SOURCE_PREFIX = "https://data.binance.vision/data/spot/monthly/klines"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"{field} must be repository-relative: {value!r}")
    return path


def _months() -> list[str]:
    result: list[str] = []
    year, month = 2021, 1
    while (year, month) <= (2026, 6):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if (manifest.get("instrument"), manifest.get("interval")) != ("BTCUSDT", "5m"):
        raise ValueError("manifest is not the canonical BTCUSDT 5m dataset")

    layout = manifest.get("local_layout", {})
    _portable_path(layout.get("raw_root"), "local_layout.raw_root")
    _portable_path(layout.get("normalized_path"), "local_layout.normalized_path")

    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 66:
        raise ValueError("manifest must contain exactly 66 monthly source archives")
    if [item.get("month") for item in files] != _months():
        raise ValueError("manifest months must be ordered and complete from 2021-01 to 2026-06")

    for index, item in enumerate(files):
        month = item["month"]
        filename = f"BTCUSDT-5m-{month}.zip"
        expected_path = f"BTCUSDT/5m/{filename}"
        expected_url = f"{SOURCE_PREFIX}/{expected_path}"
        if str(_portable_path(item.get("path"), f"files[{index}].path")) != expected_path:
            raise ValueError(f"unexpected source path for {month}")
        if item.get("url") != expected_url:
            raise ValueError(f"unexpected source URL for {month}")
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid SHA-256 for {month}")
        if not isinstance(item.get("size"), int) or item["size"] <= 0:
            raise ValueError(f"invalid byte size for {month}")

    normalized = manifest.get("normalized", {})
    parquet = normalized.get("parquet", {})
    required = {
        "rows": 577803,
        "content_sha256": "3ec05eb0ea618310209ae92de4bf1940b929ed2c889bccb0b3f749ff0a8a17fa",
    }
    if any(normalized.get(key) != value for key, value in required.items()):
        raise ValueError("normalized logical-content pins do not match the canonical dataset")
    if (
        parquet.get("sha256") != "d4d6b3306c44e242f3fb7f71c44bacabf9a6af1f1f8d507ca2de0853b6a727d0"
        or parquet.get("size") != 35542487
    ):
        raise ValueError("normalized Parquet byte pins do not match the canonical dataset")
    return manifest


def verify_file(path: Path, expected_sha256: str, expected_size: int, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    size = path.stat().st_size
    if size != expected_size:
        raise RuntimeError(f"{label} size mismatch: expected {expected_size}, found {size}")
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise RuntimeError(f"{label} SHA-256 mismatch: expected {expected_sha256}, found {digest}")


def verify_sources(manifest: dict[str, Any], raw_root: Path) -> None:
    for item in manifest["files"]:
        verify_file(
            raw_root / item["path"],
            item["sha256"],
            item["size"],
            f"source archive {item['month']}",
        )


def fetch_missing(
    manifest: dict[str, Any],
    raw_root: Path,
    fetcher: Callable[[str], bytes] = fetch,
) -> int:
    """Fetch only missing archives and install each one after pinned-hash validation."""
    installed = 0
    for item in manifest["files"]:
        destination = raw_root / item["path"]
        if destination.exists():
            verify_file(
                destination,
                item["sha256"],
                item["size"],
                f"source archive {item['month']}",
            )
            continue

        data = fetcher(item["url"])
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != item["size"] or digest != item["sha256"]:
            raise RuntimeError(
                f"downloaded source archive {item['month']} does not match its frozen pins"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        installed += 1
    return installed


def _verify_logical_table(table: pa.Table, manifest: dict[str, Any], dropped: int) -> None:
    expected = manifest["normalized"]
    if table.num_rows != expected["rows"]:
        raise RuntimeError(
            f"normalized row-count mismatch: expected {expected['rows']}, found {table.num_rows}"
        )
    if dropped != expected["dropped_duplicate_open_timestamps"]:
        raise RuntimeError(
            "normalized duplicate count mismatch: "
            f"expected {expected['dropped_duplicate_open_timestamps']}, found {dropped}"
        )
    # Parquet readers may choose different row-group chunking. Canonicalize that
    # implementation detail before checking the logical Arrow-stream digest.
    digest = content_sha256(table.combine_chunks())
    if digest != expected["content_sha256"]:
        raise RuntimeError(
            f"normalized content SHA-256 mismatch: expected {expected['content_sha256']}, "
            f"found {digest}"
        )
    opens = table.column("timestamp_open_utc")
    coverage = (str(opens[0]), str(opens[-1]))
    expected_coverage = (expected["coverage_start_utc"], expected["coverage_end_utc"])
    if coverage != expected_coverage:
        raise RuntimeError(
            f"normalized coverage mismatch: expected {expected_coverage}, found {coverage}"
        )


def verify_normalized(manifest: dict[str, Any], output: Path) -> None:
    parquet = manifest["normalized"]["parquet"]
    verify_file(output, parquet["sha256"], parquet["size"], "normalized Parquet")
    table = pq.read_table(output)
    _verify_logical_table(table, manifest, dropped=0)


def rebuild(manifest: dict[str, Any], raw_root: Path, output: Path) -> None:
    """Rebuild atomically from pinned local archives, preserving any valid old output."""
    required_version = manifest["normalized"]["parquet"]["pyarrow_version"]
    if pa.__version__ != required_version:
        raise RuntimeError(
            "exact Parquet reproduction requires "
            f"pyarrow {required_version}; found {pa.__version__}"
        )
    verify_sources(manifest, raw_root)

    tables: list[pa.Table] = []
    for item in manifest["files"]:
        raw, detection = parse_zip(raw_root / item["path"], item["month"])
        tables.append(to_canonical(raw, detection.detected_unit, "BTCUSDT", "5m"))
    merged = pa.concat_tables(tables).sort_by("timestamp_open_utc")
    merged, dropped = dedup_sorted(merged)
    _verify_logical_table(merged, manifest, dropped)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".part")
    try:
        pq.write_table(merged, temporary, compression="zstd")
        parquet = manifest["normalized"]["parquet"]
        verify_file(temporary, parquet["sha256"], parquet["size"], "rebuilt Parquet")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_path(override: Path | None, manifest_value: str) -> Path:
    return override if override is not None else ROOT / manifest_value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="rebuild from local pinned archives without network access",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="explicitly allow public downloads for missing archives, then rebuild",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    layout = manifest["local_layout"]
    raw_root = _resolve_path(args.raw_root, layout["raw_root"])
    output = _resolve_path(args.output, layout["normalized_path"])

    fetched = fetch_missing(manifest, raw_root) if args.fetch else 0
    if args.fetch or args.rebuild:
        rebuild(manifest, raw_root, output)
        mode = "RESTORED"
    else:
        verify_sources(manifest, raw_root)
        verify_normalized(manifest, output)
        mode = "VERIFIED_OFFLINE"
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "mode": mode,
                "network_allowed": args.fetch,
                "fetched_archives": fetched,
                "status": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
