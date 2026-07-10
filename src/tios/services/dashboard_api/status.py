"""Read-only project status projection for the local progress dashboard."""

# The dashboard's compact HTML is intentionally embedded in the UI module; this API module
# remains subject to the normal project lint rules.

from __future__ import annotations

import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from tios.research_assets import ResearchSourceError, ResearchSourceRegistry
from tios.services.jobs.projection import build_jobs_projection

STATUS_RE = re.compile(r"Status:\s*\*?\*?([^\n]+)")
TASK_RE = re.compile(r"^## (T-\d{3}-\d{2}) (.+)$", re.MULTILINE)
TASK_STATUS_RE = re.compile(r"Status:\s*\*?\*?([^\n]+)")
CHECK_ARTIFACT_MAX_AGE = timedelta(hours=24)


def _automation(root: Path) -> dict[str, Any]:
    try:
        projection = build_jobs_projection(root)
        if not isinstance(projection, dict):
            raise ValueError("jobs projection must be an object")
        return projection
    except Exception as error:
        return {
            "schema_version": 1,
            "availability": "ERROR",
            "database": {
                "schema_version": None,
                "integrity": "UNAVAILABLE",
                "capacity": {"bytes": None, "max_bytes": None, "usage_ratio": None},
            },
            "counts": {
                "states": {
                    "QUEUED": 0,
                    "RUNNING": 0,
                    "SUCCEEDED": 0,
                    "FAILED": 0,
                    "CANCELLED": 0,
                },
                "types": {},
            },
            "latest_jobs": [],
            "schedules": [],
            "worker": {
                "mode": "LOCAL_OPERATOR_CLI_ONLY",
                "polling": "UNKNOWN",
                "http_endpoint": False,
            },
            "capabilities": {
                "allowed": ["READ_ONLY_STATUS"],
                "prohibited": ["HTTP_JOB_CONTROL", "ORDER_EXECUTION", "LIVE_EXECUTION"],
            },
            "error": str(error),
        }


def _status_label(value: str) -> str:
    cleaned = re.sub(r"[*`]", "", value).strip().rstrip(".")
    match = re.match(r"(DONE|IN PROGRESS|TODO|ONGOING|DEFERRED(?:-[A-Z0-9]+)?|BLOCKED)", cleaned)
    return match.group(1) if match else cleaned


def _initiative(path: Path) -> dict[str, Any]:
    text = path.read_text()
    title = text.splitlines()[0].removeprefix("# ").strip()
    tasks = []
    matches = list(TASK_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start() : end]
        status_match = TASK_STATUS_RE.search(block)
        status = _status_label(status_match.group(1)) if status_match else "UNKNOWN"
        tasks.append({"id": match.group(1), "title": match.group(2).strip(), "status": status})
    statuses = [task["status"] for task in tasks]
    if statuses and all(status.startswith("DONE") for status in statuses):
        overall = "DONE"
    elif any(status.startswith(("IN PROGRESS", "ONGOING")) for status in statuses):
        overall = "IN PROGRESS"
    elif any(status == "TODO" for status in statuses):
        overall = "TODO"
    else:
        overall = "REVIEW"
    return {
        "id": path.name[:2],
        "file": path.name,
        "title": title,
        "status": overall,
        "tasks": tasks,
    }


