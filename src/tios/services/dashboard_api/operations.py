"""Operations view: data freshness + per-strategy results, and the data-refresh trigger.

`build_operations` is read-only — it projects retained files (daily_update status +
strategy-search artifacts) with no mutation. `trigger_data_update` is the ONE bounded
write action: it launches ONLY the local `daily_update` module (no params, no venue,
no order, no credential), records an audit line, and returns immediately. This is a
governed console action (see DECISION_LOG D-041); loopback binding is enforced by the
server, and any wider action needs its own decision gate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

# Strategy-search artifacts to aggregate (path, search-kind label).
_SEARCH_ARTIFACTS = (
    ("artifacts/research_lab/external_strategy_search/EXTERNAL_STRATEGY_SEARCH_2026_07_12.json",
     "public-copied"),
    ("artifacts/research_lab/signal_strategy_search/SIGNAL_STRATEGY_SEARCH.json",
     "signal-based"),
)  # fmt: skip
_DATA_STATUS_PATHS = (
    "data/normalized_multi/daily_update_status.json",
    "data/normalized/daily_update_status.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _mtime_utc(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        return None


def _data_update(root: Path) -> dict[str, Any]:
    for rel in _DATA_STATUS_PATHS:
        status = _read_json(root / rel)
        if status:
            return {
                "last_update_utc": status.get("last_run_utc"),
                "files_updated": status.get("files_updated", 0),
                "bars_added": status.get("bars_added", 0),
                "target": status.get("target"),
            }
    return {"last_update_utc": None, "files_updated": 0, "bars_added": 0, "target": None}


def _best_context(contexts: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [c for c in contexts if "best_total_return" in c]
    if not scored:
        return None
    return max(scored, key=lambda c: float(c["best_total_return"]))


def _strategy_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel, kind in _SEARCH_ARTIFACTS:
        path = root / rel
        report = _read_json(path)
        tested = _mtime_utc(path)
        for strat in report.get("strategies", []):
            contexts = strat.get("contexts", [])
            best = _best_context(contexts)
            passed = [c for c in contexts if c.get("screen_pass")]
            rows.append(
                {
                    "strategy_id": strat.get("strategy_id"),
                    "source": strat.get("source"),
                    "search": kind,
                    "best_return_pct": (
                        round(float(best["best_total_return"]) * 100, 1) if best else None
                    ),
                    "best_dataset": best.get("dataset") if best else None,
                    "screen_pass": bool(passed),
                    "contexts_passed": len(passed),
                    "contexts_total": len(contexts),
                    "last_tested_utc": tested,
                    "approval_status": strat.get("approval_status", "NOT_ELIGIBLE"),
                    "execution_authority": strat.get("execution_authority", "NONE"),
                }
            )
    rows.sort(key=lambda r: (not r["screen_pass"], -(r["best_return_pct"] or -1e9)))
    return rows


def build_operations(root: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[4]
    strategies = _strategy_rows(root)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "data_update": _data_update(root),
        "strategy_count": len(strategies),
        "strategies_passing_screen": sum(1 for s in strategies if s["screen_pass"]),
        "strategies": strategies,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
    }


def trigger_data_update(root: Path) -> dict[str, Any]:
    """Governed action (D-041): launch ONLY the local daily_update refresh, detached."""
    triggered_at = datetime.now(tz=UTC).isoformat()
    log = root / "data" / "daily_update_run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    # Bounded: a fixed argv — the module cannot be swapped or parameterised from the web.
    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "tios.dataset.daily_update"],
        cwd=str(root),
        stdout=log.open("a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
    )
    audit = root / "artifacts" / "operations" / "data_update_triggers.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "triggered_at": triggered_at,
        "source": "local_dashboard_operator",
        "action": "daily_update",
    }
    with audit.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {
        "schema_version": 1,
        "status": "started",
        "action": "daily_update",
        "triggered_at": triggered_at,
    }
