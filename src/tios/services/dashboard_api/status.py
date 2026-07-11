"""Read-only project status projection for the local progress dashboard."""

# The dashboard's compact HTML is intentionally embedded in the UI module; this API module
# remains subject to the normal project lint rules.

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from tios.knowledge import ConceptError, ConceptRegistry
from tios.research_assets import (
    ReplayHypothesis,
    ReplayHypothesisRegistry,
    ResearchSourceError,
    ResearchSourceRegistry,
    SourceIntakePlan,
    SourceIntakePlanError,
    SourceIntakePlanRegistry,
)
from tios.services.jobs.projection import build_jobs_projection

STATUS_RE = re.compile(r"Status:\s*\*?\*?([^\n]+)")
TASK_RE = re.compile(r"^## (T-\d{3}-\d{2}) (.+)$", re.MULTILINE)
TASK_STATUS_RE = re.compile(r"Status:\s*\*?\*?([^\n]+)")
CHECK_ARTIFACT_MAX_AGE = timedelta(hours=24)
WORKSPACE_DECISIONS_PATH = Path("artifacts/human_decisions/workspace_decisions.jsonl")
DEFAULT_GATED_ACTIONS = [
    {
        "id": "keep_deferred",
        "label": "Keep deferred",
        "effect": "Leave this item gated; future agents must not work it.",
    }
]
WORKSPACE_ACTION_OPTIONS = {
    "T-001-03": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "authorize_source_recheck",
            "label": "Authorize source recheck",
            "effect": "Future agents may do official-source venue availability research only.",
        },
    ],
    "T-011-05": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "credentials_configured",
            "label": "Credentials configured",
            "effect": "Future agents may verify env presence and run controlled benchmark only.",
        },
    ],
    "T-017-05": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "credentials_configured",
            "label": "Credentials configured",
            "effect": "Future agents may wire cost telemetry for authorized provider runs only.",
        },
    ],
    "T-020-01": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "authorize_design_only",
            "label": "Authorize design only",
            "effect": "Future agents may draft S3 design research; no implementation.",
        },
    ],
    "T-020-02": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "authorize_design_only",
            "label": "Authorize design only",
            "effect": "Future agents may refresh S3 landscape research; no implementation.",
        },
    ],
    "T-020-03": [
        *DEFAULT_GATED_ACTIONS,
        {
            "id": "authorize_design_only",
            "label": "Authorize design only",
            "effect": "Future agents may audit expansion contracts; no implementation.",
        },
    ],
}
DEFAULT_RECURRING_ACTIONS = [
    {
        "id": "acknowledge_recurring",
        "label": "Acknowledge recurring",
        "effect": "Keep this visible as ongoing governance discipline.",
    }
]


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


def _task_bucket(status: str) -> str:
    if status.startswith(("DONE", "NOT APPLICABLE", "REJECTED")):
        return "closed"
    if status.startswith("ONGOING") or "recurring" in status.lower():
        return "recurring"
    if status.startswith("DEFERRED") or any(
        token in status for token in ("CREDENTIAL", "HUMAN", "HG-", "S3", "S4")
    ):
        return "gated"
    return "open"


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


def _workspace_decision_records(root: Path) -> list[dict[str, Any]]:
    path = root / WORKSPACE_DECISIONS_PATH
    if not path.is_file():
        return []
    records = []
    for line in path.read_text().splitlines():
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _latest_workspace_decisions(root: Path) -> dict[str, dict[str, Any]]:
    latest = {}
    for record in _workspace_decision_records(root):
        task_id = record.get("task_id")
        if isinstance(task_id, str):
            latest[task_id] = record
    return latest


