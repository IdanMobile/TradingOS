"""Normalization to the canonical schema (T-004-02, REQ-007, converter C5).

Implements specs/CANONICAL_BAKEOFF_DATASET_V1.md incl. Amendment A1: Binance
switched kline timestamps ms→µs starting with files dated 2025-01-01. The unit
is detected explicitly per file, cross-checked against the file's month, and
recorded in the normalized manifest (surfaced by the quality report).

Run: uv run python -m tios.dataset.normalize
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv
import pyarrow.parquet

from tios.dataset.download import INSTRUMENTS, INTERVALS, RAW_ROOT, months

NORM_ROOT = Path(__file__).resolve().parents[3] / "data" / "normalized"
NORM_MANIFEST = NORM_ROOT / "normalized_manifest.json"

RAW_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_base", "taker_buy_quote", "ignore",
]  # fmt: skip
DEC = pa.decimal128(38, 8)
RAW_TYPES: dict[str, pa.DataType] = {
    "open_time": pa.int64(),
    "open": DEC, "high": DEC, "low": DEC, "close": DEC, "volume": DEC,
    "close_time": pa.int64(),
    "quote_volume": DEC,
    "count": pa.int64(),
    "taker_buy_base": DEC, "taker_buy_quote": DEC,
    "ignore": pa.string(),
}  # fmt: skip

TS = pa.timestamp("us", tz="UTC")
CANONICAL_SCHEMA = pa.schema(
    [
        ("timestamp_open_utc", TS),
        ("open", DEC),
        ("high", DEC),
        ("low", DEC),
        ("close", DEC),
        ("volume_base", DEC),
        ("close_timestamp_utc", TS),
        ("quote_volume", DEC),
        ("trade_count", pa.int64()),
        ("taker_buy_base_volume", DEC),
        ("taker_buy_quote_volume", DEC),
        ("source", pa.string()),
        ("instrument", pa.string()),
        ("interval", pa.string()),
    ]
)
SOURCE_TAG = "binance-public-data:spot/monthly/klines"

# Amendment A1: epoch-ms values are ~1.7e12; epoch-µs ~1.7e15. 1e14 cleanly separates
# them for any date this project can encounter (1e14 µs = 1973, 1e14 ms = year 5138).
UNIT_THRESHOLD = 10**14
Unit = Literal["ms", "us"]


@dataclass
class FileDetection:
    file: str
    detected_unit: Unit
    expected_unit: Unit
    rows: int


def expected_unit_for_month(month: str) -> Unit:
    return "us" if month >= "2025-01" else "ms"


def detect_unit(first_open_time: int) -> Unit:
    return "us" if first_open_time >= UNIT_THRESHOLD else "ms"


def parse_zip(zip_path: Path, month: str) -> tuple[pa.Table, FileDetection]:
    """Read one monthly kline zip into a raw arrow table; detect timestamp unit."""
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        data = z.read(name)
    skip = 1 if data.startswith(b"open_time") else 0  # future-proof: optional header
    table = pyarrow.csv.read_csv(
        io.BytesIO(data),
        read_options=pyarrow.csv.ReadOptions(column_names=RAW_COLUMNS, skip_rows=skip),
        convert_options=pyarrow.csv.ConvertOptions(column_types=RAW_TYPES),
    )
    if table.num_rows == 0:
        raise ValueError(f"empty kline file: {zip_path}")
    first = table.column("open_time")[0].as_py()
    det = FileDetection(
        file=zip_path.name,
        detected_unit=detect_unit(int(first)),
        expected_unit=expected_unit_for_month(month),
        rows=table.num_rows,
    )
    if det.detected_unit != det.expected_unit:
        raise ValueError(
            f"{zip_path.name}: detected {det.detected_unit} but month {month} "
            f"implies {det.expected_unit} (Amendment A1 violation — investigate)"
        )
    return table, det


def to_canonical(raw: pa.Table, unit: Unit, instrument: str, interval: str) -> pa.Table:
    """Convert one raw table to the canonical schema. Both unit regimes converge to µs UTC."""
    factor = 1000 if unit == "ms" else 1
    n = raw.num_rows

    def ts(col: str) -> pa.Array:
        scaled = pc.multiply_checked(raw.column(col), pa.scalar(factor, pa.int64()))
        return scaled.combine_chunks().cast(TS)

    const = lambda v: pa.array([v] * n, pa.string())  # noqa: E731
    return pa.table(
        {
            "timestamp_open_utc": ts("open_time"),
            "open": raw.column("open"),
            "high": raw.column("high"),
            "low": raw.column("low"),
            "close": raw.column("close"),
            "volume_base": raw.column("volume"),
            "close_timestamp_utc": ts("close_time"),
            "quote_volume": raw.column("quote_volume"),
            "trade_count": raw.column("count"),
            "taker_buy_base_volume": raw.column("taker_buy_base"),
            "taker_buy_quote_volume": raw.column("taker_buy_quote"),
            "source": const(SOURCE_TAG),
            "instrument": const(instrument),
            "interval": const(interval),
        },
        schema=CANONICAL_SCHEMA,
    )


def dedup_sorted(table: pa.Table) -> tuple[pa.Table, int]:
    """Explicit dedup step (spec rule): drop rows repeating an open timestamp, keep first."""
    col = table.column("timestamp_open_utc").to_pylist()
    keep = [i for i, v in enumerate(col) if i == 0 or v != col[i - 1]]
    dropped = table.num_rows - len(keep)
    return (table.take(pa.array(keep)) if dropped else table), dropped


def content_sha256(table: pa.Table) -> str:
    """Hash of the logical content (arrow IPC stream), independent of parquet encoding."""
    sink = io.BytesIO()
    with pa.ipc.new_stream(sink, table.schema) as w:
        w.write_table(table)
    return hashlib.sha256(sink.getvalue()).hexdigest()


def normalize_pair(instrument: str, interval: str) -> dict[str, object]:
    tables, detections = [], []
    for month in months():
        zp = RAW_ROOT / instrument / interval / f"{instrument}-{interval}-{month}.zip"
        raw, det = parse_zip(zp, month)
        detections.append(det)
        tables.append(to_canonical(raw, det.detected_unit, instrument, interval))
    merged = pa.concat_tables(tables).sort_by("timestamp_open_utc")
    merged, dropped = dedup_sorted(merged)

    NORM_ROOT.mkdir(parents=True, exist_ok=True)
    out = NORM_ROOT / f"{instrument}_{interval}.parquet"
    pyarrow.parquet.write_table(merged, out, compression="zstd")

    opens = merged.column("timestamp_open_utc")
    return {
        "parquet": out.name,
        "rows": merged.num_rows,
        "dropped_duplicate_open_timestamps": dropped,
        "coverage_start_utc": str(opens[0]),
        "coverage_end_utc": str(opens[-1]),
        "parquet_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "content_sha256": content_sha256(merged),
        "file_unit_detections": [asdict(d) for d in detections],
    }


def code_commit() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def main() -> None:
    result: dict[str, object] = {
        "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "normalization_code_commit": code_commit(),
        "tables": {},
    }
    for sym in INSTRUMENTS:
        for iv in INTERVALS:
            info = normalize_pair(sym, iv)
            result["tables"][f"{sym}_{iv}"] = info  # type: ignore[index]
            print(f"{sym} {iv}: rows={info['rows']} content={str(info['content_sha256'])[:12]}…")
    NORM_MANIFEST.write_text(json.dumps(result, indent=2) + "\n")
    print(f"manifest: {NORM_MANIFEST}")


if __name__ == "__main__":
    main()