def _git(root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=root, capture_output=True, text=True, check=False
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {"changed_files": len(lines), "clean": not lines, "entries": lines[:20]}


def _check_status(root: Path, now: datetime) -> dict[str, Any]:
    path = root / "artifacts" / "quality" / "check.json"
    payload = _json(path)
    try:
        generated_at = datetime.fromisoformat(str(payload["generated_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        generated_at = None
    passed = (
        payload.get("schema_version") == 2
        and payload.get("gate") == "check"
        and payload.get("command") == "make check"
        and payload.get("status") == "PASS"
        and payload.get("includes_dependency_audit") is False
        and generated_at is not None
        and generated_at.tzinfo is not None
        and timedelta(0) <= now - generated_at <= CHECK_ARTIFACT_MAX_AGE
    )
    return {
        "command": "make check",
        "gate": "check",
        "status": "PASS" if passed else "UNKNOWN",
        "known_passing": passed,
        "includes_dependency_audit": False,
        "required_gate": {"command": "make required", "status": "UNKNOWN"},
        "artifact": str(path.relative_to(root)) if path.is_file() else None,
        "generated_at": payload.get("generated_at") if passed else None,
    }


def build_status(root: Path | None = None) -> dict[str, Any]:
    """Build a fresh status snapshot. No state is written."""
    root = root or Path(__file__).resolve().parents[4]
    initiatives = [_initiative(path) for path in sorted((root / "todos").glob("*.md"))]
    tasks = [task for item in initiatives for task in item["tasks"]]
    done = sum(task["status"].startswith("DONE") for task in tasks)
    in_progress = sum(task["status"].startswith("IN PROGRESS") for task in tasks)
    todo = sum(task["status"] == "TODO" for task in tasks)
    artifact_files = (
        [
            path
            for path in (root / "artifacts").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        ]
        if (root / "artifacts").exists()
        else []
    )
    state_text = (
        (root / "PROJECT_STATE.md").read_text() if (root / "PROJECT_STATE.md").exists() else ""
    )
    state_match = STATUS_RE.search(state_text)
    now = datetime.now(tz=UTC)
    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "project": "Trading Intelligence OS",
        "stage": _status_label(state_match.group(1)) if state_match else "UNKNOWN",
        "summary": {"total": len(tasks), "done": done, "in_progress": in_progress, "todo": todo},
        "initiatives": initiatives,
        "artifacts": {"files": len([path for path in artifact_files if path.is_file()])},
        "git": _git(root),
        "checks": _check_status(root, now),
    }


def _json(path: Path) -> dict[str, Any]:
    try:
        import json

        payload = json.loads(path.read_text())
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _research_lab(root: Path) -> dict[str, Any]:
    lab_root = root / "artifacts" / "research_lab" / "v0"
    base: dict[str, Any] = {
        "mode": "OFFLINE_RESEARCH_ONLY",
        "state": "NO_BATCH",
        "latest_batch_id": None,
        "started_at": None,
        "completed_at": None,
        "experiments": 0,
        "runs": 0,
        "completed": 0,
        "failed": 0,
        "all_trials_retained": False,
        "winner_selected": False,
        "validation_status": "UNVALIDATED",
        "approval_status": "NOT_APPROVED",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "demo_orders": "DISABLED",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "blockers": [],
        "score_dimensions": {},
        "artifact_refs": [],
        "latest_seed_cycle": _latest_seed_cycle(root),
        "next_work": (
            "Run uv run python scripts/run_research_lab_v0.py when the next evidence cycle "
            "is requested."
        ),
    }
    if not lab_root.exists():
        return base

    confined_root = lab_root.resolve()
    candidates = [
        path
        for path in lab_root.glob("LAB-*/lab_run.json")
        if path.is_file() and path.resolve().is_relative_to(confined_root)
    ]
    if not candidates:
        return base

    path = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
    payload = _json(path)
    counts_raw = payload.get("counts")
    counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}

    def count(name: str) -> int:
        value = counts.get(name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    runs = count("trials")
    completed = count("completed_trials")
    failed = count("failed_trials")
    status = payload.get("status")
    states = {
        "READY": "READY",
        "RUNNING": "RUNNING",
        "COMPLETED": "COMPLETE",
        "COMPLETE": "COMPLETE",
        "FAILED": "FAILED",
    }
    state = states.get(status, "FAILED") if isinstance(status, str) else "FAILED"
    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or any(not isinstance(item, str) for item in blockers):
        blockers = []
    if state == "FAILED" and not blockers:
        error = payload.get("error")
        blockers = [str(error)] if error else ["lab_run.json is malformed or incomplete"]
    score_dimensions = payload.get("score_states")
    if not isinstance(score_dimensions, dict):
        score_dimensions = {}
    artifact_refs = [
        str(candidate.relative_to(root))
        for name in (
            "lab_run.json",
            "manifest.json",
            "trial_ledger.jsonl",
            "trial_ledger_summary.json",
            "trading_evidence.jsonl",
        )
        if (candidate := path.parent / name).is_file()
        and candidate.resolve().is_relative_to(confined_root)
    ]
    return {
        **base,
        "mode": (
            payload.get("mode") if payload.get("mode") == "OFFLINE_RESEARCH_ONLY" else base["mode"]
        ),
        "state": state,
        "latest_batch_id": path.parent.name,
        "started_at": payload.get("started_at_utc"),
        "completed_at": payload.get("finished_at_utc"),
        "experiments": count("experiments"),
        "runs": runs,
        "completed": completed,
        "failed": failed,
        "all_trials_retained": runs > 0 and runs == completed + failed,
        "winner_selected": payload.get("winner_selected") is True,
        "blockers": blockers,
        "score_dimensions": score_dimensions,
        "artifact_refs": artifact_refs,
        "latest_seed_cycle": _latest_seed_cycle(root),
    }


def _latest_seed_cycle(root: Path) -> dict[str, Any] | None:
    cycle_root = root / "artifacts" / "research_lab" / "seed_cycle_v0"
    if not cycle_root.exists():
        return None
    confined_root = cycle_root.resolve()
    candidates = [
        path
        for path in cycle_root.glob("SEEDCYCLE-*/cycle_run.json")
        if path.is_file() and path.resolve().is_relative_to(confined_root)
    ]
    if not candidates:
        return None
    path = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
    payload = _json(path)
    counts_raw = payload.get("counts")
    counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
    return {
        "cycle_id": path.parent.name,
        "status": payload.get("status", "UNKNOWN"),
        "mode": payload.get("mode", "OFFLINE_RESEARCH_ONLY"),
        "trials": counts.get("trials", 0),
        "candidates": counts.get("candidates", 0),
        "winner_selected": payload.get("winner_selected") is True,
        "approval_status": "NOT_ELIGIBLE",
        "artifact_ref": str(path.relative_to(root)),
    }


def _research_sources(root: Path) -> dict[str, Any]:
    path = root / "research" / "PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
    base: dict[str, Any] = {
        "source_count": 0,
        "family_counts": {},
        "hypothesis_only_count": 0,
        "noneligible_count": 0,
        "checked_date": None,
        "digest": None,
        "rows": [],
    }
    try:
        registry = ResearchSourceRegistry.load(path)
    except (OSError, ResearchSourceError):
        return base
    records = registry.list()
    family_counts: dict[str, int] = {}
    for record in records:
        for family in record.hypothesis_families:
            family_counts[family.value] = family_counts.get(family.value, 0) + 1
    return {
        "source_count": len(records),
        "family_counts": dict(sorted(family_counts.items())),
        "hypothesis_only_count": sum(
            record.evidence_strength.value == "hypothesis_only" for record in records
        ),
        "noneligible_count": sum(not record.approval_eligible for record in records),
        "checked_date": max((record.checked_at[:10] for record in records), default=None),
        "digest": registry.digest(),
        "rows": [
            {
                "source_id": record.source_id,
                "title": record.title,
                "year": record.year,
                "doi": record.doi,
                "canonical_url": record.canonical_publisher_url,
                "families": [family.value for family in record.hypothesis_families],
                "reproduction": ("REPRODUCED" if record.locally_reproduced else "NOT_REPRODUCED"),
                "eligibility": "ELIGIBLE" if record.approval_eligible else "NOT_ELIGIBLE",
            }
            for record in records
        ],
    }


def build_dashboard_data(root: Path | None = None) -> dict[str, Any]:
    """Build the current evidence-operations surface from repository artifacts."""
    root = root or Path(__file__).resolve().parents[4]
    dataset_path = root / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    quality_path = root / "artifacts" / "datasets" / "QUALITY_REPORT.json"
    dataset = _json(dataset_path)
    quality = _json(quality_path)
    tables = dataset.get("tables", {})
    datasets = [
        {
            "id": dataset.get("dataset_id", "DS-CRYPTO-SPOT-BAKEOFF-V1"),
            "source": dataset.get("source", "Binance public Spot data"),
            "status": "FROZEN" if dataset else "NOT FOUND",
            "tables": len(tables),
            "rows": sum(int(table.get("rows", 0)) for table in tables.values()),
            "coverage": (
                f"{min((t.get('coverage_start_utc', '') for t in tables.values()), default='?')} → "
                f"{max((t.get('coverage_end_utc', '') for t in tables.values()), default='?')}"
            ),
            "quality": quality.get("overall", "NOT RUN"),
            "manifest": str(dataset_path.relative_to(root)),
        }
    ]

    strategies = []
    for path in sorted((root / "fixtures" / "strategies" / "baselines").glob("*.yaml")):
        text = path.read_text()
        strategy_id = path.stem.split("_")[0]
        family = re.search(r"family:\s*([^\n]+)", text)
        strategies.append(
            {
                "id": strategy_id,
                "name": path.stem,
                "family": family.group(1).strip() if family else "baseline",
                "status": "VALID",
                "spec": str(path.relative_to(root)),
            }
        )

    runs = []
    for path in sorted((root / "artifacts" / "bakeoff").glob("**/normalized_metrics.json")):
        metrics = _json(path)
        runs.append(
            {
                "id": path.parent.name,
                "engine": metrics.get(
                    "engine", path.parts[-4] if len(path.parts) > 3 else "unknown"
                ),
                "strategy": metrics.get("strategy", metrics.get("baseline", "unknown")),
                "fills": metrics.get("fills", 0),
                "roundtrips": metrics.get("trades_roundtrips", 0),
                "fee_audit": metrics.get("fee_audit", {}).get("status", "UNKNOWN"),
                "artifact": str(path.parent.relative_to(root)),
                "artifact_modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).isoformat(),
            }
        )

    engine_files = {
        "freqtrade": root / "artifacts" / "bakeoff" / "freqtrade" / "DRY_RUN_PROBE.md",
        "nautilus": root / "artifacts" / "bakeoff" / "nautilus" / "NAUTILUS_LANE_NOTES.md",
        "lean": root / "artifacts" / "bakeoff" / "lean" / "STATUS.md",
        "hummingbot": root / "artifacts" / "bakeoff" / "hummingbot" / "BLOCKER_REPORT.md",
        "vectorbt": root / "artifacts" / "bakeoff" / "vectorbt" / "PROBE_CONCLUSION.md",
    }
    engines = []
    for name, path in engine_files.items():
        text = path.read_text().lower() if path.exists() else ""
        if "incomplete" in text or "docker" in text and "running" in text and "current" in text:
            status = "BLOCKED / PARTIAL"
        elif "resolved" in text or "verdict" in text or "pass" in text:
            status = "EVIDENCE READY"
        else:
            status = "NOT STARTED"
        engines.append({"name": name, "status": status, "artifact": str(path.relative_to(root))})

    reports = []
    for path in sorted((root / "artifacts" / "reports").glob("*.md")):
        reports.append(
            {
                "name": path.stem.replace("_", " ").title(),
                "path": str(path.relative_to(root)),
                "kind": "report",
            }
        )
    validation_package_path = (
        root / "artifacts" / "validation" / "B2_F0_S0" / "validation_summary.json"
    )
    validation_package = _json(validation_package_path)
    readiness_path = root / "artifacts" / "reports" / "PROTOTYPE_READINESS_REPORT.md"
    readiness_text = readiness_path.read_text() if readiness_path.exists() else ""
    readiness_match = STATUS_RE.search(readiness_text)
    readiness_raw = _status_label(readiness_match.group(1)) if readiness_match else "NOT ASSESSED"
    readiness_status = "CONSTRAINED" if "CONSTRAINED" in readiness_raw else readiness_raw
    research_lab = _research_lab(root)
    activity = [
        {
            "kind": "RUN_ARTIFACT",
            "id": run["id"],
            "timestamp": run["artifact_modified_at"],
            "count": 1,
            "runs": 1,
            "fills": run["fills"],
            "artifact": run["artifact"],
        }
        for run in runs
    ]
    if research_lab["latest_batch_id"]:
        activity.append(
            {
                "kind": "RESEARCH_BATCH",
                "id": research_lab["latest_batch_id"],
                "timestamp": research_lab["completed_at"] or research_lab["started_at"],
                "count": 1,
                "runs": research_lab["runs"],
                "fills": None,
                "artifact": research_lab["artifact_refs"][0],
            }
        )
    activity.sort(key=lambda row: str(row["timestamp"] or ""), reverse=True)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "stage": "S2_OFFLINE_RESEARCH_OPERATIONS",
        "automation": _automation(root),
        "research_lab": research_lab,
        "research_sources": _research_sources(root),
        "datasets": datasets,
        "strategies": strategies,
        "runs": runs,
        "activity": activity,
        "engines": engines,
        "validation": {
            "status": validation_package.get("status", "IN PROGRESS"),
            "gates_required": [
                "G1",
                "G2",
                "G3",
                "G4",
                "G5",
                "G6",
                "G7",
                "G8",
                "G9",
                "G10",
                "G11",
            ],
            "report": "artifacts/reports/BACKTEST_VALIDATION_REPORT.md",
            "available": (
                root / "artifacts" / "reports" / "BACKTEST_VALIDATION_REPORT.md"
            ).exists(),
            "package": (
                str(validation_package_path.relative_to(root)) if validation_package else None
            ),
            "gates": validation_package.get("gates", {}) if validation_package else {},
            "risk_preconditions": (
                validation_package.get("risk_preconditions", {}) if validation_package else {}
            ),
        },
        "readiness": {
            "status": readiness_status,
            "scope": "S2 OFFLINE RESEARCH ONLY",
            "report": str(readiness_path.relative_to(root)),
        },
        "evidence": reports,
    }
