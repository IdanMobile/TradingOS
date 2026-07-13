"""Operations view: data freshness + per-strategy results, and the data-refresh trigger.

`build_operations` is read-only — it projects retained files (daily_update status +
strategy-search artifacts) with no mutation. `trigger_data_update` is the ONE bounded
write action: it launches ONLY the local `daily_update` module (no params, no venue,
no order, no credential), records an audit line, and returns immediately. This is a
governed console action (see DECISION_LOG D-041); loopback binding is enforced by the
server, and any wider action needs its own decision gate.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from tios.services.dashboard_api.audit import confined_audit_handle
from tios.services.dashboard_api.status import build_completion_matrix

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
DATA_UPDATE_AUDIT_PATH = Path("artifacts/operations/data_update_triggers.jsonl")


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


DEMO_BOT_ACTIVITY_PATH = "artifacts/demo_bot/activity.jsonl"
DEMO_BOT_PNL_PATH = "artifacts/demo_bot/pnl.json"
DEMO_BOT_HEARTBEAT_PATH = "artifacts/demo_bot/heartbeat.json"
_DEMO_BOT_FIELDS = ("recorded_at", "symbol", "signal", "side", "signal_price", "fill_price", "qty")


def build_demo_bot(root: Path) -> dict[str, Any]:
    """Read-only projection of quarantined historical demo evidence."""
    entries: list[dict[str, Any]] = []
    try:
        for line in (root / DEMO_BOT_ACTIVITY_PATH).read_text().splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                entries.append(item)
    except OSError:
        entries = []
    pnl = _read_json(root / DEMO_BOT_PNL_PATH)
    heartbeat = _read_json(root / DEMO_BOT_HEARTBEAT_PATH)
    has_evidence = bool(entries or pnl or heartbeat)
    return {
        "total_orders": len(entries),
        "buys": sum(1 for e in entries if e.get("side") == "BUY"),
        "sells": sum(1 for e in entries if e.get("side") == "SELL"),
        "last_activity_utc": entries[-1].get("recorded_at") if entries else None,
        "heartbeat": heartbeat or None,  # retained historical snapshot; not current liveness
        "pnl": pnl or None,  # retained historical snapshot; not current venue state
        "orders": [
            {field: entry.get(field) for field in _DEMO_BOT_FIELDS}
            for entry in entries[-25:][::-1]  # newest first
        ],
        "activity_classification": "HISTORICAL_EVIDENCE" if has_evidence else "NONE",
        "evidence_venue": "BYBIT_DEMO" if has_evidence else None,
        "current_network_state": "QUARANTINED",
        "venue_connection": "NONE",
        "execution_authority": "NONE",
    }


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
        "completion_matrix": build_completion_matrix(root),
        "demo_bot": build_demo_bot(root),
        "execution_authority": "NONE",
        "venue_connection": "NONE",
    }


def trigger_data_update(root: Path, idempotency_key: str) -> dict[str, Any]:
    """Governed action (D-041): launch ONLY the local daily_update refresh, detached."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", idempotency_key):
        raise ValueError("idempotency_key must be a bounded identifier")
    with confined_audit_handle(root, DATA_UPDATE_AUDIT_PATH, create=True) as handle:
        assert handle is not None
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        retained: list[dict[str, Any]] = []
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError as error:
                raise ValueError("data update audit is malformed") from error
            if isinstance(record, dict) and record.get("idempotency_key") == idempotency_key:
                retained.append(record)
        if retained:
            if any(record.get("action") != "daily_update" for record in retained):
                raise ValueError("idempotency key conflicts with retained data update")
            completed = next(
                (record for record in reversed(retained) if record.get("phase") == "COMPLETED"),
                None,
            )
            if completed is not None:
                return {
                    "schema_version": 1,
                    "status": "started",
                    "action": "daily_update",
                    "triggered_at": completed["triggered_at"],
                    "idempotent": True,
                }
            failed = next(
                (record for record in reversed(retained) if record.get("phase") == "FAILED"),
                None,
            )
            if failed is not None:
                raise ValueError(str(failed["failure_message"]))
            prepared = retained[-1]
            if prepared.get("phase") != "PREPARED":
                raise ValueError("data update audit phase is invalid")
            failed = {
                **prepared,
                "phase": "FAILED",
                "failure_code": "INDETERMINATE_PREPARED",
                "failure_message": (
                    "data update launch outcome is indeterminate for this idempotency_key; "
                    "use a new key to retry"
                ),
            }
            handle.write(json.dumps(failed, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            raise ValueError(str(failed["failure_message"]))
        triggered_at = datetime.now(tz=UTC).isoformat()
        prepared = {
            "schema_version": 1,
            "phase": "PREPARED",
            "triggered_at": triggered_at,
            "source": "local_dashboard_operator",
            "action": "daily_update",
            "idempotency_key": idempotency_key,
        }
        handle.write(json.dumps(prepared, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        log = root / "data" / "daily_update_run.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("a", encoding="utf-8") as output:
                # Bounded: fixed argv; no request value reaches the child command.
                subprocess.Popen(  # noqa: S603
                    [sys.executable, "-m", "tios.dataset.daily_update"],
                    cwd=str(root),
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    env={**os.environ, "PYTHONPATH": str(root / "src")},
                )
        except OSError as error:
            failed = {
                **prepared,
                "phase": "FAILED",
                "failure_code": "LAUNCH_FAILED",
                "failure_message": (
                    "data update launch failed for this idempotency_key; use a new key to retry"
                ),
            }
            handle.write(json.dumps(failed, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            raise ValueError(str(failed["failure_message"])) from error
        completed = {**prepared, "phase": "COMPLETED"}
        handle.write(json.dumps(completed, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        return {
            "schema_version": 1,
            "status": "started",
            "action": "daily_update",
            "triggered_at": triggered_at,
            "idempotent": False,
        }
