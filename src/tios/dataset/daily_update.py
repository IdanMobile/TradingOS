"""Keep the frozen klines dataset fresh by appending only the newest bars.

Instead of re-downloading history, this reads each normalized parquet, asks
Binance's REST klines API for bars *after* the last one it holds, and appends them
through the same canonical schema + dedup as the bulk normalizer. Decoded REST pages
are retained by content hash before use, and the normalized manifest records the new
coverage, source references, and hashes per refresh.

Run: uv run python -m tios.dataset.daily_update           (updates data/normalized_multi)
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
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
_INT_COLS = {"open_time", "close_time", "count"}


def _klines_json_to_raw(rows: list[list[Any]]) -> pa.Table:
    """Binance REST kline rows -> the raw arrow table the normalizer expects (ms times)."""
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
    """Concatenate, sort, and drop rows repeating an open timestamp (keep existing)."""
    merged = pa.concat_tables([existing, fresh]).sort_by("timestamp_open_utc")
    deduped, dropped = dedup_sorted(merged)
    return deduped, dropped


def fetch_klines(symbol: str, interval: str, start_ms: int, limit: int = 1000) -> list[list[Any]]:
    """One REST page of klines at/after start_ms (network; caller paginates)."""
    url = f"{REST}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())  # type: ignore[no-any-return]


def _retain_page(
    symbol: str, interval: str, start_ms: int, rows: list[list[Any]]
) -> dict[str, object]:
    """Retain the exact decoded REST payload before it can change normalized data."""
    encoded = (json.dumps(rows, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = RAW_REST_ROOT / symbol / interval / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(encoded)
    return {
        "path": path.relative_to(RAW_REST_ROOT.parent).as_posix(),
        "url": f"{REST}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit=1000",
        "sha256": digest,
        "rows": len(rows),
    }


def _last_open_ms(table: pa.Table) -> int:
    """Last open timestamp in ms (canonical stores µs)."""
    return int(table.column("timestamp_open_utc")[-1].value) // 1000


def update_file(path: Path) -> dict[str, object]:
    symbol, interval = path.stem.split("_", 1)
    existing = pyarrow.parquet.read_table(path)
    since = _last_open_ms(existing) + 1
    added = 0
    source_pages = []
    while True:
        page = fetch_klines(symbol, interval, since)
        source_pages.append(_retain_page(symbol, interval, since, page))
        page = [row for row in page if int(row[0]) >= since]
        if not page:
            break
        raw = _klines_json_to_raw(page)
        fresh = to_canonical(raw, "ms", symbol, interval)
        existing, _ = _append_dedup(existing, fresh)
        added += fresh.num_rows
        since = _last_open_ms(existing) + 1
        if len(page) < 1000:  # caught up to the latest closed/most-recent bar
            break
    if added:
        pyarrow.parquet.write_table(existing, path, compression="zstd")
    return {
        "file": path.name,
        "added_rows": added,
        "rows": existing.num_rows,
        "coverage_end_utc": str(existing.column("timestamp_open_utc")[-1]),
        "parquet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "content_sha256": content_sha256(existing),
        "source_pages": source_pages,
    }


def main() -> None:
    # ONLY the refreshable multi-set. Never touch data/normalized/ — that is the frozen,
    # checksum-pinned bake-off dataset the tests and validation depend on.
    target = DEFAULT_DIR
    target.mkdir(parents=True, exist_ok=True)
    results = [update_file(p) for p in sorted(target.glob("*.parquet"))]
    total = sum(cast(int, r["added_rows"]) for r in results)
    status = {
        "last_run_utc": datetime.now(tz=UTC).isoformat(),
        "update_code": {
            "module": "src/tios/dataset/daily_update.py",
            "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "git_commit": code_commit(),
        },
        "files_updated": len(results),
        "bars_added": total,
        "target": str(target),
        "updated": results,
    }
    (target / "daily_update_status.json").write_text(
        json.dumps(status, indent=2, default=str) + "\n"
    )
    from tios.dataset.normalize_multi import snapshot_existing, write_manifest

    write_manifest(snapshot_existing())
    print(f"updated {len(results)} files, +{total} bars in {target}")


if __name__ == "__main__":
    main()
