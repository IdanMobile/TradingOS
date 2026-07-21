"""T-017-05: AI cost telemetry projection for the dashboard.

Reads the append-only ledger real benchmark runs write (`cost_telemetry.jsonl`) and the
latest run summary. Read-only; exposes no control and never touches a credential — cost
rows are written by the runs themselves, this only aggregates what already happened.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LEDGER = Path("artifacts") / "ai_benchmarks" / "cost_telemetry.jsonl"
SUMMARY = Path("artifacts") / "ai_benchmarks" / "REAL_RUN_MODEA_V1.json"


def build_ai_costs(root: Path) -> dict[str, Any]:
    rows = _rows(root)
    by_model: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not int(row.get("calls") or 0):
            continue  # aborted/blocked configs contribute no spend
        model = str(row.get("model") or "unknown")
        entry = by_model.setdefault(model, {"calls": 0, "cost_usd": 0.0, "runs": 0})
        entry["calls"] += int(row.get("calls") or 0)
        entry["cost_usd"] = round(entry["cost_usd"] + float(row.get("cost_usd") or 0), 6)
        entry["runs"] += 1

    summary = _json(root / SUMMARY)
    return {
        "schema_version": 1,
        "available": bool(rows),
        "total_cost_usd": round(sum(r["cost_usd"] for r in by_model.values()), 6),
        "total_calls": sum(r["calls"] for r in by_model.values()),
        "by_model": by_model,
        "last_run_at": rows[-1].get("at") if rows else None,
        "last_run": (
            {
                "variance_by_config": summary.get("variance_by_config", {}),
                "blocked_configs": summary.get("blocked_configs", {}),
                "generated_at": summary.get("generated_at"),
            }
            if summary
            else None
        ),
        "ledger": str(LEDGER),
        "note": (
            "Costs from authorized benchmark runs only, computed from provider-reported "
            "usage tokens at pricing pinned per record. No credential is read here."
        ),
    }


def _rows(root: Path) -> list[dict[str, Any]]:
    target = root / LEDGER
    if not target.is_file():
        return []
    out = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
