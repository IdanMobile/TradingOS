"""Normalize DS-CRYPTO-MULTI-V1 spot klines (many pairs, all timeframes).

Reuses the DS-CRYPTO-SPOT-BAKEOFF-V1 normalizer primitives (parse_zip, to_canonical,
dedup, content hash, Amendment A1 µs/ms detection) but iterates over the wider pair
and timeframe set produced by tios.dataset.acquire, and tolerates months that predate
a coin's listing (missing zip -> skipped, recorded). Ticks are NOT normalized here —
their raw zips ARE the tick data and are normalized on demand.

Run: uv run python -m tios.dataset.normalize_multi
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet

from tios.dataset.acquire import RAW_ROOT, TIMEFRAMES, TOP_PAIRS, months
from tios.dataset.normalize import content_sha256, dedup_sorted, parse_zip, to_canonical

NORM_ROOT = Path(__file__).resolve().parents[3] / "data" / "normalized_multi"
NORM_MANIFEST = NORM_ROOT / "normalized_multi_manifest.json"


def normalize_pair(instrument: str, interval: str) -> dict[str, object] | None:
    """Normalize every present monthly kline zip for one pair/interval, or None if absent."""
    tables, detections, missing = [], [], []
    for month in months():
        zp = RAW_ROOT / "klines" / instrument / interval / f"{instrument}-{interval}-{month}.zip"
        if not zp.exists():
            missing.append(month)
            continue
        raw, det = parse_zip(zp, month)
        detections.append(det)
        tables.append(to_canonical(raw, det.detected_unit, instrument, interval))
    if not tables:
        return None
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
        "missing_months": missing,
        "parquet_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "content_sha256": content_sha256(merged),
    }


def normalize_all(pairs: tuple[str, ...] = TOP_PAIRS) -> dict[str, object]:
    tables: dict[str, object] = {}
    for sym in pairs:
        for iv in TIMEFRAMES:
            info = normalize_pair(sym, iv)
            if info is not None:
                tables[f"{sym}_{iv}"] = info
                print(f"  {sym}_{iv}: rows={info['rows']} missing={len(info['missing_months'])}")  # type: ignore[arg-type]
    return {"dataset_id": "DS-CRYPTO-MULTI-V1", "tables": tables, "pair_count": len(pairs)}


def main() -> None:
    result = normalize_all()
    NORM_ROOT.mkdir(parents=True, exist_ok=True)
    NORM_MANIFEST.write_text(json.dumps(result, indent=2) + "\n")
    print(f"tables: {len(result['tables'])}  manifest: {NORM_MANIFEST}")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
