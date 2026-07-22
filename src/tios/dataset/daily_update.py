"""Refresh normalized klines from retained Binance REST pages.

Only bars whose exchange close timestamp is at or before one run-wide UTC cutoff
may be published.  Each refresh refetches the last retained open timestamp so a
previously partial row is replaced by the now-closed official row.

Run: uv run python -m tios.dataset.daily_update
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet

from tios.dataset.normalize import (
    DEC,
    RAW_COLUMNS,
    code_commit,
    content_sha256,
    dedup_sorted,
    to_canonical,
)

REST = "https://api.binance.com/api/v3/klines"
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "normalized_multi"
RAW_REST_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "rest_klines"
PAGE_LIMIT = 1000
MAX_PAGES_PER_FILE = 10_000
_INT_COLS = {"open_time", "close_time", "count"}
_META_VERSION = b"tios.daily_update.version"
_META_CURSOR = b"tios.daily_update.resume_open_ms"
_META_CUTOFF = b"tios.daily_update.cutoff_utc"
_META_KEYS = {_META_VERSION, _META_CURSOR, _META_CUTOFF}


def _klines_json_to_raw(rows: list[list[Any]]) -> pa.Table:
    """Convert Binance REST kline rows to the raw Arrow normalization schema."""
    cols: dict[str, pa.Array] = {}
    for idx, name in enumerate(RAW_COLUMNS):
        values = [r[idx] for r in rows]
        if name in _INT_COLS:
            cols[name] = pa.array([int(v) for v in values], pa.int64())
        elif name == "ignore":
            cols[name] = pa.array([str(v) for v in values], pa.string())
        else:
            cols[name] = pa.array([Decimal(str(v)) for v in values], DEC)
    return pa.table(cols)


def _append_dedup(existing: pa.Table, fresh: pa.Table) -> tuple[pa.Table, int]:
    """Replace existing duplicate opens with verified fresh closed rows."""
    fresh = fresh.sort_by("timestamp_open_utc")
    fresh, fresh_duplicates = dedup_sorted(fresh)
    fresh_opens = set(fresh.column("timestamp_open_utc").to_pylist())
    existing_opens = existing.column("timestamp_open_utc").to_pylist()
    keep = [index for index, value in enumerate(existing_opens) if value not in fresh_opens]
    retained = (
        existing.take(pa.array(keep, type=pa.int64()))
        if len(keep) != len(existing_opens)
        else existing
    )
    replaced = len(existing_opens) - len(keep)
    merged = pa.concat_tables([retained, fresh]).sort_by("timestamp_open_utc")
    return merged, replaced + fresh_duplicates


def fetch_klines(
    symbol: str, interval: str, start_ms: int, limit: int = PAGE_LIMIT
) -> list[list[Any]]:
    """Fetch one REST page of klines at or after ``start_ms``."""
    url = f"{REST}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())  # type: ignore[no-any-return]


def _fsync_directory(path: Path) -> bool:
    """Best-effort crash-durability sync after an already-committed replace."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        return False
    return True