def _workspace_actions(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = _latest_workspace_decisions(root)
    actions = []
    for row in rows:
        task_id = str(row["id"])
        if row["bucket"] == "gated":
            options = WORKSPACE_ACTION_OPTIONS.get(task_id, DEFAULT_GATED_ACTIONS)
        elif row["bucket"] == "recurring":
            options = DEFAULT_RECURRING_ACTIONS
        else:
            continue
        actions.append({**row, "options": options, "latest_decision": latest.get(task_id)})
    return actions


def build_status(root: Path | None = None) -> dict[str, Any]:
    """Build a fresh status snapshot. No state is written."""
    root = root or Path(__file__).resolve().parents[4]
    initiatives = [_initiative(path) for path in sorted((root / "todos").glob("*.md"))]
    tasks = [task for item in initiatives for task in item["tasks"]]
    done = sum(task["status"].startswith("DONE") for task in tasks)
    in_progress = sum(task["status"].startswith("IN PROGRESS") for task in tasks)
    todo = sum(task["status"] == "TODO" for task in tasks)
    task_rows = [
        {
            "id": task["id"],
            "title": task["title"],
            "status": task["status"],
            "initiative": item["title"],
            "file": item["file"],
            "bucket": _task_bucket(task["status"]),
        }
        for item in initiatives
        for task in item["tasks"]
    ]
    open_tasks = [task for task in task_rows if task["bucket"] == "open"]
    gated_tasks = [task for task in task_rows if task["bucket"] == "gated"]
    recurring_tasks = [task for task in task_rows if task["bucket"] == "recurring"]
    workspace_actions = _workspace_actions(root, [*gated_tasks, *recurring_tasks])
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
        "summary": {
            "total": len(tasks),
            "done": done,
            "in_progress": in_progress,
            "todo": todo,
            "open": len(open_tasks),
            "gated": len(gated_tasks),
            "recurring": len(recurring_tasks),
        },
        "open_tasks": open_tasks,
        "gated_tasks": gated_tasks,
        "recurring_tasks": recurring_tasks,
        "workspace_actions": workspace_actions,
        "workspace_decisions": {
            "artifact": str(WORKSPACE_DECISIONS_PATH),
            "count": len(_workspace_decision_records(root)),
        },
        "initiatives": initiatives,
        "artifacts": {"files": len([path for path in artifact_files if path.is_file()])},
        "git": _git(root),
        "checks": _check_status(root, now),
    }


