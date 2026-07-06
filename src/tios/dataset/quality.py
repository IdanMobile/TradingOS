"""Dataset quality gate (T-004-03, REQ-008) per specs/CANONICAL_BAKEOFF_DATASET_V1.md.

Every required check is a pure function over an arrow table so corrupted-fixture
tests can prove each one can fail. CLI runs all checks over the normalized
tables + raw manifest and writes artifacts/datasets/QUALITY_REPORT.{json,md}.

Run: uv run python -m tios.dataset.quality
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet

from tios.dataset.download import INSTRUMENTS, INTERVALS, MANIFEST_PATH, RAW_ROOT
from tios.dataset.normalize import NORM_MANIFEST, NORM_ROOT

REPORT_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "datasets"
INTERVAL_US = {"5m": 300_000_000, "15m": 900_000_000, "1h": 3_600_000_000}

Check = dict[str, Any]  # {"name", "status": "PASS"|"FAIL", "details": {...}}


def _opens_us(table: pa.Table) -> list[int]:
    out: list[int] = table.column("timestamp_open_utc").cast(pa.int64()).to_pylist()
    return out


def check_monotonic_unique(table: pa.Table) -> Check:
    opens = _opens_us(table)
    violations = sum(1 for a, b in zip(opens[:-1], opens[1:], strict=True) if b <= a)
    return {
        "name": "monotonic_unique_open_timestamps",
        "status": "PASS" if violations == 0 else "FAIL",
        "details": {"non_increasing_pairs": violations, "rows": len(opens)},
    }


def check_spacing(table: pa.Table, interval: str) -> Check:
    """Every step must be an exact positive multiple of the interval; gaps are
    legitimate (exchange downtime) and land in the missing-interval report."""
    step = INTERVAL_US[interval]
    opens = _opens_us(table)
    bad = sum(1 for a, b in zip(opens[:-1], opens[1:], strict=True) if (b - a) % step or b <= a)
    return {
        "name": "interval_spacing",
        "status": "PASS" if bad == 0 else "FAIL",
        "details": {"non_multiple_steps": bad, "interval_us": step},
    }


def missing_intervals(table: pa.Table, interval: str) -> Check:
    step = INTERVAL_US[interval]
    opens = _opens_us(table)
    gaps = [
        {
            "gap_start_utc": str(table.column("timestamp_open_utc")[i].as_py()),
            "missing_bars": (b - a) // step - 1,
        }
        for i, (a, b) in enumerate(zip(opens[:-1], opens[1:], strict=True))
        if b - a > step
    ]
    return {
        "name": "missing_interval_report",
        "status": "PASS",  # informational: gaps must be reported, not hidden
        "details": {
            "gap_count": len(gaps),
            "missing_bars_total": sum(g["missing_bars"] for g in gaps),
            "gaps": gaps,
        },
    }


def check_ohlc(table: pa.Table) -> Check:
    n = (
        duckdb.arrow(table)
        .filter("low > open OR low > close OR high < open OR high < close OR low > high")
        .count("*")
        .fetchone()
    )
    bad = int(n[0]) if n else 0
    return {
        "name": "ohlc_invariants",
        "status": "PASS" if bad == 0 else "FAIL",
        "details": {"violating_rows": bad},
    }


def check_volumes(table: pa.Table) -> Check:
    n = (
        duckdb.arrow(table)
        .filter(
            "volume_base < 0 OR quote_volume < 0 OR taker_buy_base_volume < 0 "
            "OR taker_buy_quote_volume < 0 OR trade_count < 0"
        )
        .count("*")
        .fetchone()
    )
    bad = int(n[0]) if n else 0
    return {
        "name": "non_negative_volumes",
        "status": "PASS" if bad == 0 else "FAIL",
        "details": {"violating_rows": bad},
    }


def check_timezone(table: pa.Table) -> Check:
    tzs = {
        str(table.schema.field(f).type.tz) for f in ("timestamp_open_utc", "close_timestamp_utc")
    }
    return {
        "name": "timezone_utc",
        "status": "PASS" if tzs == {"UTC"} else "FAIL",
        "details": {"tz": sorted(tzs)},
    }


def month_row_counts(table: pa.Table) -> dict[str, int]:
    rows = (
        duckdb.arrow(table)
        .aggregate("strftime(timestamp_open_utc, '%Y-%m') AS month, count(*) AS n", "month")
        .order("month")
        .fetchall()
    )
    return {m: int(n) for m, n in rows}


def verify_raw_checksums() -> Check:
    manifest = json.loads(MANIFEST_PATH.read_text())
    mismatched, missing = [], []
    for f in manifest["files"]:
        p = RAW_ROOT / f["file"]
        if not p.is_file():
            missing.append(f["file"])
        elif hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            mismatched.append(f["file"])
    ok = not mismatched and not missing
    return {
        "name": "raw_source_checksums",
        "status": "PASS" if ok else "FAIL",
        "details": {
            "files": len(manifest["files"]),
            "official_checksum_verified": sum(
                1 for f in manifest["files"] if f["checksum_verified"]
            ),
            "mismatched": mismatched,
            "missing": missing,
        },
    }


def main() -> None:
    norm = json.loads(NORM_MANIFEST.read_text())
    report: dict[str, Any] = {
        "dataset_id": norm["dataset_id"],
        "normalization_code_commit": norm["normalization_code_commit"],
        "tables": {},
        "raw": verify_raw_checksums(),
    }
    schemas = set()
    for sym in INSTRUMENTS:
        for iv in INTERVALS:
            key = f"{sym}_{iv}"
            table = pyarrow.parquet.read_table(NORM_ROOT / f"{key}.parquet")
            schemas.add(str(table.schema))
            checks = [
                check_monotonic_unique(table),
                check_spacing(table, iv),
                missing_intervals(table, iv),
                check_ohlc(table),
                check_volumes(table),
                check_timezone(table),
            ]
            report["tables"][key] = {
                "checks": checks,
                "row_counts_by_month": month_row_counts(table),
                "dropped_duplicate_open_timestamps": norm["tables"][key][
                    "dropped_duplicate_open_timestamps"
                ],
                # Amendment A1: per-source-file unit detection, verbatim from normalization
                "file_unit_detections": norm["tables"][key]["file_unit_detections"],
            }
    report["schema_identical_across_tables"] = {
        "name": "schema_identical",
        "status": "PASS" if len(schemas) == 1 else "FAIL",
        "details": {"distinct_schemas": len(schemas)},
    }

    all_checks = [report["raw"], report["schema_identical_across_tables"]] + [
        c for t in report["tables"].values() for c in t["checks"]
    ]
    report["overall"] = "PASS" if all(c["status"] == "PASS" for c in all_checks) else "FAIL"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "QUALITY_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    md = [
        f"# Dataset Quality Report — {report['dataset_id']}",
        "",
        f"Overall: **{report['overall']}** · normalization commit "
        f"`{report['normalization_code_commit'][:12]}`",
        "",
        f"- raw_source_checksums: {report['raw']['status']} "
        f"({report['raw']['details']['files']} files, "
        f"{report['raw']['details']['official_checksum_verified']} official-checksum-verified)",
        f"- schema_identical_across_tables: {report['schema_identical_across_tables']['status']}",
        "",
        "| table | rows | checks | gaps | missing bars | unit files ms/µs |",
        "|---|---|---|---|---|---|",
    ]
    for key, t in report["tables"].items():
        rows = sum(t["row_counts_by_month"].values())
        statuses = {c["name"]: c["status"] for c in t["checks"]}
        gaps = next(c for c in t["checks"] if c["name"] == "missing_interval_report")
        ms = sum(1 for d in t["file_unit_detections"] if d["detected_unit"] == "ms")
        us = sum(1 for d in t["file_unit_detections"] if d["detected_unit"] == "us")
        ok = "PASS" if all(s == "PASS" for s in statuses.values()) else "FAIL"
        md.append(
            f"| {key} | {rows} | {ok} | {gaps['details']['gap_count']} | "
            f"{gaps['details']['missing_bars_total']} | {ms}/{us} |"
        )
    (REPORT_DIR / "QUALITY_REPORT.md").write_text("\n".join(md) + "\n")
    print(f"overall: {report['overall']}")
    print(f"reports: {REPORT_DIR}/QUALITY_REPORT.{{json,md}}")


if __name__ == "__main__":
    main()
