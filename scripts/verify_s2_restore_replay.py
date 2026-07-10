#!/usr/bin/env python3
"""Verify the S2 local backup/restore/replay evidence set."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "quality" / "s2_restore_replay.json"
REPORT = ROOT / "artifacts" / "reports" / "S2_RESTORE_REPLAY_REPORT.md"
LINEAGE_RESULT = ROOT / "artifacts" / "lineage" / "prototype" / "prototype_result.json"
JOBS_DB = ROOT / "artifacts" / "jobs" / "jobs.sqlite3"
LAB = (
    ROOT
    / "artifacts"
    / "research_lab"
    / "v0"
    / "LAB-799f7d81843d15aaf3b161036a4cd543ac37a709cb1e2ecc72a161f7348488fa"
)
VALIDATION = ROOT / "artifacts" / "validation" / "B2_F0_S0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def verify_sqlite_restore(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        schema_version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
        jobs = dict(
            connection.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall()
        )
        schedules = connection.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
    return {
        "source": display_path(source),
        "restored": display_path(target),
        "source_sha256": sha256(source),
        "restored_sha256": sha256(target),
        "hash_match": sha256(source) == sha256(target),
        "integrity": integrity,
        "schema_version": schema_version,
        "jobs_by_state": jobs,
        "schedule_count": schedules,
        "status": "PASS" if integrity == "ok" and jobs.get("SUCCEEDED") == 3 else "FAIL",
    }


def verify_copy_restore(paths: list[Path], restore_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in paths:
        target = restore_root / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        records.append(
            {
                "source": str(source.relative_to(ROOT)),
                "restored": display_path(target),
                "source_sha256": sha256(source),
                "restored_sha256": sha256(target),
                "hash_match": sha256(source) == sha256(target),
            }
        )
    return records


def build_result() -> dict[str, Any]:
    lineage = read_json(LINEAGE_RESULT)
    lab_run = read_json(LAB / "lab_run.json")
    validation = read_json(VALIDATION / "validation_summary.json")
    restore_paths = [
        LAB / "lab_run.json",
        LAB / "manifest.json",
        LAB / "scorecards.json",
        LAB / "trial_ledger_summary.json",
        VALIDATION / "validation_summary.json",
        VALIDATION / "multiple_testing_method_candidate.json",
        VALIDATION / "baseline_comparison.json",
    ]
    with tempfile.TemporaryDirectory(prefix="tios-s2-restore-") as tmp:
        restore_root = Path(tmp) / "restore"
        copied = verify_copy_restore(restore_paths, restore_root)
        sqlite = verify_sqlite_restore(JOBS_DB, restore_root / JOBS_DB.relative_to(ROOT))
    checks = {
        "dvc_fresh_checkout_replay": lineage["gates"]["reproduce"] == "PASS",
        "mlflow_artifact_restore": lineage["gates"]["compare"] == "PASS",
        "sqlite_backup_restore": sqlite["status"] == "PASS",
        "artifact_hash_restore": all(record["hash_match"] for record in copied),
        "lab_no_winner": lab_run["winner_selected"] is False,
        "validation_not_approvable": validation["status"] == "INCOMPLETE_NOT_APPROVABLE",
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "tios-s2-restore-replay-v1",
        "status": status,
        "checks": checks,
        "lineage_result": str(LINEAGE_RESULT.relative_to(ROOT)),
        "sqlite": sqlite,
        "artifacts": copied,
        "notes": [
            "Restore area is temporary; retained source artifacts remain authoritative.",
            "This verifies S2 local restore/replay only and does not approve a strategy.",
        ],
    }


def write_report(result: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# S2 Restore / Replay Verification",
        "",
        f"Status: **{result['status']}**",
        "",
        "## Checks",
        "",
    ]
    for name, passed in result["checks"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Machine report: `{OUT.relative_to(ROOT)}`",
            f"- Lineage prototype: `{result['lineage_result']}`",
            f"- Jobs DB restore: `{result['sqlite']['source']}`",
            "",
            "No strategy, paper/demo/testnet connection, credential, order route, live "
            "trading, or real-money path is authorized by this verification.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    result = build_result()
    write_report(result)
    print(json.dumps({"status": result["status"], "report": str(OUT)}, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
