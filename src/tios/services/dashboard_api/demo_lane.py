"""Read-only projection and bounded operator controls for the D-104/D-105 ETH demo lane.

The dashboard never touches credentials, never signs a request, and never places an order.
It can observe the lane's own artifacts, and it can start/stop the separate lane process,
which enforces every safety rail itself (demo-host lock, caps, quantization, kill switch).

Governed by D-106: this is the second audited write surface on the local loopback dashboard.
Every ACTION is allowlisted to a fixed internal literal that selects a hardcoded argv — no
free-form input ever reaches a spawned command. The lane starts (START/START_ACTIVITY/START_MULTI)
and RUN_ONCE/STOP share the lane's advisory `lane.lock`; the research search (START_RESEARCH) is
NOT a lane, so it is guarded by a separate PID-liveness research lock instead.

It also serves read-only VIEW endpoints (demo trades, demo status, research findings) that call the
deterministic report scripts as library functions — no subprocess, no command execution — and
fail closed to a safe "unavailable" shape on any defect.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import signal
import subprocess  # noqa: S404 (fixed argv, no shell, no user input — see _spawn)
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tios.evidence.demo_decision_evidence_v2 import public_stage_b_projection
from tios.services.dashboard_api.audit import AuditPathError, confined_audit_handle

LANE_DIR = Path("artifacts/trading_domain/demo_lane")
KILL_SWITCH = LANE_DIR / "KILL_SWITCH"
ORDERS_LEDGER = LANE_DIR / "orders.jsonl"
HEARTBEAT = LANE_DIR / "heartbeat.json"
LANE_STATE = LANE_DIR / "lane_state.json"
LANE_LOCK = LANE_DIR / "lane.lock"
LANE_LOG = LANE_DIR / "lane.log"
LANE_SCRIPT = Path("scripts/demo_eth_lane.py")
AUDIT_PATH = Path("artifacts/human_decisions/demo_lane_actions.jsonl")
DIVERGENCE_REPORT = LANE_DIR / "DIVERGENCE_REPORT.json"

# Research search (START_RESEARCH): offline, no venue, no orders, authority NONE. It is NOT a lane,
# so it does not use lane.lock; a separate PID-liveness guard (RESEARCH_LOCK) stops two concurrent
# searches from clobbering the same output JSON.
RESEARCH_SCRIPT = Path("scripts/run_universe_search.py")
RESEARCH_LOCK = Path("artifacts/research_lab/universe_search/.research_run.lock")
RESEARCH_LOG = Path("artifacts/research_lab/universe_search/research_run.log")
RESEARCH_REPORT = Path(
    "artifacts/research_lab/universe_search/UNIVERSE_SEARCH_TRAIN_SELECT_V2_2026_07_13.json"
)

BASE_COIN = "ETH"
QUOTE_COIN = "USDT"

# The multi-coin demo lane runs the SAME already-screened volume-breakout rule on each of these,
# independently. Mirrors scripts/demo_eth_lane.py DEMO_COINS; the operator view walks them in this
# exact order. ETHUSDT is the default lane (heartbeat.json / lane_state.json); every other coin has
# per-symbol heartbeat_<SYMBOL>.json / lane_state_<SYMBOL>.json.
DEFAULT_SYMBOL = "ETHUSDT"
DEMO_COINS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "LTCUSDT",
)
DEMO_DISASTER_STOP_PCT = 15.0  # fixed -15% hard stop from entry (measurement-mode tail insurance)

# The confluence activity lane scores this ~40-coin universe (mirrors scripts/demo_activity_lane.py
# ACTIVITY_UNIVERSE — keep in sync) into one confidence per coin, writing
# heartbeat_<SYMBOL>_activity.json / lane_state_<SYMBOL>_activity.json and tagging its orders
# ACTIVITY_STRATEGY so a shared symbol (BTCUSDT/ETHUSDT are in both universes) never
# cross-contaminates the breakout `coins` view.
ACTIVITY_STRATEGY = "ACTIVITY-CONFLUENCE"
ACTIVITY_COINS = (
    "AAVEUSDT", "ADAUSDT", "ALGOUSDT", "APTUSDT", "ARBUSDT", "ATOMUSDT", "AVAXUSDT", "AXSUSDT",
    "BCHUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT", "EGLDUSDT", "EOSUSDT", "ETCUSDT",
    "ETHUSDT", "FILUSDT", "FLOWUSDT", "FTMUSDT", "GRTUSDT", "INJUSDT", "LINKUSDT", "LTCUSDT",
    "MANAUSDT", "MATICUSDT", "NEARUSDT", "OPUSDT", "RUNEUSDT", "SANDUSDT", "SEIUSDT", "SOLUSDT",
    "SUIUSDT", "THETAUSDT", "TIAUSDT", "TRXUSDT", "UNIUSDT", "XLMUSDT", "XRPUSDT", "XTZUSDT",
)  # fmt: skip

ACTIONS = frozenset(
    {"START", "START_ACTIVITY", "START_MULTI", "START_RESEARCH", "STOP", "RUN_ONCE"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")
# Fixed confluence cadence for the START_ACTIVITY button — a hardcoded constant, never from input.
ACTIVITY_INTERVAL = "5m"
RUN_ONCE_TIMEOUT_SECONDS = 90
ORDER_HISTORY_LIMIT = 25
# The lane's documented loop is hourly. A small grace covers scheduling/network delay;
# older evidence is retained but cannot be presented as current protection.
HEARTBEAT_FRESHNESS_MAX_AGE = timedelta(minutes=75)
BOUNDARY_ABS_TOLERANCE_USD = 0.000001
EXPOSURE_REL_TOLERANCE = 0.000001
EXPOSURE_ABS_TOLERANCE = 0.00000001
MIN_STOP_QTY_COVERAGE = 0.999


class DemoLaneActionError(ValueError):
    """Rejected demo-lane action. `status_code` is the HTTP status the server should send."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _running(root: Path) -> tuple[bool, int | None, str | None]:
    """Is a lane process alive? Uses the lane's own advisory lock, so PID reuse cannot fool it.

    Acquiring the lock means nobody holds it (lane is down); we release immediately.
    """
    lock_path = root / LANE_LOCK
    if not lock_path.is_file():
        return False, None, None
    try:
        handle = lock_path.open("a+", encoding="utf-8")
    except OSError:
        return False, None, None
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = _read_json(lock_path)
            pid = holder.get("pid")
            return True, pid if isinstance(pid, int) else None, holder.get("started_at")
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False, None, None
    finally:
        handle.close()


def _orders(root: Path) -> list[dict[str, Any]]:
    try:
        lines = (root / ORDERS_LEDGER).read_text().splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


_STAGE_B_STATUSES = frozenset({"NOT_ACTIVATED", "READY", "ENTRY_BLOCK", "UNAVAILABLE"})
_AGGREGATE_FIELDS = (
    "closed_count",
    "positive_count",
    "negative_count",
    "flat_count",
    "entry_exec_value_total",
    "exit_exec_value_total",
    "gross_quote_total",
    "quote_fee_total",
    "base_fee_total",
    "net_quote_total",
)


def _unavailable_stage_b() -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "cohort_size": 30, "series": []}


def _reshape_cohort(cohort: Any) -> dict[str, Any]:
    aggregate = cohort["aggregate"]
    return {
        "cohort_number": cohort["cohort_number"],
        "assigned_count": cohort["assigned_count"],
        "eligible_closed_count": cohort["eligible_closed_count"],
        "ineligible_count": cohort["ineligible_count"],
        "open_count": cohort["open_count"],
        "readiness": cohort["readiness"],
        # aggregate is null until an exact 30-assignment cohort is complete; when present it
        # is reprojected to exactly the approved totals so nothing upstream can leak.
        "aggregate": (
            None if aggregate is None else {key: aggregate[key] for key in _AGGREGATE_FIELDS}
        ),
    }


