"""Real historical hit-rate tracking for signals — not a fabricated confidence number.

For every BUY/SELL signal that has a real `entry_price`, once 24h have passed since it
fired, this fetches the *actual* historical Binance price at that point (klines, not a
live/current price — so an old signal is always evaluated at the same fixed horizon,
not "as of whenever someone happens to look") and records whether the price moved the
predicted direction. Resolved outcomes are persisted (append-only, same
`confined_audit_handle` pattern as the rest of this package) so the same historical
price is never re-fetched twice.

`build_reliability` then aggregates a real per-source hit rate from that ledger: of the
signals old enough to check, what fraction were actually followed by the expected move.
This is still not proof of a durable edge (small sample sizes, one fixed 24h horizon,
no cost/slippage modeling) — it is real, though, unlike `signal_strength`.
"""

from __future__ import annotations

import fcntl
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tios.services.dashboard_api.audit import confined_audit_handle
from tios.services.dashboard_api.signals_inbox import read_all_signals

OUTCOMES_PATH = Path("artifacts/signals/outcomes.jsonl")
RESOLUTION_HORIZON = timedelta(hours=24)
_KLINES_URL = "https://api.binance.com/api/v3/klines"


def _get_json(url: str, *, timeout: float = 10) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def _fetch_price_at(symbol: str, at_time: datetime) -> float | None:
    """The Binance 1h close nearest at-or-after `at_time`, or None if unavailable."""
    pair = f"{symbol}USDT"
    start_ms = int(at_time.timestamp() * 1000)
    url = f"{_KLINES_URL}?symbol={pair}&interval=1h&startTime={start_ms}&limit=1"
    try:
        rows = _get_json(url)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    if not rows:
        return None
    try:
        return float(rows[0][4])  # close
    except (IndexError, TypeError, ValueError):
        return None


def _outcome_key(signal: dict[str, Any]) -> tuple[str, str, str]:
    return (signal.get("source", ""), signal.get("symbol", ""), signal.get("received_at", ""))


def _resolved_keys(root: Path) -> set[tuple[str, str, str]]:
    keys = set()
    with confined_audit_handle(root, OUTCOMES_PATH, create=False) as handle:
        if handle is not None:
            for line in handle:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    keys.add(
                        (
                            item.get("source", ""),
                            item.get("symbol", ""),
                            item.get("signal_received_at", ""),
                        )
                    )
    return keys


def resolve_pending_outcomes(root: Path) -> int:
    """Resolve any signal that's old enough and not yet checked. Returns count resolved."""
    now = datetime.now(tz=UTC)
    already = _resolved_keys(root)
    resolved_count = 0
    for signal in read_all_signals(root):
        if signal.get("action") not in ("BUY", "SELL"):
            continue
        entry_price = signal.get("entry_price")
        received_at = signal.get("received_at")
        if entry_price is None or not received_at:
            continue
        if _outcome_key(signal) in already:
            continue
        try:
            signal_time = datetime.fromisoformat(received_at)
        except ValueError:
            continue
        target_time = signal_time + RESOLUTION_HORIZON
        if target_time > now:
            continue  # not old enough to resolve yet
        target_price = _fetch_price_at(signal["symbol"], target_time)
        if target_price is None:
            continue  # transient fetch failure; retry on the next poll
        moved_up = target_price > entry_price
        correct = moved_up if signal["action"] == "BUY" else not moved_up
        outcome = {
            "schema_version": 1,
            "source": signal.get("source", ""),
            "symbol": signal["symbol"],
            "action": signal["action"],
            "entry_price": entry_price,
            "signal_received_at": received_at,
            "resolved_at": now.isoformat(),
            "target_time": target_time.isoformat(),
            "target_price": target_price,
            "correct": correct,
            "return_pct": round((target_price - entry_price) / entry_price * 100, 3),
        }
        with confined_audit_handle(root, OUTCOMES_PATH, create=True) as handle:
            assert handle is not None
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(outcome, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        resolved_count += 1
        already.add(_outcome_key(signal))
    return resolved_count


def build_reliability(root: Path) -> dict[str, Any]:
    """Read-only aggregation of the outcomes ledger — no network calls, just a read."""
    outcomes: list[dict[str, Any]] = []
    with confined_audit_handle(root, OUTCOMES_PATH, create=False) as handle:
        if handle is not None:
            for line in handle:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    outcomes.append(item)

    now = datetime.now(tz=UTC)
    pending_by_source: dict[str, int] = {}
    for signal in read_all_signals(root):
        if signal.get("action") not in ("BUY", "SELL") or signal.get("entry_price") is None:
            continue
        try:
            signal_time = datetime.fromisoformat(signal["received_at"])
        except (KeyError, ValueError):
            continue
        if signal_time + RESOLUTION_HORIZON > now:
            source = signal.get("source", "")
            pending_by_source[source] = pending_by_source.get(source, 0) + 1

    by_source: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        source = outcome.get("source", "")
        stats = by_source.setdefault(source, {"resolved": 0, "correct": 0})
        stats["resolved"] += 1
        if outcome.get("correct"):
            stats["correct"] += 1

    for source, stats in by_source.items():
        stats["hit_rate_pct"] = (
            round(stats["correct"] / stats["resolved"] * 100, 1) if stats["resolved"] else None
        )
        stats["pending"] = pending_by_source.pop(source, 0)
    for source, pending in pending_by_source.items():
        by_source[source] = {"resolved": 0, "correct": 0, "hit_rate_pct": None, "pending": pending}

    return {
        "schema_version": 1,
        "horizon_hours": RESOLUTION_HORIZON.total_seconds() / 3600,
        "by_source": by_source,
    }
