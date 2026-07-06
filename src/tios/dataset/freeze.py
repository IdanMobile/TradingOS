"""Freeze DS-CRYPTO-SPOT-BAKEOFF-V1 with double-regeneration proof (T-004-04, REQ-009, EG-1).

Regenerates the normalized dataset from raw twice, requires identical content
hashes both times (and vs the current manifest), then writes the frozen dataset
manifest binding: raw hashes, normalization code commit, normalized hashes,
coverage, quality report hash.

Run: uv run python -m tios.dataset.freeze
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.dataset import normalize
from tios.dataset.download import INSTRUMENTS, INTERVALS, MANIFEST_PATH
from tios.dataset.quality import REPORT_DIR

DS_MANIFEST = REPORT_DIR / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"


def content_hashes_from_manifest() -> dict[str, str]:
    m = json.loads(normalize.NORM_MANIFEST.read_text())
    return {k: str(v["content_sha256"]) for k, v in m["tables"].items()}


def regenerate_once() -> dict[str, str]:
    normalize.main()
    return content_hashes_from_manifest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    baseline = content_hashes_from_manifest()
    print("regeneration 1/2 …")
    run1 = regenerate_once()
    print("regeneration 2/2 …")
    run2 = regenerate_once()

    if not (baseline == run1 == run2):
        diffs = [k for k in baseline if not (baseline[k] == run1[k] == run2[k])]
        raise SystemExit(f"NONDETERMINISM in tables {diffs} — EG-1 blocked, diagnose before freeze")

    norm = json.loads(normalize.NORM_MANIFEST.read_text())
    quality = json.loads((REPORT_DIR / "QUALITY_REPORT.json").read_text())
    if quality["overall"] != "PASS":
        raise SystemExit("quality report is not PASS — freeze refused")

    tables: dict[str, Any] = {}
    for sym in INSTRUMENTS:
        for iv in INTERVALS:
            key = f"{sym}_{iv}"
            t = norm["tables"][key]
            tables[key] = {
                "parquet": t["parquet"],
                "rows": t["rows"],
                "coverage_start_utc": t["coverage_start_utc"],
                "coverage_end_utc": t["coverage_end_utc"],
                "content_sha256": t["content_sha256"],
                "parquet_sha256": t["parquet_sha256"],
            }

    manifest = {
        "dataset_id": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "manifest_version": 1,
        "source": "Binance public Spot data",
        "frozen_utc": datetime.now(tz=UTC).isoformat(),
        "normalization_code_commit": norm["normalization_code_commit"],
        "raw_manifest": {"path": str(MANIFEST_PATH), "sha256": sha256_file(MANIFEST_PATH)},
        "quality_report_sha256": sha256_file(REPORT_DIR / "QUALITY_REPORT.json"),
        "tables": tables,
        "regeneration_proof": {
            "runs": 2,
            "identical_content_hashes": True,
            "content_sha256_by_table": run2,
        },
    }
    DS_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    # register artifacts in the WS1 evidence tree manifest
    reg_path = REPORT_DIR / "manifest.json"
    reg = json.loads(reg_path.read_text())
    reg["artifacts"] = [
        {"file": p.name, "sha256": sha256_file(p)}
        for p in (DS_MANIFEST, REPORT_DIR / "QUALITY_REPORT.json", REPORT_DIR / "QUALITY_REPORT.md")
    ]
    reg_path.write_text(json.dumps(reg, indent=2) + "\n")

    print(f"FROZEN: {DS_MANIFEST.name}")
    print(f"  code commit: {manifest['normalization_code_commit']}")
    print("  double-regeneration: identical content hashes across 2 fresh runs")


if __name__ == "__main__":
    main()