def _project_stage_b(root: Path) -> dict[str, Any]:
    """Reproject the fixed, fail-closed Stage B public projection through a strict allowlist.

    Any parse/validation surprise (missing key, wrong type, bad status) fails closed to
    UNAVAILABLE with no series, so no private field can ever reach the API boundary.
    """
    try:
        raw = public_stage_b_projection(root)
        if not isinstance(raw, dict) or raw.get("status") not in _STAGE_B_STATUSES:
            return _unavailable_stage_b()
        series_in = raw["series"]
        if not isinstance(series_in, list):
            return _unavailable_stage_b()
        series_out = [
            {
                "series_number": series["series_number"],
                "cohorts": [_reshape_cohort(cohort) for cohort in series["cohorts"]],
            }
            for series in series_in
        ]
        return {"status": raw["status"], "cohort_size": 30, "series": series_out}
    except Exception:  # noqa: BLE001 — fail closed on any projection defect, never leak
        return _unavailable_stage_b()


def _operational_snapshot(root: Path) -> tuple[str, bool]:
    """Derive only operational status and kill-switch from the lane's own liveness signals."""
    try:
        running, _pid, _started = _running(root)
        kill_switch = (root / KILL_SWITCH).exists()
    except OSError:
        return "UNAVAILABLE", False
    if running:
        return ("STOPPING" if kill_switch else "RUNNING"), kill_switch
    return ("STOPPED" if kill_switch else "IDLE"), kill_switch


def _coin_heartbeat_path(root: Path, symbol: str) -> Path:
    return root / (HEARTBEAT if symbol == DEFAULT_SYMBOL else LANE_DIR / f"heartbeat_{symbol}.json")


def _coin_state_path(root: Path, symbol: str) -> Path:
    return root / (
        LANE_STATE if symbol == DEFAULT_SYMBOL else LANE_DIR / f"lane_state_{symbol}.json"
    )


def _coin_trades(
    orders_for_coin: list[dict[str, Any]], base_coin: str
) -> tuple[list[float], float, dict[str, Any] | None]:
    """Fold this coin's fills into closed-trip realised P&Ls, total fees, and the open entry.

    A buy opens an entry; the next sell closes it (received minus what the entry cost). A trailing
    unmatched buy is the currently open position. Deterministic: order follows the ledger.
    """
    closed_pnls: list[float] = []
    fees = 0.0
    entry: dict[str, Any] | None = None
    for order in orders_for_coin:
        money = _order_money(order, base_coin)
        fees += money["fee_usd"]
        if order.get("side") == "Buy":
            entry = {
                "spent_usd": money["usd_spent"],
                "size_base": money["base_delta"],
                "opened_at": order.get("recorded_at"),
            }
        elif entry is not None:
            closed_pnls.append(money["usd_received"] - entry["spent_usd"])
            entry = None
    return closed_pnls, round(fees, 4), entry


