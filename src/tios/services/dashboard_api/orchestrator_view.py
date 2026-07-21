"""Read-only dashboard projection of orchestrator state.

Surfaces what the autonomous worker last saw: escalations first, then actions it intends to
take, then routine observations. Read-only by construction — this projection exposes no
control, so viewing the orchestrator can never start, stop, or steer it.

Escalations lead because they are the only class that stops the loop, and a halted
orchestrator that looks idle is the most misleading thing this page could show.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tios.ops.driver import parked_items
from tios.ops.orchestrator import ACT, ESCALATE, JOURNAL_FILENAME, REPORT_DIR, SITUATION_FILENAME

JOURNAL_TAIL = 100  # ~25h of 15-min cycles; enough for a useful operator history view


def build_orchestrator_view(root: Path) -> dict[str, Any]:
    """Project the last observed situation, recent journal, and parked work."""
    situation = _read_situation(root)
    parked = parked_items(root)

    if situation is None:
        return {
            "schema_version": 1,
            "state": "NEVER_RUN",
            "interpretation": "The orchestrator has not completed a cycle in this checkout.",
            "halted": False,
            "escalations": [],
            "actions": [],
            "observations": [],
            "journal": [],
            "parked": [_parked_row(item) for item in parked],
            "execution_authority": "NONE",
        }

    observations = situation.get("observations", [])
    halted = bool(situation.get("halted"))

    return {
        "schema_version": 1,
        "state": "HALTED_AWAITING_OPERATOR" if halted else "RUNNING",
        "interpretation": (
            "The orchestrator stopped and needs an operator to look at the escalations below."
            if halted
            else "The orchestrator is observing autonomously; nothing requires an operator."
        ),
        "observed_at": situation.get("observed_at", ""),
        "halted": halted,
        "escalations": [row for row in observations if row.get("severity") == ESCALATE],
        "actions": [row for row in observations if row.get("severity") == ACT],
        "observations": observations,
        "journal": _read_journal(root),
        "parked": [_parked_row(item) for item in parked],
        "execution_authority": "NONE",
    }


def _read_situation(root: Path) -> dict[str, Any] | None:
    target = root / REPORT_DIR / SITUATION_FILENAME
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_journal(root: Path) -> list[dict[str, Any]]:
    target = root / REPORT_DIR / JOURNAL_FILENAME
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-JOURNAL_TAIL:][::-1]


def _parked_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item": item.get("item", ""),
        "cause": item.get("cause", ""),
        "phase": item.get("phase", ""),
        "parked_at": item.get("parked_at", ""),
    }
