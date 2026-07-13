"""Human-readable, paper-first dashboard projection and bounded local controls."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO
from zoneinfo import ZoneInfo

from tios.services.dashboard_api.audit import AuditPathError, confined_audit_handle
from tios.services.dashboard_api.news import build_external_news
from tios.services.dashboard_api.operations import build_operations
from tios.services.dashboard_api.status import build_status
from tios.services.jobs import JobStore, build_jobs_projection
from tios.services.jobs.runner import default_database as default_jobs_database
from tios.services.paper.store import (
    SCHEMA_VERSION as PAPER_SCHEMA_VERSION,
)
from tios.services.paper.store import (
    PaperAuditAction,
    PaperEventType,
    PaperStore,
    PaperStoreError,
    PaperStoreProjection,
    _audit,
    _event,
    _point,
    _projection,
)
from tios.services.paper.store import (
    default_database as default_paper_database,
)

COCKPIT_SCHEMA_VERSION = 1
RANGES = frozenset({"24h", "1d", "3d", "7d", "1m", "all"})
ACTIONS = frozenset(
    {
        "ACKNOWLEDGE",
        "PAUSE_PAPER_ENTRIES",
        "RESUME_PAPER_ENTRIES",
        "PAUSE_RESEARCH_SCHEDULE",
        "RESUME_RESEARCH_SCHEDULE",
    }
)
ACKNOWLEDGEABLE_SEVERITIES = frozenset({"INFO", "INFORMATIONAL", "WARNING"})
AUDIT_PATH = Path("artifacts/human_decisions/cockpit_actions.jsonl")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")
_TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
}


class CockpitActionError(ValueError):
    """An action cannot cross the local cockpit boundary."""

    status_code = 400


class CockpitUnavailableError(CockpitActionError):
    status_code = 409


class CockpitNotFoundError(CockpitActionError):
    status_code = 404


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cockpit timestamps must include a timezone")
    return value.astimezone(UTC).isoformat()


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _acknowledgeable(severity: object) -> bool:
    return isinstance(severity, str) and severity.strip().upper() in ACKNOWLEDGEABLE_SEVERITIES


def _range_start(as_of: datetime, range_name: str) -> datetime | None:
    if range_name not in RANGES:
        raise ValueError("range must be one of 24h, 1d, 3d, 7d, 1m, all")
    if range_name == "all":
        return None
    if range_name == "1d":
        local = as_of.astimezone(ZoneInfo("Asia/Jerusalem"))
        return datetime.combine(local.date(), time.min, tzinfo=local.tzinfo).astimezone(UTC)
    return (
        as_of
        - {
            "24h": timedelta(hours=24),
            "3d": timedelta(days=3),
            "7d": timedelta(days=7),
            "1m": timedelta(days=30),
        }[range_name]
    )


def _read_paper_projection(root: Path) -> PaperStoreProjection | None:
    """Validate and read an existing paper DB without creating a file, schema, or runtime."""
    path = default_paper_database(root)
    if not path.exists():
        return None
    store = PaperStore(path, root=root)
    before = store._assert_safe(create=False)
    if before is None:
        return None
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        versions = connection.execute("SELECT version FROM schema_version").fetchall()
        if len(versions) != 1 or int(versions[0][0]) != PAPER_SCHEMA_VERSION:
            raise PaperStoreError("unsupported paper database schema")
        if str(connection.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise PaperStoreError("paper database integrity check failed")
        events = tuple(
            _event(row)
            for row in connection.execute("SELECT * FROM paper_events ORDER BY sequence")
        )
        points = tuple(
            _point(row)
            for row in connection.execute("SELECT * FROM portfolio_points ORDER BY sequence")
        )
        audits = tuple(
            _audit(row) for row in connection.execute("SELECT * FROM paper_audit ORDER BY sequence")
        )
    finally:
        connection.close()
    if store._assert_safe(create=False) != before:
        raise PaperStoreError("paper database identity changed during cockpit read")
    return _projection(events, points, audits)


def _selected_points(
    projection: PaperStoreProjection, as_of: datetime, range_name: str
) -> tuple[Any, ...]:
    retained = tuple(point for point in projection.portfolio_points if point.observed_at <= as_of)
    if not retained:
        raise PaperStoreError("paper portfolio has no retained point")
    start = _range_start(as_of, range_name)
    if start is None:
        return retained
    baseline = next(
        (point for point in reversed(retained) if point.observed_at <= start), retained[0]
    )
    return (baseline,) + tuple(
        point
        for point in retained
        if point.sequence > baseline.sequence and point.observed_at > start
    )


def _validate_paper_relations(projection: PaperStoreProjection, starts: dict[str, Any]) -> None:
    bot_ids = set(starts)
    if len(starts) != sum(
        event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
        for event in projection.events
    ):
        raise PaperStoreError("paper state contains duplicate bot activation")
    signals: dict[str, str] = {}
    for event in projection.events:
        if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED":
            continue
        if (
            event.event_type
            in {
                PaperEventType.BOT,
                PaperEventType.SIGNAL,
                PaperEventType.RISK,
                PaperEventType.FILL,
                PaperEventType.HEARTBEAT,
                PaperEventType.INCIDENT,
            }
            and event.subject_id not in bot_ids
        ):
            raise PaperStoreError("paper event references an unknown bot")
        if event.event_type is PaperEventType.SIGNAL:
            signal_id = str(event.payload["signal_id"])
            if signal_id in signals and signals[signal_id] != event.subject_id:
                raise PaperStoreError("paper signal identity crosses bot boundaries")
            signals[signal_id] = event.subject_id
        elif event.event_type in {PaperEventType.RISK, PaperEventType.FILL}:
            if signals.get(str(event.payload["signal_id"])) != event.subject_id:
                raise PaperStoreError("paper decision references an unknown signal")


def _paper_snapshot(
    projection: PaperStoreProjection, as_of: datetime, range_name: str
) -> dict[str, Any]:
    starts = {
        event.subject_id: event
        for event in projection.events
        if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
    }
    if not starts or not projection.portfolio_points:
        raise PaperStoreError("paper state has no complete retained activation")
    _validate_paper_relations(projection, starts)

    evaluated = {
        event.subject_id: event
        for event in projection.events
        if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "EVALUATED"
    }
    health: dict[str, dict[str, Any]] = {}
    marks: dict[str, Decimal] = {}
    for bot_id in starts:
        components: dict[str, Any] = {}
        for source_name in ("BINANCE_BOOK_TICKER", "BINANCE_KLINES"):
            components[source_name] = next(
                (
                    event
                    for event in reversed(projection.events)
                    if event.event_type is PaperEventType.HEARTBEAT
                    and event.subject_id == bot_id
                    and event.payload.get("source") == source_name
                ),
                None,
            )
        health[bot_id] = components
        quote = components["BINANCE_BOOK_TICKER"]
        if quote is not None:
            marks[bot_id] = Decimal(str(quote.payload["mark_price"]))

    positions: dict[str, dict[str, Any]] = {}
    for event in projection.events:
        if event.event_type is not PaperEventType.FILL:
            continue
        prior = positions.get(event.subject_id)
        quantity = Decimal(str(event.payload["position_quantity_after"]))
        fill_quantity = Decimal(str(event.payload["quantity"]))
        fill_price = Decimal(str(event.payload["price"]))
        if event.payload["side"] == "BUY":
            entry_quantity = (prior["entry_quantity"] if prior else Decimal(0)) + fill_quantity
            entry_notional = (prior["entry_notional"] if prior else Decimal(0)) + (
                fill_quantity * fill_price
            )
        else:
            if prior is None or prior["entry_quantity"] <= 0:
                raise PaperStoreError("paper sell fill has no retained entry")
            average_entry = prior["entry_notional"] / prior["entry_quantity"]
            entry_quantity = quantity
            entry_notional = average_entry * quantity
        positions[event.subject_id] = {
            "quantity": quantity,
            "cost": Decimal(str(event.payload["position_cost_after"])),
            "realized": Decimal(str(event.payload["realized_pnl_after"])),
            "mark": fill_price,
            "entry_quantity": entry_quantity,
            "entry_notional": entry_notional,
            "opened_at": (
                event.occurred_at
                if quantity > 0 and (prior is None or prior["quantity"] == 0)
                else prior["opened_at"]
                if prior is not None
                else event.occurred_at
            ),
        }

    unresolved: dict[str, list[Any]] = {bot_id: [] for bot_id in starts}
    for event in projection.events:
        if event.event_type is not PaperEventType.INCIDENT or event.subject_id not in starts:
            continue
        item_id = f"paper-incident-{event.sequence}"
        source = event.payload.get("source")
        acknowledgement_applies = source != "RISK_ENGINE"
        recovery = (
            health[event.subject_id]["BINANCE_BOOK_TICKER"]
            if source == "BINANCE_BOOK_TICKER"
            else health[event.subject_id]["BINANCE_KLINES"]
            if source in {"BINANCE_KLINES", "BINANCE_PUBLIC_DATA"}
            else evaluated.get(event.subject_id)
            if source == "STRATEGY_EVALUATOR" and event.payload.get("code") != "MISSED_BARS"
            else None
        )
        if (
            not acknowledgement_applies or item_id not in projection.acknowledged_item_ids
        ) and not (recovery is not None and recovery.sequence > event.sequence):
            unresolved[event.subject_id].append(event)

    bot_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    attention: list[dict[str, Any]] = []
    for bot_id, start in starts.items():
        risk = start.payload["risk_policy"]
        stale_after = int(risk["stale_after_seconds"])
        component_events = health[bot_id]
        heartbeat = max(
            (event for event in component_events.values() if event is not None),
            key=lambda event: event.sequence,
            default=None,
        )
        stale = any(
            event is None or (as_of - event.occurred_at).total_seconds() > stale_after
            for event in component_events.values()
        ) or bool(unresolved[bot_id])
        position = positions.get(bot_id)
        mark = marks.get(bot_id, position["mark"] if position else None)
        net_pnl = (
            Decimal(0)
            if position is None
            else position["realized"] + position["quantity"] * mark - position["cost"]
        )
        trades = wins = 0
        realized = Decimal(0)
        for event in projection.events:
            if event.subject_id != bot_id:
                continue
            if event.event_type is PaperEventType.FILL:
                updated_realized = Decimal(str(event.payload["realized_pnl_after"]))
                if event.payload["side"] == "SELL":
                    trades += 1
                    wins += updated_realized > realized
                realized = updated_realized
        evaluated_at = (
            datetime.fromisoformat(str(evaluated[bot_id].payload["last_evaluated_bar_at"]))
            if bot_id in evaluated
            else None
        )
        next_at = (
            evaluated_at + timedelta(seconds=_TIMEFRAME_SECONDS[str(start.payload["timeframe"])])
            if evaluated_at is not None and str(start.payload["timeframe"]) in _TIMEFRAME_SECONDS
            else None
        )
        phase = (
            "STALE"
            if stale
            else "PAUSED"
            if projection.entries_paused
            else "POSITION_OPEN"
            if position is not None and position["quantity"] > 0
            else "WATCHING"
        )
        bot_rows.append(
            {
                "bot_id": bot_id,
                "strategy_version_ref": start.payload["strategy_version_ref"],
                "symbol": start.payload["symbol"],
                "timeframe": start.payload["timeframe"],
                "config_digest": start.payload["config_digest"],
                "phase": phase,
                "started_at": _iso(start.occurred_at),
                "uptime_seconds": max(0, int((as_of - start.occurred_at).total_seconds())),
                "heartbeat_at": _iso(heartbeat.occurred_at if heartbeat else None),
                "last_evaluated_bar_at": _iso(evaluated_at),
                "next_evaluation_at": _iso(next_at),
                "conditions_met": None,
                "conditions_unavailable_reason": (
                    "Condition-level evaluation is not retained in paper events."
                ),
                "entries_paused": projection.entries_paused,
                "allocated_capital": None,
                "allocation_unavailable_reason": (
                    "Actual bot allocation is not retained in paper activation events."
                ),
                "net_pnl": _decimal(net_pnl),
                "return_fraction": None,
                "return_unavailable_reason": (
                    "Return requires actual allocated capital; the risk cap is not allocation."
                ),
                "max_drawdown_fraction": None,
                "ranking_available": False,
                "trade_count": trades,
                "win_rate_fraction": _decimal(Decimal(wins) / trades) if trades else None,
            }
        )
        if position is not None and position["quantity"] > 0:
            exposure = position["quantity"] * mark
            position_rows.append(
                {
                    "bot_id": bot_id,
                    "symbol": start.payload["symbol"],
                    "opened_at": _iso(position["opened_at"]),
                    "as_of": _iso(as_of),
                    "age_seconds": int((as_of - position["opened_at"]).total_seconds()),
                    "quantity": _decimal(position["quantity"]),
                    "entry_price": _decimal(
                        position["entry_notional"] / position["entry_quantity"]
                    ),
                    "cost_basis_per_unit": _decimal(position["cost"] / position["quantity"]),
                    "mark_price": _decimal(mark),
                    "exposure": _decimal(exposure),
                    "realized_pnl": _decimal(position["realized"]),
                    "unrealized_pnl": _decimal(exposure - position["cost"]),
                    "exit_progress": {
                        "available": False,
                        "reason": "Exit thresholds are not retained in paper runtime events.",
                    },
                }
            )
        for incident in unresolved[bot_id]:
            severity = "CRITICAL" if incident.payload.get("source") == "RISK_ENGINE" else "WARNING"
            attention.append(
                {
                    "item_id": f"paper-incident-{incident.sequence}",
                    "severity": severity,
                    "title": f"{start.payload['symbol']} paper runtime needs attention",
                    "summary": str(incident.payload["summary"]),
                    "created_at": _iso(incident.occurred_at),
                    "action": "ACKNOWLEDGE" if _acknowledgeable(severity) else None,
                    "acknowledged": False,
                    "source": "PAPER_RUNTIME",
                }
            )
        if stale and not unresolved[bot_id]:
            generation = heartbeat.sequence if heartbeat else 0
            item_id = f"paper-stale-{bot_id}-{generation}"
            attention.append(
                {
                    "item_id": item_id,
                    "severity": "WARNING",
                    "title": f"{start.payload['symbol']} paper feed needs attention",
                    "summary": "A required public market-data component has no fresh heartbeat.",
                    "created_at": _iso(heartbeat.occurred_at if heartbeat else as_of),
                    "action": (
                        None if item_id in projection.acknowledged_item_ids else "ACKNOWLEDGE"
                    ),
                    "acknowledged": item_id in projection.acknowledged_item_ids,
                    "source": "PAPER_RUNTIME",
                }
            )

    signal_rows: list[dict[str, Any]] = []
    for event in projection.events:
        if event.event_type is not PaperEventType.SIGNAL:
            continue
        risk = next(
            (
                item
                for item in projection.events
                if item.event_type is PaperEventType.RISK
                and item.payload.get("signal_id") == event.payload["signal_id"]
            ),
            None,
        )
        max_age = int(starts[event.subject_id].payload["risk_policy"]["max_fill_latency_seconds"])
        state = (
            "BLOCKED"
            if risk is not None and risk.payload.get("decision") == "BLOCK"
            else "EXPIRED"
            if (as_of - event.occurred_at).total_seconds() > max_age
            else "TRIGGERED"
        )
        signal_rows.append(
            {
                "signal_id": event.payload["signal_id"],
                "bot_id": event.subject_id,
                "symbol": event.payload["symbol"],
                "timeframe": event.payload["timeframe"],
                "side": event.payload["side"],
                "state": state,
                "observed_at": _iso(event.occurred_at),
                "rationale": event.payload["rationale"],
                "conditions_met": None,
                "conditions_unavailable_reason": (
                    "Condition-level signal evidence is not retained in paper events."
                ),
            }
        )

    points = _selected_points(projection, as_of, range_name)
    latest = points[-1]
    pnl = (
        latest.equity
        - points[0].equity
        - sum((point.external_cash_flow for point in points[1:]), Decimal(0))
    )
    peak = max(point.equity for point in points)
    portfolio = {
        "available": True,
        "unavailable_reason": None,
        "range": range_name,
        "as_of": _iso(as_of),
        "currency": "USDT",
        "equity": _decimal(latest.equity),
        "cash": _decimal(latest.cash),
        "exposure": _decimal(latest.exposure),
        "pnl": _decimal(pnl),
        "realized_pnl": _decimal(latest.realized_pnl),
        "unrealized_pnl": _decimal(latest.unrealized_pnl),
        "fees": _decimal(latest.fees),
        "drawdown_fraction": _decimal((peak - latest.equity) / peak if peak else Decimal(0)),
        "points": [
            {"observed_at": _iso(point.observed_at), "equity": _decimal(point.equity)}
            for point in points
        ],
    }
    freshness = []
    for bot_id, components in health.items():
        newest = max(
            (event for event in components.values() if event is not None),
            key=lambda event: event.sequence,
            default=None,
        )
        policy = starts[bot_id].payload["risk_policy"]
        stale_after = int(policy["stale_after_seconds"])
        expected_after = int(policy["heartbeat_interval_seconds"])
        feed_incident = any(
            event.payload.get("source")
            in {"BINANCE_BOOK_TICKER", "BINANCE_KLINES", "BINANCE_PUBLIC_DATA"}
            for event in unresolved[bot_id]
        )
        if feed_incident or any(event is None for event in components.values()):
            status = "UNAVAILABLE"
            detail = "A required public market-data component is unavailable."
        elif any(
            (as_of - event.occurred_at).total_seconds() > stale_after
            for event in components.values()
        ):
            status = "STALE"
            detail = "Public market-data heartbeats are stale."
        elif any(
            (as_of - event.occurred_at).total_seconds() > expected_after
            for event in components.values()
        ):
            status = "DELAYED"
            detail = "Public market-data heartbeats are delayed."
        else:
            status = "LIVE"
            detail = "Public prices only; no account, credential, or order connection."
        freshness.append(
            {
                "source": f"BINANCE_PUBLIC_DATA:{bot_id}",
                "status": status,
                "observed_at": _iso(newest.occurred_at if newest else None),
                "detail": detail,
            }
        )
    activity = [
        {
            "sequence": event.sequence,
            "kind": event.event_type.value,
            "subject_id": event.subject_id,
            "occurred_at": _iso(event.occurred_at),
            "summary": str(
                event.payload.get("summary")
                or event.payload.get("kind")
                or event.payload.get("rationale")
                or "Updated"
            ),
            "source": "PAPER_RUNTIME",
        }
        for event in projection.events[-20:]
    ]
    bot_rows.sort(key=lambda row: str(row["bot_id"]))
    return {
        "available": True,
        "reason": None,
        "freshness": freshness,
        "attention": attention,
        "portfolio": portfolio,
        "bots": bot_rows,
        "positions": position_rows,
        "signals": signal_rows[-20:],
        "leaderboard": bot_rows,
        "activity": activity,
    }


def _unavailable_paper(as_of: datetime, range_name: str, reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "freshness": [
            {
                "source": "PAPER_RUNTIME",
                "status": "UNAVAILABLE",
                "observed_at": None,
                "detail": reason,
            }
        ],
        "attention": [],
        "portfolio": {
            "available": False,
            "unavailable_reason": reason,
            "range": range_name,
            "as_of": _iso(as_of),
            "currency": "USDT",
            "equity": None,
            "cash": None,
            "exposure": None,
            "pnl": None,
            "realized_pnl": None,
            "unrealized_pnl": None,
            "fees": None,
            "drawdown_fraction": None,
            "points": [],
        },
        "bots": [],
        "positions": [],
        "signals": [],
        "leaderboard": [],
        "activity": [],
    }


def _internal_findings(root: Path, operations: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for strategy in operations["strategies"]:
        if not strategy["screen_pass"]:
            continue
        published = strategy["last_tested_utc"]
        findings.append(
            {
                "item_id": f"strategy-{strategy['strategy_id']}",
                "kind": "RESEARCH_RESULT",
                "title": f"{strategy['strategy_id']} passed an internal screen",
                "summary": (
                    "This is research evidence only and does not authorize paper or live execution."
                ),
                "source": strategy["source"],
                "published_at": published,
                "affected_subjects": [strategy["strategy_id"]],
                "match_reason": "Internal strategy screen result",
                "url": None,
            }
        )
    reports = root / "artifacts/reports"
    for path in reports.glob("*") if reports.is_dir() else ():
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        relative = path.relative_to(root).as_posix()
        findings.append(
            {
                "item_id": f"report-{hashlib.sha256(relative.encode()).hexdigest()[:16]}",
                "kind": "INTERNAL_REPORT",
                "title": path.stem.replace("_", " ").title(),
                "summary": "A new internal evidence report is available for review.",
                "source": relative,
                "published_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "affected_subjects": ["TRADING_OS"],
                "match_reason": "Internal system or research report",
                "url": None,
            }
        )
    findings.sort(key=lambda item: str(item["published_at"] or ""), reverse=True)
    return findings[:10]


def _decision_is_actionable(item: dict[str, Any]) -> bool:
    """A gated workspace item belongs in the attention feed only if a real choice exists
    beyond leaving it deferred. Deferred-only tasks (e.g. gated S3/S4 work waiting on a human
    gate) are shown in the completion matrix and the Workspace-actions view, not surfaced as
    'needs your attention' — acknowledging them would decide nothing."""
    return any(
        str(option.get("id")) not in {"keep_deferred", "acknowledge_recurring"}
        for option in item.get("options", [])
    )


def _research_attention(status: dict[str, Any], jobs: dict[str, Any]) -> list[dict[str, Any]]:
    attention = [
        {
            "item_id": task["id"],
            "severity": "INFO",
            "title": task["title"],
            "summary": f"{task['initiative']} · {task['status']}",
            "created_at": status["generated_at"],
            "action": "ACKNOWLEDGE",
            "acknowledged": False,
            "source": "PROJECT_STATUS",
        }
        for task in status["open_tasks"][:5]
    ]
    unresolved_decisions = [
        item
        for item in status["workspace_actions"]
        if item["latest_decision"] is None and _decision_is_actionable(item)
    ]
    attention.extend(
        {
            "item_id": item["id"],
            "severity": "INFO",
            "title": item["title"],
            "summary": f"Decide in Operations → Workspace actions · {item['status']}",
            "created_at": status["generated_at"],
            "action": "ACKNOWLEDGE",
            "acknowledged": False,
            "source": "PROJECT_STATUS",
        }
        for item in unresolved_decisions[:5]
    )
    failed_jobs = [job for job in jobs["latest_jobs"] if job["state"] == "FAILED"]
    attention.extend(
        {
            "item_id": job["job_id"],
            "severity": "WARNING",
            "title": "A research job failed",
            "summary": f"{job['type']} needs operator review.",
            "created_at": job["times"]["finished"] or job["times"]["created"],
            "action": "ACKNOWLEDGE",
            "acknowledged": False,
            "source": "RESEARCH_JOBS",
        }
        for job in failed_jobs[:5]
    )
    return attention


def _cockpit_acknowledgements(root: Path) -> frozenset[str]:
    acknowledged: set[str] = set()
    try:
        with confined_audit_handle(root, AUDIT_PATH, create=False) as handle:
            if handle is None:
                return frozenset()
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(record, dict)
                    and record.get("action") == "ACKNOWLEDGE"
                    and record.get("phase", "COMPLETED") == "COMPLETED"
                    and isinstance(record.get("subject_id"), str)
                ):
                    acknowledged.add(record["subject_id"])
    except (OSError, AuditPathError):
        return frozenset()
    return frozenset(acknowledged)


def build_cockpit(
    root: Path | None = None, range_name: str = "24h", *, now: datetime | None = None
) -> dict[str, Any]:
    """Build one honest operating snapshot; this function never activates or creates paper state."""
    root = (root or Path(__file__).resolve().parents[4]).resolve()
    as_of = (now or datetime.now(tz=UTC)).astimezone(UTC)
    _range_start(as_of, range_name)
    status = build_status(root)
    operations = build_operations(root)
    jobs = build_jobs_projection(root)
    try:
        projection = _read_paper_projection(root)
        paper = (
            _unavailable_paper(as_of, range_name, "No strategy is approved for paper simulation.")
            if projection is None
            else _paper_snapshot(projection, as_of, range_name)
        )
    except (OSError, sqlite3.DatabaseError, PaperStoreError, ValueError):
        paper = _unavailable_paper(
            as_of, range_name, "Retained paper state is unavailable or failed validation."
        )

    research_attention = _research_attention(status, jobs)
    acknowledged_items = _cockpit_acknowledgements(root)
    for item in research_attention:
        if item["item_id"] in acknowledged_items and _acknowledgeable(item["severity"]):
            item["acknowledged"] = True
            item["action"] = None
    attention = [*paper["attention"], *research_attention]
    needs_attention = sum(not item["acknowledged"] for item in attention)
    try:
        running_jobs = int(jobs["counts"]["states"]["RUNNING"])
    except (KeyError, TypeError, ValueError):
        running_jobs = sum(job["state"] == "RUNNING" for job in jobs["latest_jobs"])
    working_bots = paused_bots = stale_bots = 0
    if paper["available"]:
        working_bots = sum(bot["phase"] in {"WATCHING", "POSITION_OPEN"} for bot in paper["bots"])
        paused_bots = sum(bot["phase"] == "PAUSED" for bot in paper["bots"])
        stale_bots = sum(bot["phase"] == "STALE" for bot in paper["bots"])
        headline = (
            f"{working_bots} paper bot{' is' if working_bots == 1 else 's are'} working; "
            f"{paused_bots} paused and {stale_bots} stale; "
            f"{len(paper['positions'])} position"
            f"{' is' if len(paper['positions']) == 1 else 's are'} open, and "
            f"{needs_attention} item{' needs' if needs_attention == 1 else 's need'} you."
        )
        mode = "SYNTHETIC_LOCAL_SIMULATOR"
    else:
        headline = (
            f"Research mode is active; paper portfolio data is unavailable, "
            f"{running_jobs} research job{' is' if running_jobs == 1 else 's are'} running, "
            f"and {needs_attention} item{' needs' if needs_attention == 1 else 's need'} you."
        )
        mode = "RESEARCH_ONLY"

    data_at = operations["data_update"]["last_update_utc"]
    data_status = "UNAVAILABLE"
    if isinstance(data_at, str):
        try:
            age = as_of - datetime.fromisoformat(data_at.replace("Z", "+00:00")).astimezone(UTC)
            data_status = (
                "LIVE"
                if age <= timedelta(minutes=15)
                else "DELAYED"
                if age <= timedelta(days=1)
                else "STALE"
            )
        except ValueError:
            data_at = None
    freshness = [
        *paper["freshness"],
        {
            "source": "RESEARCH_JOBS",
            "status": "LIVE" if jobs["availability"] == "AVAILABLE" else "UNAVAILABLE",
            "observed_at": (
                jobs["latest_jobs"][0]["times"]["created"] if jobs["latest_jobs"] else None
            ),
            "detail": f"Local jobs store: {jobs['availability']}.",
        },
        {
            "source": "RESEARCH_DATA",
            "status": data_status,
            "observed_at": data_at,
            "detail": "Governed local dataset refresh status.",
        },
    ]
    job_activity = [
        {
            "sequence": None,
            "kind": "RESEARCH_JOB",
            "subject_id": job["job_id"],
            "occurred_at": job["times"]["finished"] or job["times"]["created"],
            "summary": f"{job['type']} is {job['state'].lower()}.",
            "source": "RESEARCH_JOBS",
        }
        for job in jobs["latest_jobs"][:10]
    ]
    activity = sorted(
        [*paper["activity"], *job_activity],
        key=lambda item: str(item["occurred_at"] or ""),
        reverse=True,
    )[:20]
    news_subjects = {
        str(item["symbol"])
        for item in [*paper["bots"], *paper["positions"]]
        if isinstance(item.get("symbol"), str)
    }
    external_news = build_external_news(root, news_subjects, now=as_of)
    freshness.append(external_news["freshness"])
    return {
        "schema_version": COCKPIT_SCHEMA_VERSION,
        "mode": mode,
        "generated_at": _iso(as_of),
        "range": range_name,
        "available": paper["available"],
        "reason": paper["reason"],
        "capabilities": {
            "execution_authority": "NONE",
            "venue_connection": "NONE",
            "real_money": False,
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "credential_access": "ABSENT",
            "order_endpoint": "ABSENT",
            "actions": sorted(ACTIONS),
        },
        "freshness": freshness,
        "headline": headline,
        "now": {
            "headline": headline,
            "paper_bots": len(paper["bots"]) if paper["available"] else None,
            "paper_bots_working": working_bots if paper["available"] else None,
            "paper_bots_paused": paused_bots if paper["available"] else None,
            "paper_bots_stale": stale_bots if paper["available"] else None,
            "paper_bots_historical": None,
            "paper_bots_historical_reason": (
                "Paper events do not retain a stopped lifecycle state; stale bots are not "
                "silently labeled historical."
            ),
            "open_positions": len(paper["positions"]) if paper["available"] else None,
            "research_jobs_running": running_jobs,
            "attention_items": needs_attention,
        },
        "attention": attention,
        "portfolio": paper["portfolio"],
        "bots": paper["bots"],
        "positions": paper["positions"],
        "signals": paper["signals"],
        "leaderboard": paper["leaderboard"],
        "findings": [*_internal_findings(root, operations), *external_news["items"]],
        "activity": activity,
    }


def _validated_action(payload: dict[str, Any]) -> tuple[str, str, str, str | None]:
    if set(payload) - {"action", "subject_id", "idempotency_key", "reason"}:
        raise CockpitActionError("request contains unsupported fields")
    action = payload.get("action")
    subject_id = payload.get("subject_id")
    idempotency_key = payload.get("idempotency_key")
    reason = payload.get("reason")
    if not isinstance(action, str) or action not in ACTIONS:
        raise CockpitActionError("unknown cockpit action")
    if not isinstance(subject_id, str) or not _IDENTIFIER.fullmatch(subject_id):
        raise CockpitActionError("subject_id must be a bounded identifier")
    if not isinstance(idempotency_key, str) or not _IDENTIFIER.fullmatch(idempotency_key):
        raise CockpitActionError("idempotency_key must be a bounded identifier")
    if reason is not None and (not isinstance(reason, str) or len(reason.strip()) > 500):
        raise CockpitActionError("reason must be text of at most 500 characters")
    return action, subject_id, idempotency_key, reason.strip() if reason else None


def _validate_action_target(
    root: Path, action: str, subject_id: str, at: datetime
) -> dict[str, str | None]:
    if action in {"PAUSE_RESEARCH_SCHEDULE", "RESUME_RESEARCH_SCHEDULE"}:
        jobs = build_jobs_projection(root)
        if jobs["availability"] != "AVAILABLE":
            raise CockpitUnavailableError("research schedule state is unavailable")
        if subject_id not in {item["schedule_id"] for item in jobs["schedules"]}:
            raise CockpitNotFoundError("unknown research schedule")
        return {"target_source": "RESEARCH_SCHEDULE", "target_severity": None}

    projection: PaperStoreProjection | None = None
    paper_error = False
    try:
        projection = _read_paper_projection(root)
    except (OSError, sqlite3.DatabaseError, PaperStoreError):
        paper_error = True

    if action == "ACKNOWLEDGE":
        paper_attention: list[dict[str, Any]] = []
        if projection is not None:
            try:
                paper_attention = _paper_snapshot(projection, at, "all")["attention"]
            except (PaperStoreError, ValueError):
                paper_error = True
        research_attention = _research_attention(build_status(root), build_jobs_projection(root))
        item = next(
            (
                candidate
                for candidate in [*paper_attention, *research_attention]
                if candidate["item_id"] == subject_id
            ),
            None,
        )
        if item is None:
            if paper_error:
                raise CockpitUnavailableError("paper attention state is unavailable")
            raise CockpitNotFoundError("unknown attention item")
        if not _acknowledgeable(item["severity"]):
            raise CockpitActionError(
                "only informational or warning attention items can be acknowledged"
            )
        return {
            "target_source": str(item["source"]),
            "target_severity": str(item["severity"]).strip().upper(),
        }

    if projection is None:
        raise CockpitUnavailableError("paper state is unavailable")
    snapshot = _paper_snapshot(projection, at, "all")
    bot_ids = {item["bot_id"] for item in snapshot["bots"]}
    if subject_id not in bot_ids:
        raise CockpitNotFoundError("unknown paper bot")
    return {"target_source": "PAPER_RUNTIME", "target_severity": None}


def _execute_action(
    root: Path,
    action: str,
    subject_id: str,
    key: str,
    acted_at: datetime,
    target: dict[str, str | None],
) -> None:
    if action in {"PAUSE_RESEARCH_SCHEDULE", "RESUME_RESEARCH_SCHEDULE"}:
        try:
            with JobStore(default_jobs_database(root), root=root) as store:
                store.initialize()
                store.set_schedule_enabled(
                    subject_id,
                    action == "RESUME_RESEARCH_SCHEDULE",
                    now=acted_at,
                )
        except KeyError as error:
            raise CockpitNotFoundError("unknown research schedule") from error
        except (FileNotFoundError, OSError, sqlite3.DatabaseError, RuntimeError) as error:
            raise CockpitUnavailableError("research schedule state is unavailable") from error
        return
    if action == "ACKNOWLEDGE":
        severity = target.get("target_severity")
        source = target.get("target_source")
        if not _acknowledgeable(severity) or source not in {
            "PAPER_RUNTIME",
            "PROJECT_STATUS",
            "RESEARCH_JOBS",
        }:
            raise CockpitUnavailableError("retained acknowledgement target is invalid")
        if source == "PAPER_RUNTIME":
            PaperStore(root=root).acknowledge_attention(
                subject_id,
                actor="local_dashboard_operator",
                idempotency_key=key,
                occurred_at=acted_at,
            )
        return
    PaperStore(root=root).set_entries_paused(
        action == "PAUSE_PAPER_ENTRIES",
        actor="local_dashboard_operator",
        idempotency_key=key,
        occurred_at=acted_at,
    )


def _reconcile_orphan_paper_action(
    root: Path, action: str, subject_id: str, key: str
) -> tuple[datetime, dict[str, str | None]] | None:
    """Recover an action retained by PaperStore before its cockpit audit publication."""
    try:
        projection = _read_paper_projection(root)
    except (OSError, sqlite3.DatabaseError, PaperStoreError) as error:
        raise CockpitUnavailableError("paper action state is unavailable") from error
    if projection is None:
        return None
    retained = next((audit for audit in projection.audits if audit.idempotency_key == key), None)
    if retained is None:
        return None
    expected = {
        "ACKNOWLEDGE": PaperAuditAction.ACKNOWLEDGE,
        "PAUSE_PAPER_ENTRIES": PaperAuditAction.PAUSE_ENTRIES,
        "RESUME_PAPER_ENTRIES": PaperAuditAction.RESUME_ENTRIES,
    }.get(action)
    if (
        expected is None
        or retained.action is not expected
        or retained.actor != "local_dashboard_operator"
        or retained.payload
    ):
        raise CockpitUnavailableError("retained paper action cannot be safely reconciled")
    snapshot = _paper_snapshot(projection, retained.occurred_at, "all")
    if action in {"PAUSE_PAPER_ENTRIES", "RESUME_PAPER_ENTRIES"}:
        if retained.subject_id != "paper-entries" or subject_id not in {
            bot["bot_id"] for bot in snapshot["bots"]
        }:
            raise CockpitUnavailableError("retained paper control subject does not match")
        return retained.occurred_at, {
            "target_source": "PAPER_RUNTIME",
            "target_severity": None,
        }
    if retained.subject_id != subject_id:
        raise CockpitUnavailableError("retained acknowledgement subject does not match")
    severity: str | None = None
    if subject_id.startswith("paper-incident-"):
        try:
            sequence = int(subject_id.removeprefix("paper-incident-"))
        except ValueError as error:
            raise CockpitUnavailableError("retained acknowledgement subject is invalid") from error
        incident = next(
            (
                event
                for event in projection.events
                if event.sequence == sequence and event.event_type is PaperEventType.INCIDENT
            ),
            None,
        )
        if incident is not None:
            severity = "CRITICAL" if incident.payload.get("source") == "RISK_ENGINE" else "WARNING"
    elif any(
        subject_id.startswith(f"paper-stale-{bot_id}-")
        for bot_id in {bot["bot_id"] for bot in snapshot["bots"]}
    ):
        severity = "WARNING"
    if not _acknowledgeable(severity):
        raise CockpitUnavailableError("retained acknowledgement is not safely acknowledgeable")
    return retained.occurred_at, {
        "target_source": "PAPER_RUNTIME",
        "target_severity": severity,
    }


def _append_action_record(handle: TextIO, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def perform_cockpit_action(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one allowlisted local action and retain an idempotent operator audit."""
    action, subject_id, key, reason = _validated_action(payload)
    root = root.resolve()
    try:
        audit = confined_audit_handle(root, AUDIT_PATH, create=True)
    except (OSError, AuditPathError) as error:
        raise CockpitUnavailableError("cockpit action audit is unavailable") from error
    try:
        with audit as handle:
            assert handle is not None
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            matching: list[dict[str, Any]] = []
            for line in handle:
                try:
                    retained = json.loads(line)
                except json.JSONDecodeError as error:
                    raise CockpitUnavailableError("cockpit action audit is malformed") from error
                if not isinstance(retained, dict):
                    raise CockpitUnavailableError("cockpit action audit is malformed")
                if retained.get("idempotency_key") == key:
                    matching.append(retained)
            for retained in matching:
                if (
                    retained.get("action"),
                    retained.get("subject_id"),
                    retained.get("reason"),
                ) != (action, subject_id, reason):
                    raise CockpitUnavailableError("idempotency key conflicts with retained action")
                if retained.get("phase", "COMPLETED") not in {"PREPARED", "COMPLETED"}:
                    raise CockpitUnavailableError("cockpit action audit phase is invalid")
            completed = next(
                (
                    retained
                    for retained in reversed(matching)
                    if retained.get("phase", "COMPLETED") == "COMPLETED"
                ),
                None,
            )
            if completed is not None:
                return {
                    "schema_version": 1,
                    "status": "recorded",
                    "idempotent": True,
                    "recorded": completed,
                }
            prepared = next(
                (retained for retained in matching if retained.get("phase") == "PREPARED"),
                None,
            )
            reconciled = False
            if prepared is None:
                orphan = _reconcile_orphan_paper_action(root, action, subject_id, key)
                if orphan is None:
                    acted_at = datetime.now(tz=UTC)
                    target = _validate_action_target(root, action, subject_id, acted_at)
                else:
                    acted_at, target = orphan
                    reconciled = True
                prepared = {
                    "schema_version": 1,
                    "phase": "PREPARED",
                    "acted_at": acted_at.isoformat(),
                    "source": "local_dashboard_operator",
                    "action": action,
                    "subject_id": subject_id,
                    "idempotency_key": key,
                    "reason": reason,
                    "execution_authority": "NONE",
                    **target,
                }
                _append_action_record(handle, prepared)
            else:
                try:
                    acted_at = datetime.fromisoformat(str(prepared["acted_at"]))
                except (KeyError, ValueError) as error:
                    raise CockpitUnavailableError(
                        "prepared cockpit action timestamp is invalid"
                    ) from error
                if acted_at.tzinfo is None or acted_at.utcoffset() != timedelta(0):
                    raise CockpitUnavailableError("prepared cockpit action timestamp is not UTC")
                target = {
                    "target_source": prepared.get("target_source"),
                    "target_severity": prepared.get("target_severity"),
                }
                if any(
                    value is not None and not isinstance(value, str) for value in target.values()
                ):
                    raise CockpitUnavailableError("prepared cockpit action target is invalid")
            _execute_action(root, action, subject_id, key, acted_at, target)
            completed = {
                **prepared,
                "phase": "COMPLETED",
                "completed_at": datetime.now(tz=UTC).isoformat(),
            }
            _append_action_record(handle, completed)
            return {
                "schema_version": 1,
                "status": "recorded",
                "idempotent": bool(matching) or reconciled,
                "recorded": completed,
            }
    except CockpitActionError:
        raise
    except (OSError, AuditPathError) as error:
        raise CockpitUnavailableError("cockpit action audit is unavailable") from error
