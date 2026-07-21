"""One place to see every open item, classified by who can actually act on it.

Open work is spread across three surfaces that answer different questions and none of
which answers "what is left". `todos/NN_*.md` holds the formal task registry, currently
reporting zero open tasks — true, and misleading, because the live work moved into the
parked ledger. `artifacts/driver/parked_items.jsonl` holds what is genuinely unreachable
and why. The orchestrator situation holds anything that stopped the loop.

Merging them is only half the job. The question an operator actually has is not "what is
open" but "what needs *me*", so every item is classified by who can act:

- `requires_operator` — needs a fact, a credential, or a decision only the human has.
- `agent_executable` — the orchestrator or an agent can do it now.
- `blocked_external` — waiting on time, data that does not exist, or an upstream stage.
- `recurring` — ongoing discipline, never "done".

The distinction matters because a list that mixes them reads as a backlog the operator owes
work on, when most of it is either automatic or genuinely unreachable. Read-only: this
projection exposes no control.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tios.ops.driver import parked_items
from tios.ops.orchestrator import ESCALATE, REPORT_DIR, SITUATION_FILENAME
from tios.services.dashboard_api.status import build_status

REQUIRES_OPERATOR = "requires_operator"
AGENT_EXECUTABLE = "agent_executable"
BLOCKED_EXTERNAL = "blocked_external"
RECURRING = "recurring"

# Phrases that mean a human is the only unblocker. Deliberately specific: matching a bare
# word like "operator" catches causes that merely *mention* the operator while describing
# something else entirely, which inflates the list the human thinks they owe work on.
_OPERATOR_PHRASES = (
    "operator-only",
    "operator decision",
    "OPERATOR REVIEW REQUESTED",
    "no provider credential",
    "credentials are operator-only",
    "reviewer independent",
    "not independent",
)


def _classify_task(status: str) -> str:
    upper = status.upper()
    if upper.startswith("ONGOING") or "RECURRING" in upper:
        return RECURRING
    if any(signal.upper() in upper for signal in ("CREDENTIAL", "S4", "HUMAN")):
        return REQUIRES_OPERATOR
    if "REOPENED" in upper:
        return AGENT_EXECUTABLE
    if "S3" in upper or "DEFERRED" in upper:
        return BLOCKED_EXTERNAL
    return AGENT_EXECUTABLE


def _classify_park(item: dict[str, Any]) -> str:
    status = str(item.get("status", ""))
    if status.startswith("RESOLVED") and "OPERATOR REVIEW REQUESTED" not in status:
        return ""  # a resolved park is a record, not open work
    blob = f"{item.get('item', '')} {item.get('cause', '')} {status}"
    if any(phrase in blob for phrase in _OPERATOR_PHRASES):
        return REQUIRES_OPERATOR
    return BLOCKED_EXTERNAL


def build_open_work(root: Path) -> dict[str, Any]:
    """Merge task registry, parked ledger, and orchestrator escalations."""
    buckets: dict[str, list[dict[str, Any]]] = {
        REQUIRES_OPERATOR: [],
        AGENT_EXECUTABLE: [],
        BLOCKED_EXTERNAL: [],
        RECURRING: [],
    }

    status = build_status(root)
    for task in [*status["open_tasks"], *status["gated_tasks"], *status["recurring_tasks"]]:
        buckets[_classify_task(task["status"])].append(
            {
                "source": "task",
                "ref": task["id"],
                "title": task["title"],
                "detail": task["status"],
                "where": task["file"],
            }
        )

    for item in parked_items(root):
        bucket = _classify_park(item)
        if not bucket:
            continue
        buckets[bucket].append(
            {
                "source": "parked",
                "ref": item.get("phase", ""),
                "title": item.get("item", ""),
                "detail": item.get("cause", ""),
                "where": "artifacts/driver/parked_items.jsonl",
            }
        )

    # An escalation stopped the orchestrator; nothing outranks it.
    for row in _escalations(root):
        buckets[REQUIRES_OPERATOR].insert(
            0,
            {
                "source": "escalation",
                "ref": row.get("domain", ""),
                "title": row.get("summary", ""),
                "detail": "The orchestrator halted on this.",
                "where": "artifacts/orchestrator/SITUATION.json",
            },
        )

    return {
        "schema_version": 1,
        "counts": {name: len(rows) for name, rows in buckets.items()},
        "total_open": sum(len(rows) for name, rows in buckets.items() if name != RECURRING),
        **buckets,
        "interpretation": (
            "requires_operator needs a human fact, credential, or decision. "
            "agent_executable can be done now without you. blocked_external waits on time, "
            "absent data, or an upstream stage. recurring is ongoing discipline."
        ),
        "execution_authority": "NONE",
    }


def _escalations(root: Path) -> list[dict[str, Any]]:
    target = root / REPORT_DIR / SITUATION_FILENAME
    if not target.is_file():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(payload, dict):
        return []
    return [
        row
        for row in payload.get("observations", [])
        if isinstance(row, dict) and row.get("severity") == ESCALATE
    ]