def _atomic_write_bytes(path: Path, content: bytes) -> bool:
    """Publish complete bytes; return whether post-replace directory fsync succeeded."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
        return _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_parquet(path: Path, table: pa.Table) -> bool:
    """Publish a complete parquet; return post-replace directory-fsync status."""
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        pyarrow.parquet.write_table(table, temporary, compression="zstd")
        with temporary.open("rb") as retained:
            os.fsync(retained.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
        return _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _retain_page(
    symbol: str, interval: str, start_ms: int, rows: list[list[Any]]
) -> dict[str, object]:
    """Retain the exact decoded REST payload before filtering or normalization."""
    encoded = (json.dumps(rows, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = RAW_REST_ROOT / symbol / interval / f"{digest}.json"
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"retained REST page is corrupt: {path}")
        directory_synced = True
    else:
        directory_synced = _atomic_write_bytes(path, encoded)
    return {
        "path": path.relative_to(RAW_REST_ROOT.parent).as_posix(),
        "url": (
            f"{REST}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={PAGE_LIMIT}"
        ),
        "sha256": digest,
        "rows": len(rows),
        "directory_fsync": "CONFIRMED" if directory_synced else "BEST_EFFORT_FAILED",
    }


def _last_open_ms(table: pa.Table) -> int:
    """Return the last canonical open timestamp in milliseconds."""
    return int(table.column("timestamp_open_utc")[-1].value) // 1000


def _closed_existing(table: pa.Table, cutoff_utc: datetime) -> tuple[pa.Table, int]:
    """Remove pre-existing rows that were not closed at the captured cutoff."""
    closes = table.column("close_timestamp_utc").to_pylist()
    keep = [index for index, close in enumerate(closes) if close <= cutoff_utc]
    excluded = table.num_rows - len(keep)
    return (
        table.take(pa.array(keep, type=pa.int64())) if excluded else table,
        excluded,
    )


def _changed_overlap_count(existing: pa.Table, fresh: pa.Table) -> int:
    """Count overlapping opens whose complete canonical row actually changed."""
    existing_rows = {row["timestamp_open_utc"]: row for row in existing.to_pylist()}
    return sum(
        row["timestamp_open_utc"] in existing_rows
        and existing_rows[row["timestamp_open_utc"]] != row
        for row in fresh.to_pylist()
    )


def _cutoff_ms(cutoff_utc: datetime) -> int:
    if cutoff_utc.tzinfo is None or cutoff_utc.utcoffset() is None:
        raise ValueError("cutoff_utc must be timezone-aware")
    cutoff_utc = cutoff_utc.astimezone(UTC)
    return int(cutoff_utc.timestamp()) * 1000 + cutoff_utc.microsecond // 1000


def _embedded_refresh_cursor(table: pa.Table, current_cutoff: datetime) -> int | None:
    """Validate and return the parquet-committed refresh cursor, when present."""
    metadata = table.schema.metadata or {}
    present = _META_KEYS.intersection(metadata)
    if not present:
        return None
    if present != _META_KEYS:
        raise ValueError("parquet refresh metadata is incomplete")
    if metadata[_META_VERSION] != b"1":
        raise ValueError("parquet refresh metadata version is unsupported")
    try:
        cursor_text = metadata[_META_CURSOR].decode("ascii")
        cursor = int(cursor_text)
        retained_cutoff = datetime.fromisoformat(metadata[_META_CUTOFF].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("parquet refresh metadata is malformed") from error
    if cursor < 0 or str(cursor) != cursor_text:
        raise ValueError("parquet refresh cursor is noncanonical")
    if retained_cutoff.tzinfo is None or retained_cutoff.utcoffset() is None:
        raise ValueError("parquet refresh cutoff is not timezone-aware")
    if cursor > _cutoff_ms(retained_cutoff):
        raise ValueError("parquet refresh cursor is later than its embedded cutoff")
    if retained_cutoff.astimezone(UTC) > current_cutoff:
        raise ValueError("parquet refresh cutoff is later than the current cutoff")
    return cursor


def _with_refresh_metadata(table: pa.Table, cursor: int, cutoff_utc: datetime) -> pa.Table:
    """Bind recovery state to the same parquet publication as normalized rows."""
    return table.replace_schema_metadata(
        {
            _META_VERSION: b"1",
            _META_CURSOR: str(cursor).encode("ascii"),
            _META_CUTOFF: cutoff_utc.isoformat().encode("ascii"),
        }
    )


def update_file(
    path: Path, cutoff_utc: datetime, empty_start_ms: int | None = None
) -> dict[str, object]:
    """Refresh one parquet through ``cutoff_utc`` and atomically publish it."""
    symbol, interval = path.stem.split("_", 1)
    cutoff = _cutoff_ms(cutoff_utc)
    cutoff_utc = cutoff_utc.astimezone(UTC)
    retained = pyarrow.parquet.read_table(path)
    embedded_cursor = _embedded_refresh_cursor(retained, cutoff_utc)
    original = retained.replace_schema_metadata(None)
    if original.num_rows:
        if embedded_cursor is not None and embedded_cursor != _last_open_ms(original):
            raise ValueError(f"parquet refresh cursor conflicts with retained rows: {path.name}")
        existing, excluded_open = _closed_existing(original, cutoff_utc)
        # Overlap the last row that was closed at the cutoff. If every retained row was
        # still open, begin at the earliest original row so no coordinate is skipped.
        since = (
            _last_open_ms(existing)
            if existing.num_rows
            else int(original.column("timestamp_open_utc")[0].value) // 1000
        )
    else:
        if embedded_cursor is None:
            raise ValueError(f"empty parquet lacks committed refresh metadata: {path.name}")
        if empty_start_ms is not None and empty_start_ms != embedded_cursor:
            raise ValueError(f"status/parquet refresh cursor conflict: {path.name}")
        existing = original
        excluded_open = 0
        since = embedded_cursor
    resume_open_ms = since
    added = 0
    revised = 0
    source_pages: list[dict[str, object]] = []

    for _page_number in range(MAX_PAGES_PER_FILE):
        page = fetch_klines(symbol, interval, since, PAGE_LIMIT)
        if len(page) > PAGE_LIMIT:
            raise ValueError(f"REST page exceeded limit for {path.name}")
        source_pages.append(_retain_page(symbol, interval, since, page))
        if not page:
            break

        try:
            page_max_open = max(int(row[0]) for row in page)
        except (IndexError, TypeError, ValueError) as error:
            raise ValueError(f"malformed REST page for {path.name}") from error
        if page_max_open < since:
            raise ValueError(f"REST pagination did not advance for {path.name}")

        try:
            closed = [row for row in page if int(row[0]) >= since and int(row[6]) <= cutoff]
        except (IndexError, TypeError, ValueError) as error:
            raise ValueError(f"malformed REST page for {path.name}") from error
        if closed:
            raw = _klines_json_to_raw(closed)
            fresh = to_canonical(raw, "ms", symbol, interval)
            existing_opens = set(existing.column("timestamp_open_utc").to_pylist())
            fresh, _ = dedup_sorted(fresh.sort_by("timestamp_open_utc"))
            overlap = sum(
                value in existing_opens for value in fresh.column("timestamp_open_utc").to_pylist()
            )
            changed_overlap = _changed_overlap_count(existing, fresh)
            existing, _ = _append_dedup(existing, fresh)
            revised += changed_overlap
            added += fresh.num_rows - overlap

        if len(page) < PAGE_LIMIT:
            break
        next_since = page_max_open + 1
        if next_since <= since:
            raise ValueError(f"REST pagination did not advance for {path.name}")
        since = next_since
    else:
        raise RuntimeError(f"REST pagination exceeded {MAX_PAGES_PER_FILE} pages for {path.name}")

    final_resume_open_ms = _last_open_ms(existing) if existing.num_rows else resume_open_ms
    parquet_directory_synced = True
    if added or revised or excluded_open:
        parquet_directory_synced = _atomic_write_parquet(
            path, _with_refresh_metadata(existing, final_resume_open_ms, cutoff_utc)
        )
    coverage_end = str(existing.column("timestamp_open_utc")[-1]) if existing.num_rows else None
    return {
        "file": path.name,
        "added_rows": added,
        "revised_rows": revised,
        "excluded_open_rows": excluded_open,
        "resume_open_ms": final_resume_open_ms,
        "rows": existing.num_rows,
        "coverage_end_utc": coverage_end,
        "parquet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "content_sha256": content_sha256(existing),
        "parquet_directory_fsync": (
            "CONFIRMED" if parquet_directory_synced else "BEST_EFFORT_FAILED"
        ),
        "source_pages": source_pages,
    }


@contextmanager
def _process_lock(target: Path) -> Iterator[None]:
    """Refuse concurrent refresh processes for one normalized dataset."""
    target.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(os.fsencode(target.resolve())).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"tios-daily-update-{identity}.lock"
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("daily update is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _publish_manifest(target: Path, result: dict[str, object]) -> tuple[Path, bool, bool]:
    """Atomically publish the current manifest and its content-addressed archive."""
    encoded = (json.dumps(result, indent=2) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    archive = target / "manifests" / f"normalized_multi_manifest_{digest}.json"
    if archive.exists():
        if archive.read_bytes() != encoded:
            raise ValueError(f"content-addressed manifest is corrupt: {archive}")
        archive_synced = True
    else:
        archive_synced = _atomic_write_bytes(archive, encoded)
    current_synced = _atomic_write_bytes(target / "normalized_multi_manifest.json", encoded)
    return archive, archive_synced, current_synced


def _archive_status(target: Path, encoded: bytes) -> tuple[Path, bool]:
    digest = hashlib.sha256(encoded).hexdigest()
    path = target / "statuses" / f"daily_update_status_{digest}.json"
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"content-addressed status is corrupt: {path}")
        return path, True
    return path, _atomic_write_bytes(path, encoded)


def _bind_snapshot_status(
    snapshot: dict[str, object],
    results: list[dict[str, object]],
    status_archive: Path,
    status_sha256: str,
    cutoff_utc: datetime,
    target: Path,
) -> None:
    """Bind each updated table to immutable status bytes and complete counts."""
    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("normalized snapshot tables are malformed")
    for result in results:
        key = Path(cast(str, result["file"])).stem
        info = tables.get(key)
        if not isinstance(info, dict):
            raise ValueError(f"normalized snapshot is missing {key}")
        rest = info.get("rest_update_source")
        if not isinstance(rest, dict):
            raise ValueError(f"normalized snapshot lacks REST lineage for {key}")
        rest["status_manifest"] = {
            "path": status_archive.relative_to(target).as_posix(),
            "sha256": status_sha256,
            "last_run_utc": cutoff_utc.isoformat(),
        }
        rest["reported_revised_rows"] = result["revised_rows"]
        rest["reported_excluded_open_rows"] = result["excluded_open_rows"]


def _load_resume_cursors(target: Path) -> dict[str, int]:
    """Recover per-file cursors needed only when a prior run published zero rows."""
    path = target / "daily_update_status.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    updated = payload.get("updated", [])
    if not isinstance(updated, list):
        raise ValueError("daily update status has malformed updated rows")
    cursors: dict[str, int] = {}
    for item in updated:
        if not isinstance(item, dict):
            raise ValueError("daily update status has malformed updated row")
        file_name = item.get("file")
        cursor = item.get("resume_open_ms")
        if isinstance(file_name, str) and isinstance(cursor, int) and not isinstance(cursor, bool):
            cursors[file_name] = cursor
    return cursors


def main() -> None:
    # One cutoff applies to every file in this run; never admit an in-progress candle.
    cutoff_utc = datetime.now(tz=UTC)
    target = DEFAULT_DIR
    with _process_lock(target):
        resume_cursors = _load_resume_cursors(target)
        results = [
            update_file(path, cutoff_utc, resume_cursors.get(path.name))
            for path in sorted(target.glob("*.parquet"))
        ]
        total_added = sum(cast(int, result["added_rows"]) for result in results)
        total_revised = sum(cast(int, result["revised_rows"]) for result in results)
        total_excluded = sum(cast(int, result["excluded_open_rows"]) for result in results)
        status = {
            "last_run_utc": cutoff_utc.isoformat(),
            "closed_bar_cutoff_utc": cutoff_utc.isoformat(),
            "update_code": {
                "module": "src/tios/dataset/daily_update.py",
                "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "git_commit": code_commit(),
            },
            "files_updated": len(results),
            "bars_added": total_added,
            "bars_revised": total_revised,
            "open_rows_excluded": total_excluded,
            "target": str(target),
            "updated": results,
        }
        status_encoded = (json.dumps(status, indent=2, default=str) + "\n").encode()
        status_synced = _atomic_write_bytes(target / "daily_update_status.json", status_encoded)
        status_archive, status_archive_synced = _archive_status(target, status_encoded)
        from tios.dataset.normalize_multi import snapshot_existing

        snapshot = snapshot_existing()
        _bind_snapshot_status(
            snapshot,
            results,
            status_archive,
            hashlib.sha256(status_encoded).hexdigest(),
            cutoff_utc,
            target,
        )
        _, manifest_archive_synced, manifest_current_synced = _publish_manifest(target, snapshot)
        durability = all(
            [
                status_synced,
                status_archive_synced,
                manifest_archive_synced,
                manifest_current_synced,
                *(result["parquet_directory_fsync"] == "CONFIRMED" for result in results),
            ]
        )
        print(
            f"updated {len(results)} files, +{total_added} added, "
            f"{total_revised} revised, {total_excluded} open excluded in {target}; "
            f"directory_fsync={'CONFIRMED' if durability else 'BEST_EFFORT_FAILED'}"
        )


if __name__ == "__main__":
    main()
