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
import subprocess
from dataclasses import asdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet

from tios.dataset.acquire import RAW_ROOT, TIMEFRAMES, TOP_PAIRS, months
from tios.dataset.normalize import content_sha256, dedup_sorted, parse_zip, to_canonical

NORM_ROOT = Path(__file__).resolve().parents[3] / "data" / "normalized_multi"
NORM_MANIFEST = NORM_ROOT / "normalized_multi_manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_inputs(instrument: str, interval: str) -> tuple[list[dict[str, object]], list[str]]:
    files, missing = [], []
    for month in months():
        path = RAW_ROOT / "klines" / instrument / interval / f"{instrument}-{interval}-{month}.zip"
        if not path.exists():
            missing.append(month)
            continue
        files.append(
            {
                "path": path.relative_to(RAW_ROOT).as_posix(),
                "url": (
                    "https://data.binance.vision/data/spot/monthly/klines/"
                    f"{instrument}/{interval}/{path.name}"
                ),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return files, missing


def _input_set_sha256(files: list[dict[str, object]]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _code_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    changed = subprocess.run(
        ["git", "diff", "--quiet", "--", "src/tios/dataset/normalize_multi.py"], cwd=root
    )
    return {
        "module": "src/tios/dataset/normalize_multi.py",
        "module_sha256": _sha256(Path(__file__)),
        "git_commit": result.stdout.strip() if result.returncode == 0 else "unknown",
        "git_state": "committed" if changed.returncode == 0 else "modified_from_commit",
    }


def normalize_pair(instrument: str, interval: str) -> dict[str, object] | None:
    """Normalize every present monthly kline zip for one pair/interval, or None if absent."""
    tables, detections = [], []
    source_files, missing = _raw_inputs(instrument, interval)
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
        "file_unit_detections": [asdict(detection) for detection in detections],
        "source_files": source_files,
        "source_input_set_sha256": _input_set_sha256(source_files),
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
    return {
        "schema_version": 2,
        "dataset_id": "DS-CRYPTO-MULTI-V1",
        "lineage_status": "recorded_at_normalization",
        "normalization_code": _code_identity(),
        "tables": tables,
        "pair_count": len(pairs),
    }


def snapshot_existing() -> dict[str, object]:
    """Describe retained outputs without pretending this reconstructs their original run."""
    tables: dict[str, object] = {}
    status_path = NORM_ROOT / "daily_update_status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    updates = {item["file"]: item for item in status.get("updated", [])}
    status_ref = (
        {
            "path": status_path.name,
            "sha256": _sha256(status_path),
            "last_run_utc": status.get("last_run_utc"),
        }
        if status
        else None
    )
    unretained_rest_payloads = False
    for path in sorted(NORM_ROOT.glob("*.parquet")):
        instrument, interval = path.stem.rsplit("_", 1)
        table = pyarrow.parquet.read_table(path)
        source_files, missing = _raw_inputs(instrument, interval)
        opens = table.column("timestamp_open_utc")
        info = {
            "parquet": path.name,
            "rows": table.num_rows,
            "coverage_start_utc": str(opens[0]) if table.num_rows else None,
            "coverage_end_utc": str(opens[-1]) if table.num_rows else None,
            "missing_months": missing,
            "source_files": source_files,
            "source_input_set_sha256": _input_set_sha256(source_files),
            "parquet_sha256": _sha256(path),
            # Daily-refresh recovery metadata is operational, not logical candle content.
            "content_sha256": content_sha256(table.replace_schema_metadata(None)),
        }
        if update := updates.get(path.name):
            pages = update.get("source_pages", [])
            unretained_rest_payloads |= not bool(pages)
            info["rest_update_source"] = {
                "endpoint": "https://api.binance.com/api/v3/klines",
                "status_manifest": status_ref,
                "reported_added_rows": update.get("added_rows"),
                "source_pages": pages,
                "payloads_retained": bool(pages),
            }
        tables[path.stem] = info
    limitation = (
        "Hashes identify current raw and normalized bytes but do not prove the raw inputs "
        "or code identity used by the original normalization run."
    )
    if unretained_rest_payloads:
        limitation += " Historical REST append response payloads were not retained."
    return {
        "schema_version": 2,
        "dataset_id": "DS-CRYPTO-MULTI-V1",
        "source_snapshot_utc": status.get("last_run_utc", "unknown"),
        "lineage_status": "reconstructed_from_retained_files",
        "lineage_limitation": limitation,
        "normalization_code": _code_identity(),
        "tables": tables,
        "pair_count": len({name.rsplit("_", 1)[0] for name in tables}),
    }


def write_manifest(result: dict[str, object]) -> Path:
    """Write a current index and retain an immutable, content-addressed copy."""
    encoded = (json.dumps(result, indent=2) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    archive = NORM_ROOT / "manifests" / f"normalized_multi_manifest_{digest}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.write_bytes(encoded)
    NORM_MANIFEST.write_bytes(encoded)
    return archive


def verify_manifest(path: Path | None = None) -> list[str]:
    """Return every missing or byte-drifted normalized and retained source file."""
    path = path or NORM_MANIFEST
    manifest = json.loads(path.read_text())
    errors = []
    root = Path(__file__).resolve().parents[3]
    code = manifest.get("normalization_code", {})
    if code.get("module") and code.get("module_sha256"):
        code_path = root / code["module"]
        if not code_path.exists():
            errors.append(f"missing: {code_path}")
        elif _sha256(code_path) != code["module_sha256"]:
            errors.append(f"sha256 mismatch: {code_path}")
    for info in manifest["tables"].values():
        expected = [(NORM_ROOT / info["parquet"], info["parquet_sha256"])]
        expected += [(RAW_ROOT / ref["path"], ref["sha256"]) for ref in info["source_files"]]
        rest = info.get("rest_update_source", {})
        if status := rest.get("status_manifest"):
            expected.append((NORM_ROOT / status["path"], status["sha256"]))
        expected += [
            (RAW_ROOT / ref["path"], ref["sha256"]) for ref in rest.get("source_pages", [])
        ]
        for file_path, digest in expected:
            if not file_path.exists():
                errors.append(f"missing: {file_path}")
            elif _sha256(file_path) != digest:
                errors.append(f"sha256 mismatch: {file_path}")
    return errors


def main() -> None:
    result = normalize_all()
    NORM_ROOT.mkdir(parents=True, exist_ok=True)
    archive = write_manifest(result)
    print(f"tables: {len(result['tables'])}  manifest: {NORM_MANIFEST}  archive: {archive}")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