def _position_projection(
    lane_base: float,
    mark: float,
    entry: float,
    is_long: bool,
    open_entry: dict[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Entry-based live position + P&L, shared by the breakout `coins` and confluence `activity`
    views. Both are fed a run_cycle heartbeat/state, so the position math is identical."""
    cost = lane_base * entry if (is_long and entry > 0) else None
    value = lane_base * mark if (is_long and mark > 0) else None
    unrealised = value - cost if (value is not None and cost is not None) else None
    spent_usd = (
        open_entry["spent_usd"]
        if open_entry is not None
        else (round(cost, 4) if cost is not None else None)
    )
    opened_at = open_entry["opened_at"] if open_entry is not None else None
    opened = _parse_ts(opened_at)
    time_in_trade_seconds = (
        round((now - opened.astimezone(UTC)).total_seconds(), 1)
        if opened is not None and opened.tzinfo is not None
        else None
    )
    return {
        "side": "LONG" if is_long else "FLAT",
        "base_qty": round(lane_base, 8) if is_long else 0.0,
        "entry_price_usd": round(entry, 2) if (is_long and entry > 0) else None,
        "mark_price_usd": round(mark, 2) if mark > 0 else None,
        "spent_usd": spent_usd,
        "value_usd": round(value, 4) if value is not None else None,
        "unrealised_pnl_usd": round(unrealised, 4) if unrealised is not None else None,
        "unrealised_pnl_pct": (
            round(unrealised / cost * 100, 2) if unrealised is not None and cost else None
        ),
        "opened_at": opened_at,
        "time_in_trade_seconds": time_in_trade_seconds,
    }


def _protection_projection(
    heartbeat: dict[str, Any], state: dict[str, Any], is_long: bool, entry: float, mark: float
) -> dict[str, Any]:
    """-15% disaster floor + any venue-resting/trailing stop. Shared by the coins/activity views."""
    resting = state.get("resting_stop") or heartbeat.get("resting_stop")
    resting = resting if isinstance(resting, dict) else {}
    resting_trigger = _number(
        resting.get("trigger_price") or resting.get("venue_trigger_price_usd")
    )
    disaster = _number(heartbeat.get("disaster_stop_price"))
    if disaster <= 0 and is_long and entry > 0:
        disaster = entry * (1 - DEMO_DISASTER_STOP_PCT / 100)
    stop_level = resting_trigger if resting_trigger > 0 else disaster
    return {
        "disaster_stop_price_usd": round(disaster, 2) if disaster > 0 else None,
        "disaster_stop_pct": DEMO_DISASTER_STOP_PCT,
        "venue_resting_stop_trigger_usd": round(resting_trigger, 2)
        if resting_trigger > 0
        else None,
        "venue_resting_stop_state": resting.get("state") if resting else None,
        "distance_to_stop_pct": (
            round((mark - stop_level) / mark * 100, 2) if mark > 0 and stop_level > 0 else None
        ),
    }


def _coin_projection(
    root: Path, symbol: str, orders: list[dict[str, Any]], kill_switch: bool, now: datetime
) -> dict[str, Any]:
    """Rich, live, per-coin operator view. Missing/malformed files degrade to idle — never crash.

    Field definitions mirror scripts/report_demo_status.py so the dashboard matches that report:
    position side/live unrealised, protection (-15% disaster + venue-resting stop), what the coin
    is watching (bands, distance-to-entry, volume-vs-gate), signals, and realised trade history.
    """
    base_coin = symbol.removesuffix(QUOTE_COIN)
    heartbeat = _read_json(_coin_heartbeat_path(root, symbol))
    state = _read_json(_coin_state_path(root, symbol))
    orders_for_coin = [o for o in orders if o.get("symbol") == symbol]
    data_available = bool(heartbeat) or bool(state) or bool(orders_for_coin)

    lane_base = _number(state.get("lane_base", heartbeat.get("lane_base", "0")))
    mark = _number(heartbeat.get("mark_price"))
    entry = _number(heartbeat.get("entry_price") or state.get("entry_price"))
    is_long = lane_base > 0

    closed_pnls, fees, open_entry = _coin_trades(orders_for_coin, base_coin)

    position = _position_projection(lane_base, mark, entry, is_long, open_entry, now)
    protection = _protection_projection(heartbeat, state, is_long, entry, mark)

    # --- what it's watching / how close to acting ---
    raw_levels = heartbeat.get("rule_levels")
    levels = raw_levels if isinstance(raw_levels, dict) else {}
    warming = bool(levels.get("warming_up")) or not levels
    upper = _number(levels.get("donchian_upper"))
    lower = _number(levels.get("donchian_lower"))
    close = _number(levels.get("close"))
    volume_base = _number(levels.get("volume_base"))
    volume_threshold = _number(levels.get("volume_threshold"))
    watching = {
        "warming_up": warming,
        "donchian_upper_usd": round(upper, 2) if upper else None,
        "donchian_lower_usd": round(lower, 2) if lower else None,
        "close_usd": round(close, 2) if close else None,
        "distance_to_entry_pct": (
            round((upper - close) / upper * 100, 2) if upper > 0 and close > 0 else None
        ),
        "exit_trigger_usd": round(lower, 2) if lower else None,
        "volume_base": round(volume_base, 4) if volume_base else None,
        "volume_threshold": round(volume_threshold, 4) if volume_threshold else None,
        "volume_pct_of_gate": (
            round(volume_base / volume_threshold * 100, 1) if volume_threshold > 0 else None
        ),
        "entry_rule": "close > donchian_upper(40) AND volume > 1.5x average(40)",
        "exit_rule": "close < donchian_lower(40)",
        "latest_closed_bar": heartbeat.get("latest_closed_bar"),
    }

    freshness = _heartbeat_freshness(heartbeat, now)
    closed_count = len(closed_pnls)
    wins = sum(1 for p in closed_pnls if p > 0)
    losses = sum(1 for p in closed_pnls if p < 0)
    return {
        "symbol": symbol,
        "base_coin": base_coin,
        "data_available": data_available,
        "kill_switch": kill_switch,
        "heartbeat_age_seconds": freshness["age_seconds"],
        "heartbeat_fresh": freshness["fresh"],
        "signals": {
            "in_window": heartbeat.get("signals_in_window"),
            "fresh": heartbeat.get("fresh_signals"),
        },
        "position": position,
        "protection": protection,
        "watching": watching,
        "trade_history": {
            "closed_count": closed_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / closed_count * 100, 1) if closed_count else None,
            "realised_pnl_usd": round(sum(closed_pnls), 4),
            "fees_usd": fees,
        },
    }


def _portfolio_rollup(coins: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-coin totals: open/flat counts, realised + unrealised P&L, exposure, fees, win rate."""
    in_position = 0
    open_exposure = 0.0
    unrealised = 0.0
    realised = 0.0
    fees = 0.0
    closed = 0
    wins = 0
    for coin in coins:
        pos = coin["position"]
        if pos["side"] == "LONG":
            in_position += 1
            exposure = pos["spent_usd"]
            if exposure is None and pos["base_qty"] and pos["entry_price_usd"]:
                exposure = pos["base_qty"] * pos["entry_price_usd"]
            open_exposure += exposure or 0.0
            unrealised += pos["unrealised_pnl_usd"] or 0.0
        hist = coin["trade_history"]
        realised += hist["realised_pnl_usd"]
        fees += hist["fees_usd"]
        closed += hist["closed_count"]
        wins += hist["wins"]
    return {
        "coins_total": len(coins),
        "coins_in_position": in_position,
        "coins_flat": len(coins) - in_position,
        "open_exposure_usd": round(open_exposure, 4),
        "unrealised_pnl_usd": round(unrealised, 4),
        "realised_pnl_usd": round(realised, 4),
        "total_fees_usd": round(fees, 4),
        "closed_trades": closed,
        "wins": wins,
        "win_rate_pct": round(wins / closed * 100, 1) if closed else None,
    }


def _confidence_value(raw: Any) -> float | None:
    """Confluence confidence in [-1, +1] as a float, or None if missing/malformed. Unlike `_number`
    this keeps None distinct from a real 0.0 score so no-data coins sink to the bottom of the
    sort."""
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _contributors(raw: Any) -> list[dict[str, str]]:
    """Project a bullish/bearish contributor list to just (strategy, timeframe) string pairs."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and "strategy" in item and "timeframe" in item:
            out.append({"strategy": str(item["strategy"]), "timeframe": str(item["timeframe"])})
    return out


def _activity_projection(
    root: Path, symbol: str, orders: list[dict[str, Any]], kill_switch: bool, now: datetime
) -> dict[str, Any]:
    """Per-coin confluence projection: the confidence score, the agreeing strategies/timeframes,
    and the same position/protection blocks as `_coin_projection`. Reads
    heartbeat_<SYMBOL>_activity.json / lane_state_<SYMBOL>_activity.json; missing/malformed files
    degrade to idle no-data, never crash (build_demo_lane still wraps each call in a per-coin
    try/except). Orders are filtered to the ACTIVITY_STRATEGY tag so a symbol shared with the
    breakout `coins` lane never bleeds in."""
    base_coin = symbol.removesuffix(QUOTE_COIN)
    heartbeat = _read_json(root / LANE_DIR / f"heartbeat_{symbol}_activity.json")
    state = _read_json(root / LANE_DIR / f"lane_state_{symbol}_activity.json")
    orders_for_coin = [
        o for o in orders if o.get("symbol") == symbol and o.get("strategy") == ACTIVITY_STRATEGY
    ]
    data_available = bool(heartbeat) or bool(state) or bool(orders_for_coin)

    confluence = heartbeat.get("confluence")
    confluence = confluence if isinstance(confluence, dict) else {}
    decision = confluence.get("decision")

    lane_base = _number(state.get("lane_base", heartbeat.get("lane_base", "0")))
    mark = _number(heartbeat.get("mark_price"))
    entry = _number(heartbeat.get("entry_price") or state.get("entry_price"))
    is_long = lane_base > 0
    _closed, _fees, open_entry = _coin_trades(orders_for_coin, base_coin)
    freshness = _heartbeat_freshness(heartbeat, now)
    return {
        "symbol": symbol,
        "base_coin": base_coin,
        "data_available": data_available,
        "kill_switch": kill_switch,
        "confidence_score": _confidence_value(confluence.get("confidence")),
        "decision": decision if isinstance(decision, str) else None,
        "bullish": _contributors(confluence.get("bullish")),
        "bearish": _contributors(confluence.get("bearish")),
        "position": _position_projection(lane_base, mark, entry, is_long, open_entry, now),
        "protection": _protection_projection(heartbeat, state, is_long, entry, mark),
        "heartbeat_age_seconds": freshness["age_seconds"],
        "heartbeat_fresh": freshness["fresh"],
    }


def _activity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll-up over the scored confluence coins: how many scored, how many long, and the top/mean
    confidence (None until at least one coin reports a score)."""
    scores = [r["confidence_score"] for r in rows if r["confidence_score"] is not None]
    longs = sum(1 for r in rows if r["position"]["side"] == "LONG")
    return {
        "coins_scored": len(scores),
        "coins_long": longs,
        "highest_confidence": max(scores) if scores else None,
        "average_confidence": round(sum(scores) / len(scores), 4) if scores else None,
    }


def build_demo_lane(root: Path | None = None) -> dict[str, Any]:
    """Rich, live, multi-coin operator projection plus the fixed aggregate-only Stage B field.

    The top-level safety envelope (authority NONE, real_money False, UNVALIDATED, no promotion,
    no auto-tune) and the `stage_b` field stay exactly as the aggregate-only projection they were:
    `stage_b` is redacted and never carries per-episode rows. The breakout operator view lives in
    `coins` (one rich section per DEMO_COINS entry, in order) with a `portfolio` roll-up; the
    confluence activity lane's per-coin confidence lives in `activity` (ACTIVITY_COINS, sorted
    strongest-first) with an `activity_summary`. Read-only; a missing or malformed per-coin file
    degrades that coin to idle, never fails the response.
    """
    root = (root or Path(__file__).resolve().parents[4]).resolve()
    operational_status, kill_switch = _operational_snapshot(root)
    now = datetime.now(tz=UTC)
    orders = _orders(root)
    coins: list[dict[str, Any]] = []
    for symbol in DEMO_COINS:
        try:
            coins.append(_coin_projection(root, symbol, orders, kill_switch, now))
        except Exception:  # noqa: BLE001 — one bad coin never fails the whole operator view
            coins.append(
                {
                    "symbol": symbol,
                    "base_coin": symbol.removesuffix(QUOTE_COIN),
                    "data_available": False,
                    "kill_switch": kill_switch,
                    "heartbeat_age_seconds": None,
                    "heartbeat_fresh": False,
                    "signals": {"in_window": None, "fresh": None},
                    "position": {
                        "side": "FLAT",
                        "base_qty": 0.0,
                        "entry_price_usd": None,
                        "mark_price_usd": None,
                        "spent_usd": None,
                        "value_usd": None,
                        "unrealised_pnl_usd": None,
                        "unrealised_pnl_pct": None,
                        "opened_at": None,
                        "time_in_trade_seconds": None,
                    },
                    "protection": {
                        "disaster_stop_price_usd": None,
                        "disaster_stop_pct": DEMO_DISASTER_STOP_PCT,
                        "venue_resting_stop_trigger_usd": None,
                        "venue_resting_stop_state": None,
                        "distance_to_stop_pct": None,
                    },
                    "watching": {
                        "warming_up": True,
                        "donchian_upper_usd": None,
                        "donchian_lower_usd": None,
                        "close_usd": None,
                        "distance_to_entry_pct": None,
                        "exit_trigger_usd": None,
                        "volume_base": None,
                        "volume_threshold": None,
                        "volume_pct_of_gate": None,
                        "entry_rule": "close > donchian_upper(40) AND volume > 1.5x average(40)",
                        "exit_rule": "close < donchian_lower(40)",
                        "latest_closed_bar": None,
                    },
                    "trade_history": {
                        "closed_count": 0,
                        "wins": 0,
                        "losses": 0,
                        "win_rate_pct": None,
                        "realised_pnl_usd": 0.0,
                        "fees_usd": 0.0,
                    },
                }
            )

    # Confluence activity view: parallel to `coins`, read-only, strongest confidence first. One bad
    # coin degrades to idle no-data (helpers already return safe defaults on empty inputs) and never
    # fails the response.
    activity: list[dict[str, Any]] = []
    for symbol in ACTIVITY_COINS:
        try:
            activity.append(_activity_projection(root, symbol, orders, kill_switch, now))
        except Exception:  # noqa: BLE001 — one bad coin never fails the whole activity view
            activity.append(
                {
                    "symbol": symbol,
                    "base_coin": symbol.removesuffix(QUOTE_COIN),
                    "data_available": False,
                    "kill_switch": kill_switch,
                    "confidence_score": None,
                    "decision": None,
                    "bullish": [],
                    "bearish": [],
                    "position": _position_projection(0.0, 0.0, 0.0, False, None, now),
                    "protection": _protection_projection({}, {}, False, 0.0, 0.0),
                    "heartbeat_age_seconds": None,
                    "heartbeat_fresh": False,
                }
            )
    # Strongest setups on top; no-data coins (confidence None) sink to the bottom.
    activity.sort(
        key=lambda row: (
            row["confidence_score"] if row["confidence_score"] is not None else float("-inf")
        ),
        reverse=True,
    )

    return {
        # schema_version 1 to match every other GET endpoint and the client's fetchJson gate
        # (which rejects anything != 1); the demo-lane action POST body keeps its own version.
        "schema_version": 1,
        "operational_status": operational_status,
        "kill_switch": kill_switch,
        "environment": "VENUE_DEMO",
        "real_money": False,
        "execution_authority": "NONE",
        "validation_state": "UNVALIDATED",
        "promotion_eligible": False,
        "auto_tune": False,
        "coins": coins,
        "portfolio": _portfolio_rollup(coins),
        "activity": activity,
        "activity_summary": _activity_summary(activity),
        "stage_b": _project_stage_b(root),
    }


# --- read-only VIEW endpoints -------------------------------------------------------------------
# These render the deterministic report scripts as LIBRARY CALLS (import + call the pure function),
# never a subprocess. Each returns schema_version 1 (the client fetchJson gate requires === 1) and
# fails closed to a safe {available: False, report: None} shape on any defect — never a 500, never a
# leaked secret/pid/path. The report scripts live at the repo root (a namespace `scripts` package),
# which is independent of the `root` DATA directory passed in (tmp in tests, repo root in prod).


def _report_module(name: str) -> Any:
    """Import a `scripts.<name>` report module, ensuring the repo root is importable. Returns Any so
    the dynamic import never drags the scripts into this module's static type surface."""
    import importlib

    repo_root = str(Path(__file__).resolve().parents[4])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module(f"scripts.{name}")


def _report_view(root: Path | None, name: str, build: Any) -> dict[str, Any]:
    """Shared fail-closed wrapper: call one report module's pure function and wrap it with
    schema_version 1. Any error (missing/malformed source, import defect) degrades to a safe
    unavailable shape."""
    resolved = (root or Path(__file__).resolve().parents[4]).resolve()
    try:
        module = _report_module(name)
        return {"schema_version": 1, "available": True, "report": build(module, resolved)}
    except Exception:  # noqa: BLE001 — a report defect must never crash the read-only server
        return {"schema_version": 1, "available": False, "report": None}


def build_demo_trades_view(root: Path | None = None) -> dict[str, Any]:
    """Read-only per-trade P&L over the demo order ledger (report_demo_trades.build_report)."""
    return _report_view(root, "report_demo_trades", lambda m, r: m.build_report(r / ORDERS_LEDGER))


def build_demo_status_view(root: Path | None = None) -> dict[str, Any]:
    """Read-only operational status of the demo lane (report_demo_status.build_status)."""
    return _report_view(
        root,
        "report_demo_status",
        lambda m, r: m.build_status(r / HEARTBEAT, r / LANE_STATE, r / ORDERS_LEDGER),
    )


def build_research_findings_view(root: Path | None = None) -> dict[str, Any]:
    """Read-only honest research-findings summary (report_research_findings.build_report). The
    honest framing — LEADS not edges, multiple-testing + cross-coin-correlation confounders,
    UNVALIDATED — is carried through verbatim from the report's own fields; nothing is stripped."""
    return _report_view(
        root, "report_research_findings", lambda m, r: m.build_report(r / RESEARCH_REPORT)
    )


# ponytail: the legacy fill/pnl/stop helpers below are no longer in the API projection but are
# retained because out-of-scope src/tios/ops/demo_readiness.py imports _order_money and
# _operational_disaster_stop; delete this cluster only alongside that consumer.
def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _positive_number(value: Any) -> float | None:
    """Normalize a required positive numeric field without turning bad data into zero."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _stop_fields(raw: Any) -> dict[str, Any]:
    stop = raw if isinstance(raw, dict) else {}
    stop_state = stop.get("state") if isinstance(stop.get("state"), str) else None
    order_id = stop.get("order_id")
    order_id = order_id.strip() if isinstance(order_id, str) and order_id.strip() else None
    risk_fraction = _positive_number(stop.get("risk_fraction"))
    if risk_fraction is not None and risk_fraction >= 1:
        risk_fraction = None
    return {
        "state": stop_state,
        "order_id": order_id,
        "local_boundary_price_usd": _positive_number(stop.get("risk_boundary_price")),
        "venue_trigger_price_usd": _positive_number(stop.get("trigger_price")),
        "base_qty": _positive_number(stop.get("base_qty")),
        "position_base_qty": _positive_number(stop.get("position_base_qty")),
        "risk_fraction": risk_fraction,
        "price_tick_usd": _positive_number(stop.get("price_tick")),
    }


def _heartbeat_freshness(heartbeat: dict[str, Any], now: datetime) -> dict[str, Any]:
    reported_at = heartbeat.get("at")
    try:
        parsed = datetime.fromisoformat(str(reported_at))
        if parsed.tzinfo is None:
            raise ValueError("heartbeat timestamp has no timezone")
        age = (now - parsed.astimezone(UTC)).total_seconds()
    except (OverflowError, TypeError, ValueError):
        return {
            "heartbeat_at": reported_at if isinstance(reported_at, str) else None,
            "age_seconds": None,
            "max_age_seconds": int(HEARTBEAT_FRESHNESS_MAX_AGE.total_seconds()),
            "fresh": False,
        }
    return {
        "heartbeat_at": parsed.astimezone(UTC).isoformat(),
        "age_seconds": round(age, 3),
        "max_age_seconds": int(HEARTBEAT_FRESHNESS_MAX_AGE.total_seconds()),
        "fresh": 0 <= age <= HEARTBEAT_FRESHNESS_MAX_AGE.total_seconds(),
    }


def _same_exposure(left: float | None, right: float | None) -> bool:
    return (
        left is not None
        and right is not None
        and math.isfinite(left)
        and math.isfinite(right)
        and left > 0
        and right > 0
        and math.isclose(
            left,
            right,
            rel_tol=EXPOSURE_REL_TOLERANCE,
            abs_tol=EXPOSURE_ABS_TOLERANCE,
        )
    )


def _stops_agree(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_boundary = left["local_boundary_price_usd"]
    right_boundary = right["local_boundary_price_usd"]
    left_trigger = left["venue_trigger_price_usd"]
    right_trigger = right["venue_trigger_price_usd"]
    return (
        left["state"] == right["state"]
        and left["order_id"] == right["order_id"]
        and left_boundary is not None
        and right_boundary is not None
        and math.isclose(
            left_boundary,
            right_boundary,
            rel_tol=0.0,
            abs_tol=BOUNDARY_ABS_TOLERANCE_USD,
        )
        and left_trigger is not None
        and right_trigger is not None
        and math.isclose(
            left_trigger,
            right_trigger,
            rel_tol=0.0,
            abs_tol=BOUNDARY_ABS_TOLERANCE_USD,
        )
        and _same_exposure(left["base_qty"], right["base_qty"])
        and _same_exposure(left["position_base_qty"], right["position_base_qty"])
        and _same_exposure(left["risk_fraction"], right["risk_fraction"])
        and _same_exposure(left["price_tick_usd"], right["price_tick_usd"])
    )


def _operational_disaster_stop(
    state: dict[str, Any],
    heartbeat: dict[str, Any],
    *,
    running: bool,
    ledger_base: float,
    now: datetime,
) -> dict[str, Any]:
    """Separate last-reported stop evidence from currently corroborated protection.

    State is the preferred report, but `active` requires a running lane and a fresh
    heartbeat to agree with state, ledger exposure, sizing, entry boundary, tick, and
    mark. This does not claim venue truth; it is fresh lane reconciliation evidence.
    """
    state_has_stop = "resting_stop" in state
    if state_has_stop:
        selected = _stop_fields(state.get("resting_stop"))
        source = "lane_state"
    else:
        selected = _stop_fields(heartbeat.get("resting_stop"))
        source = "heartbeat"
    state_stop = _stop_fields(state.get("resting_stop"))
    heartbeat_stop = _stop_fields(heartbeat.get("resting_stop"))
    freshness = _heartbeat_freshness(heartbeat, now)
    state_base = _positive_number(state.get("lane_base"))
    heartbeat_base = _positive_number(heartbeat.get("lane_base"))
    entry_price = _positive_number(state.get("entry_price"))
    mark_present = "mark_price" in heartbeat
    mark = _positive_number(heartbeat.get("mark_price")) if mark_present else None
    reasons: list[str] = []

    if selected["state"] != "ACTIVE":
        reasons.append("LAST_REPORT_NOT_ACTIVE")
    if not running:
        reasons.append("LANE_NOT_RUNNING")
    if not freshness["fresh"]:
        if freshness["age_seconds"] is None:
            reasons.append("HEARTBEAT_TIMESTAMP_INVALID")
        elif freshness["age_seconds"] < 0:
            reasons.append("HEARTBEAT_TIME_IN_FUTURE")
        else:
            reasons.append("HEARTBEAT_STALE")
    if not state_has_stop:
        reasons.append("LANE_STATE_STOP_MISSING")
    if state_stop["state"] != "ACTIVE" or heartbeat_stop["state"] != "ACTIVE":
        reasons.append("STOP_NOT_ACTIVE_IN_BOTH_SNAPSHOTS")
    elif not _stops_agree(state_stop, heartbeat_stop):
        reasons.append("STATE_HEARTBEAT_STOP_MISMATCH")

    required = (
        selected["order_id"],
        selected["local_boundary_price_usd"],
        selected["venue_trigger_price_usd"],
        selected["base_qty"],
        selected["position_base_qty"],
    )
    if any(value is None for value in required):
        reasons.append("STOP_FIELDS_INVALID_OR_MISSING")
    risk_fraction = selected["risk_fraction"]
    price_tick = selected["price_tick_usd"]
    if risk_fraction is None or price_tick is None:
        reasons.append("BOUND_STOP_METADATA_MISSING_OR_INVALID")
    if not math.isfinite(ledger_base) or ledger_base <= EXPOSURE_ABS_TOLERANCE:
        reasons.append("LEDGER_POSITION_NOT_OPEN")
    if not _same_exposure(state_base, ledger_base):
        reasons.append("STATE_LEDGER_EXPOSURE_MISMATCH")
    if not _same_exposure(heartbeat_base, ledger_base):
        reasons.append("HEARTBEAT_LEDGER_EXPOSURE_MISMATCH")
    if not _same_exposure(selected["position_base_qty"], ledger_base):
        reasons.append("STOP_POSITION_EXPOSURE_MISMATCH")

    stop_qty = selected["base_qty"]
    if stop_qty is not None and ledger_base > 0:
        if stop_qty > ledger_base:
            reasons.append("STOP_QTY_EXCEEDS_POSITION")
        elif stop_qty / ledger_base < MIN_STOP_QTY_COVERAGE:
            reasons.append("STOP_QTY_COVERAGE_TOO_LOW")

    boundary = selected["local_boundary_price_usd"]
    trigger = selected["venue_trigger_price_usd"]
    if entry_price is None:
        reasons.append("ENTRY_PRICE_INVALID_OR_MISSING")
    elif risk_fraction is None:
        pass
    elif boundary is None or not math.isclose(
        boundary,
        entry_price * (1 - risk_fraction),
        rel_tol=0.0,
        abs_tol=BOUNDARY_ABS_TOLERANCE_USD,
    ):
        reasons.append("LOCAL_BOUNDARY_MISMATCH")
    if (
        boundary is not None
        and trigger is not None
        and price_tick is not None
        and not (boundary <= trigger <= boundary + price_tick + BOUNDARY_ABS_TOLERANCE_USD)
    ):
        reasons.append("VENUE_TRIGGER_OUTSIDE_TICK_TOLERANCE")
    if not mark_present or mark is None:
        reasons.append("MARK_INVALID_OR_MISSING")
    elif mark is not None and trigger is not None and mark <= trigger:
        reasons.append("MARK_AT_OR_BELOW_TRIGGER")

    reasons = list(dict.fromkeys(reasons))
    active = not reasons
    # A dead process or an old heartbeat can still truthfully identify when the stop was
    # last structurally confirmed. Any data/risk mismatch means it was not confirmation.
    corroborated_report = freshness["heartbeat_at"] is not None and not any(
        reason not in {"LANE_NOT_RUNNING", "HEARTBEAT_STALE"} for reason in reasons
    )
    return {
        "state": selected["state"],
        "last_reported_active": selected["state"] == "ACTIVE",
        "active": active,
        "currently_confirmed": active,
        "source": source,
        "order_id": selected["order_id"],
        "local_boundary_price_usd": selected["local_boundary_price_usd"],
        "venue_trigger_price_usd": selected["venue_trigger_price_usd"],
        "base_qty": selected["base_qty"],
        "position_base_qty": selected["position_base_qty"],
        "risk_fraction": selected["risk_fraction"],
        "price_tick_usd": selected["price_tick_usd"],
        "last_confirmed_at": freshness["heartbeat_at"] if corroborated_report else None,
        "freshness": freshness,
        "reason": reasons[0] if reasons else "CURRENTLY_CONFIRMED_BY_FRESH_LANE_RECONCILIATION",
        "reasons": reasons,
    }


def _order_money(order: dict[str, Any], base_coin: str = BASE_COIN) -> dict[str, Any]:
    """Cash and base movement for one order, taken from reconciled wallet deltas.

    The venue's own before/after balances are the source of truth rather than
    `qty * avg_price`: the delta already includes the fee however the venue charged it
    (quote on sells, base on buys), so a derived notional would disagree with the wallet.

    `base_coin` selects the `<COIN>_delta` reconcile key; it defaults to ETH so the single-lane
    callers (and demo_readiness) are byte-identical, and the multi-coin projection passes each coin.
    """
    reconcile = order.get("reconcile") or {}
    quote_delta = _number(reconcile.get(f"{QUOTE_COIN}_delta"))
    base_delta = _number(reconcile.get(f"{base_coin}_delta"))
    price = _number(order.get("avg_price"))

    return {
        "usd_spent": round(-quote_delta, 4) if quote_delta < 0 else 0.0,
        "usd_received": round(quote_delta, 4) if quote_delta > 0 else 0.0,
        "usd_notional": round(abs(quote_delta), 4),
        "base_delta": round(base_delta, 8),
        # Fee is charged in the base coin on a buy and the quote coin on a sell; express
        # both in USD so the column means one thing.
        "fee_usd": round(
            _number(order.get("fee")) * price
            if order.get("side") == "Buy"
            else _number(order.get("fee")),
            4,
        ),
    }


def _annotate_orders(filled: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-order protection and realised P&L, keyed by order id.

    Walks fills chronologically carrying a running average cost, so a sell can be scored
    against what the position actually cost rather than against the last buy alone.

    `stop_loss` and `take_profit` are recorded per order because that is what they
    describe: the protection attached to *that* position when it was opened. They are
    null here because this strategy defines none — but the field belongs on the order, not
    on the account, so a future strategy that does set them displays without restructuring.
    """
    annotations: dict[str, dict[str, Any]] = {}
    base_held = 0.0
    cost_basis = 0.0

    for index, order in enumerate(filled):
        money = _order_money(order)
        key = str(order.get("order_id") or f"idx-{index}")
        realised: float | None = None

        if order.get("side") == "Buy":
            base_held += money["base_delta"]
            cost_basis += money["usd_spent"]
        else:
            sold = -money["base_delta"]
            average = cost_basis / base_held if base_held > 0 else 0.0
            realised = money["usd_received"] - sold * average
            cost_basis -= sold * average
            base_held -= sold

        annotations[key] = {
            "stop_loss": None,
            "take_profit": None,
            "protection": "none — rule-driven exit",
            "realised_pnl_usd": round(realised, 4) if realised is not None else None,
        }
    return annotations


def _position(
    filled: list[dict[str, Any]],
    mark: float,
    rules: dict[str, Any],
    operational_stop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The open position, if any — everything scoped to this trade rather than the account.

    Stop loss, take profit, exit trigger, entry, and unrealised P&L all belong here: they
    describe one position. Wallet balances and order caps do not, and live at account
    scope instead.
    """
    base_held = 0.0
    cost_basis = 0.0
    opened_at: str | None = None

    for order in filled:
        money = _order_money(order)
        if order.get("side") == "Buy":
            if base_held <= 0:
                opened_at = order.get("recorded_at")
            base_held += money["base_delta"]
            cost_basis += money["usd_spent"]
        else:
            sold = -money["base_delta"]
            average = cost_basis / base_held if base_held > 0 else 0.0
            cost_basis -= sold * average
            base_held -= sold
            if base_held <= 1e-12:
                base_held, cost_basis, opened_at = 0.0, 0.0, None

    if base_held <= 1e-12:
        return {
            "open": False,
            "symbol": "ETHUSDT",
            "side": None,
            "entry_price_usd": None,
            "stop_loss": None,
            "take_profit": None,
            "would_enter_above": rules.get("donchian_upper"),
            "note": (
                "No open position. The lane buys on a 40-bar breakout with volume confirmation."
            ),
        }

    entry = cost_basis / base_held
    value = base_held * mark if mark > 0 else None
    exit_trigger = _number(rules.get("donchian_lower"))

    position = {
        "open": True,
        "symbol": "ETHUSDT",
        "side": "LONG",
        "size_base": round(base_held, 8),
        "opened_at": opened_at,
        "entry_price_usd": round(entry, 2),
        "cost_usd": round(cost_basis, 4),
        "mark_price_usd": round(mark, 2) if mark > 0 else None,
        "value_usd": round(value, 4) if value is not None else None,
        "unrealised_pnl_usd": round(value - cost_basis, 4) if value is not None else None,
        "unrealised_pnl_pct": (
            round((value - cost_basis) / cost_basis * 100, 2)
            if value is not None and cost_basis > 0
            else None
        ),
        # Position-scoped protection. Null because the spec sets both to null — stated
        # here rather than at account level, because a stop protects a position.
        "stop_loss": None,
        "take_profit": None,
        "protection": "none — this strategy defines no stop loss or take profit",
        "exit_trigger_usd": round(exit_trigger, 2) if exit_trigger else None,
        "exit_rule": "sells when a 1h bar closes below the 40-bar Donchian low",
        "distance_to_exit_pct": (
            round((mark - exit_trigger) / mark * 100, 2) if mark > 0 and exit_trigger > 0 else None
        ),
        "max_loss_bounded_by": "position size — no leverage, spot only",
    }
    if operational_stop is not None:
        position["operational_disaster_stop"] = dict(operational_stop)
        if operational_stop.get("active") is True:
            position["protection"] = _operational_protection_text(operational_stop)
    return position


# Measured on 259 historical trades of this exact rule (ETHUSDT 1h, 2026-07-20 analysis):
# median hold 65 bars. Shown as the expected trade time because it is measured, not guessed.
EXPECTED_HOLD_BARS = 65
EXPECTED_HOLD_SOURCE = "median of 259 historical trades of this rule"
STRATEGY_ID = "STRAT-ETH-volume-breakout-prospective-v1"


def _round_trips(filled: list[dict[str, Any]], mark: float) -> list[dict[str, Any]]:
    """Fills folded into positions: each buy→sell round trip is one closed position,
    a trailing unmatched buy is the open one.

    This is the object the operator actually thinks in. The ledger stores orders because
    orders are what the venue confirms; positions are derived, never stored, so they can
    never disagree with the fills underneath them.
    """
    positions: list[dict[str, Any]] = []
    entry: dict[str, Any] | None = None

    for order in filled:
        money = _order_money(order)
        if order.get("side") == "Buy":
            entry = {
                "coin": "ETH",
                "symbol": "ETHUSDT",
                "side": "LONG",
                "status": "OPEN",
                "opened_at": order.get("recorded_at"),
                "size_base": money["base_delta"],
                "entry_price_usd": (
                    round(money["usd_spent"] / money["base_delta"], 2)
                    if money["base_delta"] > 0
                    else None
                ),
                "spent_usd": money["usd_spent"],
                "strategy": STRATEGY_ID,
                "timeframe": "1h",
                # Steps as lists so a future laddered-TP/SL strategy fits unchanged.
                "tp_steps": [],
                "sl_steps": [],
                "protection": "none — rule-driven exit (close < 40-bar Donchian low)",
                "expected_hold_bars": EXPECTED_HOLD_BARS,
                "expected_hold_source": EXPECTED_HOLD_SOURCE,
            }
        elif entry is not None:
            received = money["usd_received"]
            pnl = received - entry["spent_usd"]
            positions.append(
                {
                    **entry,
                    "status": "CLOSED",
                    "closed_at": order.get("recorded_at"),
                    "exit_price_usd": (
                        round(received / -money["base_delta"], 2)
                        if money["base_delta"] < 0
                        else None
                    ),
                    "received_usd": received,
                    "pnl_usd": round(pnl, 4),
                    "pnl_pct": (
                        round(pnl / entry["spent_usd"] * 100, 2) if entry["spent_usd"] > 0 else None
                    ),
                }
            )
            entry = None

    if entry is not None:
        value = entry["size_base"] * mark if mark > 0 else None
        pnl = value - entry["spent_usd"] if value is not None else None
        positions.append(
            {
                **entry,
                "mark_price_usd": round(mark, 2) if mark > 0 else None,
                "value_usd": round(value, 4) if value is not None else None,
                "pnl_usd": round(pnl, 4) if pnl is not None else None,
                "pnl_pct": (
                    round(pnl / entry["spent_usd"] * 100, 2)
                    if pnl is not None and entry["spent_usd"] > 0
                    else None
                ),
            }
        )
    return positions[::-1]  # newest first


def _attach_operational_stop(
    positions: list[dict[str, Any]], operational_stop: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach operational protection only to the one current open position."""
    attached = False
    projected: list[dict[str, Any]] = []
    for original in positions:
        position = dict(original)
        if not attached and position.get("status") == "OPEN":
            attached = True
            position["operational_disaster_stop"] = dict(operational_stop)
            if operational_stop.get("active") is True:
                position["sl_steps"] = [operational_stop["venue_trigger_price_usd"]]
                position["protection"] = _operational_protection_text(operational_stop)
        projected.append(position)
    return projected


def _operational_protection_text(operational_stop: dict[str, Any]) -> str:
    risk_pct = _number(operational_stop.get("risk_fraction")) * 100
    return (
        "currently confirmed by fresh lane reconciliation: last reported operational "
        f"-{risk_pct:g}% disaster stop at the venue trigger, plus the strategy's "
        "rule-driven exit on a close below the 40-bar Donchian low"
    )


def _parse_ts(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _window_stats(
    positions: list[dict[str, Any]],
    filled: list[dict[str, Any]],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    """Per-window aggregates: realised P/L, open/closed counts, fees, win rate, volume.

    Realised P/L is attributed to the window the position *closed* in — the moment the
    result became real. Unrealised P/L is deliberately excluded from window numbers: it
    belongs to the open position, and mixing it in would make '1 day net' drift with every
    price tick even when nothing was traded.
    """
    windows = {"1d": 1, "1w": 7, "1m": 30, "all": None}
    out: dict[str, dict[str, Any]] = {}

    for name, days in windows.items():
        threshold = None if days is None else now - timedelta(days=days)

        def _in(ts: Any, threshold: datetime | None = threshold) -> bool:
            parsed = _parse_ts(ts)
            return parsed is not None and (threshold is None or parsed >= threshold)

        closed = [p for p in positions if p["status"] == "CLOSED" and _in(p.get("closed_at"))]
        opened = [p for p in positions if _in(p.get("opened_at"))]
        window_fills = [o for o in filled if _in(o.get("recorded_at"))]
        wins = [p for p in closed if (p.get("pnl_usd") or 0) > 0]
        realised = sum(p.get("pnl_usd") or 0 for p in closed)
        spent = sum(p.get("spent_usd") or 0 for p in closed)

        out[name] = {
            "realised_pnl_usd": round(realised, 4),
            "realised_pnl_pct": round(realised / spent * 100, 2) if spent > 0 else None,
            "positions_opened": len(opened),
            "positions_closed": len(closed),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
            "fees_usd": round(sum(_order_money(o)["fee_usd"] for o in window_fills), 4),
            "volume_usd": round(sum(_order_money(o)["usd_notional"] for o in window_fills), 2),
        }
    return out


def _pnl(filled: list[dict[str, Any]], mark_price: float) -> dict[str, Any]:
    """Average-cost P&L for the lane.

    Average cost rather than lot matching: the lane holds one position at a time and
    never partially exits, so the two agree here, and average cost degrades sensibly if
    that ever changes.

    `mark_price` of zero means the lane has not yet recorded a snapshot. Unrealised P&L is
    then unavailable rather than zero — reporting an unmarked position as flat would
    understate risk, so the field is null and the UI says so.
    """
    spent = sum(_order_money(order)["usd_spent"] for order in filled)
    received = sum(_order_money(order)["usd_received"] for order in filled)
    base_bought = sum(
        _order_money(order)["base_delta"] for order in filled if order.get("side") == "Buy"
    )
    position = sum(_order_money(order)["base_delta"] for order in filled)
    net_cash = received - spent

    average_cost = spent / base_bought if base_bought > 0 else 0.0
    marked = mark_price > 0

    position_value = position * mark_price if marked else None
    unrealised = position * (mark_price - average_cost) if marked and position > 0 else 0.0
    total = (net_cash + position_value) if marked and position_value is not None else None
    realised = (total - unrealised) if total is not None else None

    return {
        "invested_usd": round(spent, 4),
        "returned_usd": round(received, 4),
        "net_cash_usd": round(net_cash, 4),
        "position_base": round(position, 8),
        "average_cost_usd": round(average_cost, 4) if base_bought > 0 else None,
        "mark_price_usd": round(mark_price, 4) if marked else None,
        "position_value_usd": round(position_value, 4) if position_value is not None else None,
        "realised_pnl_usd": round(realised, 4) if realised is not None else None,
        "unrealised_pnl_usd": round(unrealised, 4) if marked else None,
        "total_pnl_usd": round(total, 4) if total is not None else None,
        "total_pnl_pct": (
            round(total / spent * 100, 4) if total is not None and spent > 0 else None
        ),
        "marked": marked,
        "basis": "average_cost",
        "currency": QUOTE_COIN,
    }


def _wallet(heartbeat: dict[str, Any], filled: list[dict[str, Any]]) -> dict[str, Any]:
    """Latest wallet snapshot, preferring the per-cycle heartbeat over the last fill.

    The heartbeat is refreshed every cycle; a fill's snapshot is only as recent as the
    last trade. Whichever is used, `as_of` states when it was taken — a balance shown
    without its timestamp invites reading a stale number as live.
    """
    balances = heartbeat.get("wallet")
    as_of = heartbeat.get("at")
    source = "heartbeat"

    if not isinstance(balances, dict) or not balances:
        source = "last_fill"
        balances, as_of = {}, None
        for order in reversed(filled):
            snapshot = order.get("wallet_after")
            if isinstance(snapshot, dict) and snapshot:
                balances, as_of = snapshot, order.get("recorded_at")
                break

    coins = {coin: _number(amount) for coin, amount in balances.items()}
    return {
        "available": bool(coins),
        "as_of": as_of,
        "source": source if coins else None,
        "balances": {coin: round(amount, 8) for coin, amount in coins.items()},
        "quote_balance_usd": round(coins.get(QUOTE_COIN, 0.0), 4) if coins else None,
        "base_balance": round(coins.get(BASE_COIN, 0.0), 8) if coins else None,
    }


def _rules(heartbeat: dict[str, Any], holding: bool, mark: float) -> dict[str, Any]:
    """What actually governs entry and exit, including the absence of a stop.

    The spec sets `stop_loss: null` and `take_profit: null`. Rendering those as blank
    fields would read as "not loaded yet"; they are stated as explicitly absent, with the
    rule that does govern the exit shown alongside, so the screen cannot be mistaken for
    one describing a stop-protected position.
    """
    levels = heartbeat.get("rule_levels") or {}
    warming = bool(levels.get("warming_up")) or not levels

    lower = _number(levels.get("donchian_lower"))
    upper = _number(levels.get("donchian_upper"))
    threshold = _number(levels.get("volume_threshold"))
    volume = _number(levels.get("volume_base"))

    # While long, the exit band is the price that matters; while flat, the entry band is.
    trigger = lower if holding else upper
    distance_pct = ((mark - trigger) / mark * 100) if (mark > 0 and trigger > 0) else None

    return {
        # Stop loss and take profit are NOT here: they describe a position, not the market
        # state or the account. See `position.stop_loss` / `position.take_profit`.
        "warming_up": warming,
        "entry_rule": "close > donchian_upper(40) AND volume > 1.5x average(40)",
        "exit_rule": "close < donchian_lower(40)",
        "donchian_upper": round(upper, 2) if upper else None,
        "donchian_lower": round(lower, 2) if lower else None,
        "volume_threshold": round(threshold, 4) if threshold else None,
        "volume_base": round(volume, 4) if volume else None,
        "active_trigger": "EXIT_BELOW" if holding else "ENTRY_ABOVE",
        "active_trigger_price": round(trigger, 2) if trigger else None,
        "distance_to_trigger_pct": round(distance_pct, 2) if distance_pct is not None else None,
        "bar_close_time": levels.get("bar_close_time"),
        "evaluated_on": "closed 1h bars only; fills at the next bar open",
    }


def _divergence(root: Path, fills_now: int) -> dict[str, Any]:
    """Latest divergence report (T-015-03 measurement mode), with staleness stated.

    The report is regenerated by `scripts/run_demo_divergence_report.py`; if fills have
    landed since it last ran, saying so beats silently showing numbers that omit them.
    """
    payload = _read_json(root / DIVERGENCE_REPORT)
    if not payload:
        return {
            "available": False,
            "note": "no divergence report yet - run scripts/run_demo_divergence_report.py",
        }
    measured = int(payload.get("fills_measured") or 0)
    return {
        "available": True,
        "fills_measured": measured,
        "stale": fills_now > measured,
        "mean_divergence_bps": payload.get("mean_divergence_bps"),
        "worst_divergence_bps": payload.get("worst_divergence_bps"),
        "generated_at": payload.get("generated_at"),
        "interpretation": "positive bps = worse than the frozen next-open expectation",
    }


def _validated(payload: dict[str, Any]) -> tuple[str, str]:
    action = str(payload.get("action", "")).strip().upper()
    if action not in ACTIONS:
        # Fixed generic error — never reflect the requested action value back to the client.
        raise DemoLaneActionError("demo lane action is invalid")
    key = payload.get("idempotency_key")
    if not isinstance(key, str) or not _IDENTIFIER.fullmatch(key):
        raise DemoLaneActionError("idempotency_key must be a bounded identifier")
    if set(payload) - {"action", "idempotency_key"}:
        raise DemoLaneActionError("demo lane actions accept only action and idempotency_key")
    return action, key


def _audit(root: Path, record: dict[str, Any]) -> None:
    try:
        with confined_audit_handle(root, AUDIT_PATH, create=True) as handle:
            assert handle is not None
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, AuditPathError) as error:
        raise DemoLaneActionError("demo lane audit is unavailable", 503) from error


# The ONLY flag-sets _spawn will launch, keyed by internal mode literal. perform_demo_lane_action
# picks the key from the allowlisted action; no request/user value ever reaches this map, so the
# spawned argv stays fixed. "--activity" is bare START's confluence sibling: --loop until killed at
# a hardcoded interval; it shares lane.lock and the same KILL_SWITCH, so STOP halts it too.
_SPAWN_FLAGS: dict[str, tuple[str, ...]] = {
    "--loop": ("--loop",),
    "--multi": ("--multi",),
    "--activity": ("--activity", "--loop", "--interval", ACTIVITY_INTERVAL),
}


def _spawn(root: Path, mode: str) -> subprocess.Popen[bytes]:
    """Launch the lane. Fixed argv, no shell, no user input — `mode` is an internal literal that
    selects one hardcoded flag-set from _SPAWN_FLAGS (an unknown key is a bug, never a request)."""
    flags = _SPAWN_FLAGS[mode]
    (root / LANE_DIR).mkdir(parents=True, exist_ok=True)
    log = (root / LANE_LOG).open("ab")
    return subprocess.Popen(  # noqa: S603 (fixed argv, shell=False)
        [sys.executable, str(root / LANE_SCRIPT), *flags],
        cwd=str(root),
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _research_running(root: Path) -> bool:
    """Is a prior research search still alive? PID-liveness on the research guard lock.

    ponytail: PID-liveness (not an flock) because run_universe_search.py holds no lock of its own;
    PID reuse could in theory mask a dead run, and a concurrent-request burst can still race the
    check-then-spawn to launch >1 search (the script has no self-lock) — both acceptable for a
    single-operator local search. Upgrade to a self-locking (flock/exit-3) wrapper on
    run_universe_search.py if research ever runs multi-tenant or must be double-click-safe.
    """
    holder = _read_json(root / RESEARCH_LOCK)
    pid = holder.get("pid")
    # bool is an int subclass; a non-positive pid targets a process GROUP or the caller, never a
    # research run. Reject both, and treat ANY liveness-probe failure (incl. OverflowError from a
    # huge/corrupt pid) as "not running" so a hostile/garbage lock file can never crash the guard.
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # the process exists, just owned by another user
    except Exception:
        return False
    return True


def _spawn_research(root: Path) -> subprocess.Popen[bytes]:
    """Launch the offline universe search detached. Fixed argv, no flags, no shell, no user input —
    research only (no venue, no orders, authority NONE). Records a PID-liveness guard lock so a
    second search is refused while one is in flight."""
    (root / RESEARCH_LOCK).parent.mkdir(parents=True, exist_ok=True)
    log = (root / RESEARCH_LOG).open("ab")
    process = subprocess.Popen(  # noqa: S603 (fixed argv, shell=False)
        [sys.executable, str(root / RESEARCH_SCRIPT)],
        cwd=str(root),
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    (root / RESEARCH_LOCK).write_text(
        json.dumps({"pid": process.pid, "started_at": datetime.now(tz=UTC).isoformat()})
    )
    return process


def perform_demo_lane_action(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one allowlisted lane control and retain an operator audit record."""
    action, key = _validated(payload)
    root = root.resolve()
    if not (root / LANE_SCRIPT).is_file():
        raise DemoLaneActionError("demo lane script is missing", 503)
    running, pid, _started = _running(root)
    kill_switch = root / KILL_SWITCH
    detail = ""

    if action == "START":
        if running:
            raise DemoLaneActionError("the demo lane is already running", 409)
        kill_switch.unlink(missing_ok=True)  # starting clears a previous stop
        process = _spawn(root, "--loop")
        detail = f"lane started (pid {process.pid}); stop flag cleared"
    elif action == "START_ACTIVITY":
        # Shares lane.lock (so `running` above already refuses a second lane) and the same
        # KILL_SWITCH STOP writes, so STOP halts it too. Fixed argv: --activity --loop --interval.
        if running:
            raise DemoLaneActionError("the demo lane is already running", 409)
        kill_switch.unlink(missing_ok=True)  # starting clears a previous stop
        process = _spawn(root, "--activity")
        detail = f"confluence activity lane started (pid {process.pid}); stop flag cleared"
    elif action == "START_MULTI":
        # Multi-coin order-path lane. Shares lane.lock (so `running` above already refuses a second
        # lane) and the same KILL_SWITCH STOP writes, so STOP halts it too. Fixed argv: --multi.
        if running:
            raise DemoLaneActionError("the demo lane is already running", 409)
        kill_switch.unlink(missing_ok=True)  # starting clears a previous stop
        process = _spawn(root, "--multi")
        detail = f"multi-coin lane started (pid {process.pid}); stop flag cleared"
    elif action == "START_RESEARCH":
        # Research-only (NO orders, authority NONE): NOT a lane, so it does NOT share lane.lock.
        # A separate PID-liveness research guard stops two searches clobbering the same output.
        if not (root / RESEARCH_SCRIPT).is_file():
            raise DemoLaneActionError("research search script is missing", 503)
        if _research_running(root):
            raise DemoLaneActionError("a research search is already running", 409)
        process = _spawn_research(root)
        detail = f"offline research search started (pid {process.pid}); no orders, authority NONE"
    elif action == "STOP":
        kill_switch.parent.mkdir(parents=True, exist_ok=True)
        kill_switch.write_text(
            json.dumps({"stopped_at": datetime.now(tz=UTC).isoformat(), "source": "dashboard"})
        )
        # The flag alone already blocks every order; also end the process so it stops polling.
        if running and isinstance(pid, int):
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
        detail = "stop flag set; orders are refused immediately"
    else:  # RUN_ONCE
        if running:
            raise DemoLaneActionError(
                "the lane is already running; a second cycle would race its state", 409
            )
        kill_switch.unlink(missing_ok=True)
        try:
            completed = subprocess.run(  # noqa: S603 (fixed argv, shell=False)
                [sys.executable, str(root / LANE_SCRIPT), "--once"],
                cwd=str(root),
                capture_output=True,
                timeout=RUN_ONCE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DemoLaneActionError("the demo lane cycle timed out", 504) from error
        detail = f"single cycle finished with exit code {completed.returncode}"

    record = {
        "schema_version": 1,
        "decided_at": datetime.now(tz=UTC).isoformat(),
        "source": "local_dashboard_operator",
        "action": action,
        "idempotency_key": key,
        "detail": detail,
        "environment": "VENUE_DEMO",
        "real_money": False,
    }
    _audit(root, record)
    # Detailed audit stays disk-only; the success body is restricted to four fixed fields.
    state, _kill = _operational_snapshot(root)
    return {"schema_version": 2, "ok": True, "action": action, "state": state}