def record_workspace_decision(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    status = build_status(root)
    task_id = str(payload.get("task_id", "")).strip()
    choice = str(payload.get("choice", "")).strip()
    note = str(payload.get("note", "")).strip()
    if len(note) > 500:
        raise ValueError("note is too long")
    action = next(
        (row for row in status["workspace_actions"] if row["id"] == task_id),
        None,
    )
    if action is None:
        raise ValueError("unknown workspace action task")
    option = next((item for item in action["options"] if item["id"] == choice), None)
    if option is None:
        raise ValueError("unknown workspace action choice")
    record = {
        "schema_version": 1,
        "decided_at": datetime.now(tz=UTC).isoformat(),
        "source": "local_dashboard_operator",
        "task_id": task_id,
        "task_title": action["title"],
        "task_status": action["status"],
        "choice": choice,
        "choice_label": option["label"],
        "effect": option["effect"],
        "note": note,
    }
    path = root / WORKSPACE_DECISIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {"schema_version": 1, "recorded": record, "status": build_status(root)}


def _json(path: Path) -> dict[str, Any]:
    try:
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
    intake_path = root / "research" / "EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml"
    replay_path = root / "research" / "EXTERNAL_REPLAY_HYPOTHESES_V1.yaml"
    base: dict[str, Any] = {
        "source_count": 0,
        "family_counts": {},
        "hypothesis_only_count": 0,
        "noneligible_count": 0,
        "checked_date": None,
        "digest": None,
        "intake_plans": {"plan_count": 0, "ready_count": 0, "design_only_count": 0},
        "replay_hypotheses": {
            "hypothesis_count": 0,
            "spec_candidate_count": 0,
            "replay_candidate_count": 0,
            "non_reconstructable_count": 0,
            "noneligible_count": 0,
        },
        "rows": [],
    }
    try:
        registry = ResearchSourceRegistry.load(path)
    except (OSError, ResearchSourceError):
        return base
    records = registry.list()
    intake_plans: tuple[SourceIntakePlan, ...]
    try:
        intake_registry = SourceIntakePlanRegistry.load(intake_path, source_registry=registry)
        intake_plans = intake_registry.list()
    except (OSError, SourceIntakePlanError):
        intake_plans = ()
        intake_registry = None
    replay_hypotheses: tuple[ReplayHypothesis, ...] = ()
    if intake_registry is not None:
        try:
            replay_registry = ReplayHypothesisRegistry.load(
                replay_path,
                source_registry=registry,
                intake_registry=intake_registry,
            )
            replay_hypotheses = replay_registry.list()
        except (OSError, SourceIntakePlanError):
            replay_hypotheses = ()
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
        "intake_plans": {
            "plan_count": len(intake_plans),
            "ready_count": sum(
                plan.status.value == "ready_for_offline_capture" for plan in intake_plans
            ),
            "design_only_count": sum(plan.status.value == "design_only" for plan in intake_plans),
        },
        "replay_hypotheses": {
            "hypothesis_count": len(replay_hypotheses),
            "spec_candidate_count": sum(
                item.status.value == "spec_candidate" for item in replay_hypotheses
            ),
            "replay_candidate_count": sum(
                item.status.value == "replay_candidate" for item in replay_hypotheses
            ),
            "non_reconstructable_count": sum(
                item.status.value == "non_reconstructable" for item in replay_hypotheses
            ),
            "noneligible_count": sum(not item.approval_eligible for item in replay_hypotheses),
        },
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


def _dictionary_concepts(root: Path) -> dict[str, Any]:
    path = root / "research" / "DICTIONARY_CONCEPTS_V1.json"
    base: dict[str, Any] = {
        "concept_count": 0,
        "fibo_provenance_count": 0,
        "categories": {},
        "gaps": [],
        "rows": [],
    }
    try:
        registry = ConceptRegistry.load(path)
    except (OSError, ConceptError):
        return base
    records = registry.list()
    categories: dict[str, int] = {}
    for record in records:
        categories[record.category] = categories.get(record.category, 0) + 1
    return {
        "concept_count": len(records),
        "fibo_provenance_count": sum(
            record.evidence_status.value == "FIBO_PROVENANCE" for record in records
        ),
        "categories": dict(sorted(categories.items())),
        "gaps": list(registry.gaps()),
        "rows": [
            {
                "concept_id": record.concept_id,
                "name": record.canonical_name,
                "aliases": [*record.abbreviations, *record.aliases],
                "category": record.category,
                "contexts": [*record.market_contexts, *record.venue_variants],
                "evidence_status": record.evidence_status.value,
                "freshness": record.freshness.value,
                "sources": list(record.sources),
            }
            for record in records
        ],
    }


def _trading_domain(
    runs: list[dict[str, Any]], validation_package: dict[str, Any]
) -> dict[str, Any]:
    retained_fills = sum(
        int(run.get("fills", 0))
        for run in runs
        if isinstance(run.get("fills", 0), int) and not isinstance(run.get("fills", 0), bool)
    )
    risk_preconditions = validation_package.get("risk_preconditions", {})
    if not isinstance(risk_preconditions, dict):
        risk_preconditions = {}
    return {
        "schema_version": 1,
        "environment": "HISTORICAL_RESEARCH",
        "mode": "INERT_READ_MODEL",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "capabilities": {
            "credential_access": "ABSENT",
            "order_endpoint": "ABSENT",
            "account_mutation": "DISABLED",
            "synthetic_wallet": "ABSENT",
            "demo_orders": "DISABLED",
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "risk_engine": "VALIDATION_PRECONDITIONS_ONLY",
        },
        "counts": {
            "retained_run_artifacts": len(runs),
            "retained_backtest_fills": retained_fills,
            "order_intents": 0,
            "order_states": 0,
            "accounts": 0,
            "portfolios": 0,
            "positions": 0,
            "risk_decisions": 0,
        },
        "read_models": [
            {
                "name": "Order intents and states",
                "status": "DISABLED",
                "detail": "No order submit, cancel, replace, or route command exists in S2.",
            },
            {
                "name": "Account and demo wallet",
                "status": "ABSENT",
                "detail": "No synthetic wallet ledger or account mutation exists before S3 gates.",
            },
            {
                "name": "Positions and portfolio",
                "status": "EMPTY",
                "detail": (
                    "Only retained historical fills exist; no paper/live position state exists."
                ),
            },
            {
                "name": "Risk decisions",
                "status": "PRECONDITIONS_ONLY",
                "detail": "Risk is currently validation evidence, not a runtime execution engine.",
            },
        ],
        "demo_wallet_design": {
            "schema_version": 1,
            "status": "DESIGN_ONLY_NOT_ACTIVATED",
            "ledger_state": "ABSENT",
            "environment": "RESERVED_FOR_S3",
            "synthetic_capital": "NOT_CREATED",
            "mutation_api": "ABSENT",
            "order_route": "ABSENT",
            "venue_connection": "NONE",
            "execution_authority": "NONE",
            "allowed_future_scope": [
                "isolated synthetic ledger",
                "deterministic local fill simulator",
                "typed account and portfolio snapshots",
                "backtest-versus-demo divergence reports",
                "operator-visible kill-switch drill evidence",
            ],
            "required_gates": [
                "S2_EXIT_PASS",
                "HG_3_APPROVED",
                "one COMPLETE_APPROVABLE strategy context",
                "paper_lane_architecture_decision",
                "security_review_pass",
                "operator activation decision for a specific isolated demo mode",
            ],
            "must_never_include": [
                "exchange credential",
                "venue account connection",
                "funds-transfer permission",
                "real-money balance",
                "venue order routing",
                "copy-trading action",
            ],
            "invariants": [
                "demo records cannot exist in S2",
                "synthetic wallets cannot be constructed in current domain contracts",
                "every future synthetic balance must be tagged non-real-money",
                "demo fills must be derived locally from retained market data",
                "demo divergence cannot promote a strategy without human gates",
            ],
        },
        "stage_gate_readiness": build_stage_gate_readiness(),
        "risk_preconditions": {
            "status": risk_preconditions.get("status", "NOT_RUN"),
            "no_live_capability": risk_preconditions.get("no_live_capability") is True,
            "complete_cost_grid": risk_preconditions.get("complete_cost_grid") is True,
            "promotion_eligible": risk_preconditions.get("promotion_eligible") is True,
        },
        "activation_predicate": [
            "S2_EXIT_PASS",
            "HG_3_APPROVED",
            "validation.status == COMPLETE_APPROVABLE",
            "validation.promotion_eligible == true",
            "paper_lane_architecture_decision_exists",
            "security_review_passes",
            "operator_approved_specific_demo_or_testnet_integration",
        ],
        "prohibited": [
            "credential_request",
            "account_connection",
            "synthetic_wallet_mutation",
            "demo_or_paper_order",
            "venue_order_routing",
            "live_order_capability",
            "real_money",
        ],
    }


def build_stage_gate_readiness() -> dict[str, Any]:
    """Project the S3/S4 gate chain without exposing any activation control."""
    return {
        "schema_version": 1,
        "mode": "LOCAL_READ_ONLY",
        "status": "BLOCKED_BY_GATES",
        "execution_authority": "NONE",
        "capabilities": {
            "writes": "DISABLED",
            "credential_access": "ABSENT",
            "order_endpoint": "ABSENT",
            "venue_connection": "NONE",
            "demo_paper_control": "ABSENT",
            "live_control": "ABSENT",
        },
        "s3_paper_demo": {
            "stage": "S3",
            "status": "NOT_READY",
            "satisfied": [
                "S2 research console implemented",
                "no-live/no-order boundary verified",
                "design-only demo-wallet readiness visible",
            ],
            "blocked_by": [
                "S2_EXIT_PASS",
                "HG_3_APPROVED",
                "one COMPLETE_APPROVABLE strategy context",
                "paper_lane_architecture_decision",
                "security_review_pass",
                "operator activation decision for a specific isolated demo mode",
            ],
            "next_human_actions": [
                "approve HG-3 only after S2 exit evidence supports it",
                "choose a paper-lane architecture after a validated strategy exists",
                "approve a specific isolated demo/paper integration",
            ],
        },
        "s4_live": {
            "stage": "S4",
            "status": "NOT_READY",
            "satisfied": [
                "live states are unreachable in S2",
                "venue/source prep is documented as human-gated",
            ],
            "blocked_by": [
                "S3_EXIT_PASS",
                "paper stability period",
                "quantified backtest-versus-paper divergence",
                "independent live risk and kill-switch package",
                "specific limited-capital venue proposal",
                "HG_5_OPERATOR_APPROVAL",
            ],
            "next_human_actions": [
                "complete human venue/account eligibility checks",
                "approve restricted credentials only after S4 gate evidence",
                "approve limited capital and drawdown limits",
            ],
        },
    }


def _latest_scorecards(root: Path) -> tuple[Path | None, dict[str, Any]]:
    candidates = [
        path
        for path in (root / "artifacts" / "research_lab" / "v0").glob("LAB-*/scorecards.json")
        if path.is_file()
    ]
    if not candidates:
        return None, {}
    path = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
    return path, _json(path)


def _comparisons(root: Path, validation_package: dict[str, Any]) -> dict[str, Any]:
    scorecards_path, scorecards = _latest_scorecards(root)
    candidate_rows = []
    scorecard_candidates = scorecards.get("candidates")
    if isinstance(scorecard_candidates, list):
        for candidate in scorecard_candidates:
            if not isinstance(candidate, dict):
                continue
            dimensions = candidate.get("dimensions")
            if not isinstance(dimensions, dict):
                dimensions = {}
            candidate_rows.append(
                {
                    "candidate_id": candidate.get("candidate_id", "UNKNOWN"),
                    "validation_state": candidate.get("validation_state", "UNKNOWN"),
                    "approval_state": candidate.get("approval_state", "UNKNOWN"),
                    "pass_count": sum(str(value) == "PASS" for value in dimensions.values()),
                    "fail_count": sum(str(value) == "FAIL" for value in dimensions.values()),
                    "scope_note_count": sum(
                        str(value) == "PASS_WITH_SCOPE_NOTE" for value in dimensions.values()
                    ),
                    "dimensions": dict(
                        sorted((str(key), str(value)) for key, value in dimensions.items())
                    ),
                    "blockers": [
                        str(item) for item in candidate.get("blockers", []) if isinstance(item, str)
                    ],
                }
            )

    gates_raw = validation_package.get("gates")
    gates = gates_raw if isinstance(gates_raw, dict) else {}
    validation_gates = [
        {
            "gate": str(gate),
            "status": str(value.get("status", "UNKNOWN")) if isinstance(value, dict) else "UNKNOWN",
            "reason": str(value.get("reason", "")) if isinstance(value, dict) else "",
        }
        for gate, value in sorted(gates.items())
    ]

    g10_path = root / "artifacts" / "validation" / "G10_CANDIDATE_EVIDENCE_2026_07_11.json"
    g10 = _json(g10_path)
    families_raw = g10.get("families")
    families = families_raw if isinstance(families_raw, dict) else {}
    g10_rows = []
    for family, value in sorted(families.items()):
        if not isinstance(value, dict):
            continue
        pbo = value.get("pbo")
        dsr = value.get("dsr")
        primary_pbo = pbo.get("primary", {}) if isinstance(pbo, dict) else {}
        primary_dsr = dsr.get("primary", {}) if isinstance(dsr, dict) else {}
        g10_rows.append(
            {
                "family": str(family).upper(),
                "verdict": value.get("verdict", "UNKNOWN"),
                "selected_trial_key": value.get("selected_trial_key", "UNKNOWN"),
                "trial_count": value.get("trial_count", 0),
                "pbo": primary_pbo.get("pbo"),
                "dsr": primary_dsr.get("dsr"),
            }
        )

    cross_path = root / "artifacts" / "validation" / "CROSS_ENGINE_REPRODUCTION_2026_07_11.json"
    cross = _json(cross_path)
    seed_probe_path = (
        root
        / "artifacts"
        / "validation"
        / "seed_candidates"
        / "SEED_VALIDATION_PROBE_2026_07_11.json"
    )
    seed_probe = _json(seed_probe_path)
    seed_contexts = []
    contexts = seed_probe.get("contexts")
    if isinstance(contexts, list):
        for context in contexts:
            if not isinstance(context, dict):
                continue
            identity = context.get("context")
            full_period = context.get("full_period")
            holdout = context.get("temporal_splits", {})
            holdout_final = (
                holdout.get("holdout_final_third", {}) if isinstance(holdout, dict) else {}
            )
            seed_contexts.append(
                {
                    "candidate_id": (
                        identity.get("candidate_id", "UNKNOWN")
                        if isinstance(identity, dict)
                        else "UNKNOWN"
                    ),
                    "dataset": identity.get("dataset", "UNKNOWN")
                    if isinstance(identity, dict)
                    else "UNKNOWN",
                    "trial_key": (
                        identity.get("trial_key", "UNKNOWN")
                        if isinstance(identity, dict)
                        else "UNKNOWN"
                    ),
                    "status": context.get("status", "UNKNOWN"),
                    "approval_status": context.get("approval_status", "UNKNOWN"),
                    "total_return": (
                        full_period.get("total_return") if isinstance(full_period, dict) else None
                    ),
                    "holdout_return": (
                        holdout_final.get("total_return")
                        if isinstance(holdout_final, dict)
                        else None
                    ),
                    "blocker_count": len(
                        [item for item in context.get("blockers", []) if isinstance(item, str)]
                    ),
                }
            )

    seed_g10_path = (
        root
        / "artifacts"
        / "validation"
        / "seed_candidates"
        / "SEED_G10_QC2_ETHUSDT_1H_2026_07_11.json"
    )
    seed_g10 = _json(seed_g10_path)
    seed_pbo = seed_g10.get("pbo")
    seed_dsr = seed_g10.get("dsr")
    seed_pbo_primary = seed_pbo.get("primary", {}) if isinstance(seed_pbo, dict) else {}
    seed_dsr_primary = seed_dsr.get("primary", {}) if isinstance(seed_dsr, dict) else {}
    refs = [
        "artifacts/validation/B2_F0_S0/validation_summary.json",
        str(g10_path.relative_to(root)),
        str(cross_path.relative_to(root)),
        str(seed_probe_path.relative_to(root)),
        str(seed_g10_path.relative_to(root)),
    ]
    if scorecards_path is not None:
        refs.append(str(scorecards_path.relative_to(root)))
    return {
        "schema_version": 1,
        "mode": "LOCAL_READ_ONLY",
        "status": "NO_PROMOTION_CANDIDATE",
        "execution_authority": "NONE",
        "winner_selected": False,
        "capabilities": {
            "writes": "DISABLED",
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "approval_mutation": "DISABLED",
        },
        "candidate_rows": candidate_rows,
        "validation_gates": validation_gates,
        "g10_rows": g10_rows,
        "cross_engine": {
            "verdict": cross.get("verdict", "UNKNOWN"),
            "candidate": cross.get("candidate", "UNKNOWN"),
            "fill_match_ratio": (
                cross.get("freqtrade_single_pair", {}).get("fill_match_ratio")
                if isinstance(cross.get("freqtrade_single_pair"), dict)
                else None
            ),
            "economic_direction_agreement": cross.get("economic_direction_agreement") is True,
            "scope_notes": [
                str(item) for item in cross.get("scope_notes", []) if isinstance(item, str)
            ],
        },
        "seed_contexts": seed_contexts,
        "seed_g10": {
            "candidate_id": seed_g10.get("candidate_id", "UNKNOWN"),
            "dataset": seed_g10.get("dataset", "UNKNOWN"),
            "selected_trial_key": seed_g10.get("selected_trial_key", "UNKNOWN"),
            "status": seed_g10.get("g10_gate_status", "UNKNOWN"),
            "pbo": seed_pbo_primary.get("pbo"),
            "dsr": seed_dsr_primary.get("dsr"),
        },
        "evidence_refs": refs,
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
    for path in sorted((root / "strategies" / "external").glob("*/replay_candidate.yaml")):
        text = path.read_text(encoding="utf-8")
        strategy_id_match = re.search(r"^strategy_id:\s*([^\n]+)$", text, re.MULTILINE)
        status_match = re.search(r"^status:\s*([^\n]+)$", text, re.MULTILINE)
        validation_state_match = re.search(r"^validation_state:\s*([^\n]+)$", text, re.MULTILINE)
        execution_authority_match = re.search(
            r"^execution_authority:\s*([^\n]+)$", text, re.MULTILINE
        )
        promotion_eligible_match = re.search(
            r"^promotion_eligible:\s*(true|false)$", text, re.MULTILINE
        )
        strategies.append(
            {
                "id": strategy_id_match.group(1).strip() if strategy_id_match else path.parent.name,
                "name": path.parent.name,
                "family": "external_replay",
                "status": (
                    status_match.group(1).strip() if status_match else "SPECIFIED_NOT_REPRODUCED"
                ),
                "validation_state": (
                    validation_state_match.group(1).strip()
                    if validation_state_match
                    else "UNVALIDATED"
                ),
                "promotion_eligible": (
                    promotion_eligible_match.group(1).strip() == "true"
                    if promotion_eligible_match
                    else False
                ),
                "execution_authority": (
                    execution_authority_match.group(1).strip()
                    if execution_authority_match
                    else "NONE"
                ),
                "spec": str((path.parent / "canonical_strategy_spec.yaml").relative_to(root)),
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
        "dictionary_concepts": _dictionary_concepts(root),
        "trading_domain": _trading_domain(runs, validation_package),
        "comparisons": _comparisons(root, validation_package),
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
