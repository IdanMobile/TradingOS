"""Local, loopback-only inbox for third-party trading-signal webhooks.

`POST /api/v1/signals/ingest` accepts a bounded JSON payload from any external source
(TradingView alert webhook, a custom bot, a relay like 3Commas' Signal Bot) and appends
it to a confined, append-only JSONL ledger. `GET /api/v1/signals` projects that ledger
read-only. Disabled by default (fail-closed): requires TIOS_SIGNALS_WEBHOOK_SECRET.

Reaching this endpoint from a real external service (TradingView's cloud, a hosted
bot) requires exposing the dashboard beyond loopback — a separate, explicit decision
this module does not make; `server.py`'s `is_loopback_host` still enforces localhost
binding. No order, venue, or execution capability exists behind this endpoint.

Every field beyond source/symbol/action/rationale (network, strategy, entry_price,
stop_loss, take_profit, timeframe) is optional — a sender that doesn't know a field
just omits it, and the dashboard shows "not provided" rather than a fabricated value.
"""

from __future__ import annotations

import fcntl
import hmac
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.services.dashboard_api.audit import confined_audit_handle

SIGNALS_INBOX_PATH = Path("artifacts/signals/inbox.jsonl")
_ACTIONS = {"BUY", "SELL", "HOLD", "INFORMATIVE"}
_SOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/&()-]{0,79}$")
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_MAX_SIGNALS_RETURNED = 200
_MAX_TAKE_PROFIT_STEPS = 4


class SignalIngestError(ValueError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _webhook_secret() -> str | None:
    return os.environ.get("TIOS_SIGNALS_WEBHOOK_SECRET") or None


def _bounded_str(value: Any, field: str, max_len: int) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > max_len:
        raise SignalIngestError(400, f"{field} must be a string under {max_len} chars")
    return value


def _positive_price(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise SignalIngestError(400, f"{field} must be a positive number")
    return float(value)


def _take_profit_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > _MAX_TAKE_PROFIT_STEPS:
        raise SignalIngestError(
            400, f"take_profit must be a list of at most {_MAX_TAKE_PROFIT_STEPS} numbers"
        )
    return [_positive_price(step, "take_profit step") for step in value]  # type: ignore[misc]


def _signal_strength(value: Any) -> float | None:
    """0-100: how far past its own trigger threshold the underlying data is.

    NOT a probability, NOT backtested accuracy — there is no outcome-tracking behind
    this number (yet). It only answers "how strong was this reading relative to what
    it took to trigger," e.g. a +18% move against a +5% threshold is stronger than a
    +5.1% move. A real historical hit-rate would need outcome tracking and is a
    separate, bigger feature — this is the honest thing computable today.
    """
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool) or not (0 <= value <= 100):
        raise SignalIngestError(400, "signal_strength must be a number from 0 to 100")
    return float(value)


def _iso_datetime(value: Any, field: str) -> str | None:
    """When the underlying event actually happened/was computed by the source —
    distinct from `received_at`, which is always when *we* stored the record. A
    source that can't honestly say when its data is from just omits this."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SignalIngestError(400, f"{field} must be an ISO 8601 datetime string")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise SignalIngestError(400, f"{field} must be a valid ISO 8601 datetime") from error
    return value


def _build_record(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source")
    symbol = payload.get("symbol")
    action = payload.get("action")
    rationale = payload.get("rationale", "")
    if not isinstance(source, str) or not _SOURCE_RE.fullmatch(source):
        raise SignalIngestError(400, "source must be a short bounded identifier")
    if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol.upper()):
        raise SignalIngestError(400, "symbol must be a short bounded ticker")
    if not isinstance(action, str) or action.upper() not in _ACTIONS:
        raise SignalIngestError(400, "action must be one of BUY, SELL, HOLD, INFORMATIVE")
    if not isinstance(rationale, str) or len(rationale) > 500:
        raise SignalIngestError(400, "rationale must be a string under 500 chars")

    return {
        "schema_version": 2,
        "received_at": datetime.now(tz=UTC).isoformat(),
        "source": source,
        "symbol": symbol.upper(),
        "action": action.upper(),
        "rationale": rationale[:500],
        "network": _bounded_str(payload.get("network"), "network", 60),
        "strategy": _bounded_str(payload.get("strategy"), "strategy", 140),
        "timeframe": _bounded_str(payload.get("timeframe"), "timeframe", 60),
        "entry_price": _positive_price(payload.get("entry_price"), "entry_price"),
        "stop_loss": _positive_price(payload.get("stop_loss"), "stop_loss"),
        "take_profit": _take_profit_list(payload.get("take_profit")),
        "signal_strength": _signal_strength(payload.get("signal_strength")),
        "observed_at": _iso_datetime(payload.get("observed_at"), "observed_at"),
    }


def ingest_signal(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and append one inbound signal record; raises SignalIngestError."""
    expected_secret = _webhook_secret()
    if not expected_secret:
        raise SignalIngestError(
            503, "signal ingest is disabled: set TIOS_SIGNALS_WEBHOOK_SECRET to enable it"
        )
    secret = payload.get("secret")
    if not isinstance(secret, str) or not hmac.compare_digest(
        secret.encode(), expected_secret.encode()
    ):
        raise SignalIngestError(401, "invalid or missing secret")

    record = _build_record(payload)
    _append_record(root, record)
    return record


def append_polled_signal(root: Path, **fields: Any) -> dict[str, Any]:
    """Append a signal from a trusted internal poller (e.g. signal_pollers.py).

    Skips the webhook secret check — this is not reachable from outside the process,
    unlike `ingest_signal` which validates an inbound HTTP request. Accepts the same
    fields as `ingest_signal`'s payload (minus `secret`).
    """
    record = _build_record(fields)
    _append_record(root, record)
    return record


def _append_record(root: Path, record: dict[str, Any]) -> None:
    with confined_audit_handle(root, SIGNALS_INBOX_PATH, create=True) as handle:
        assert handle is not None
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_all_signals(root: Path) -> list[dict[str, Any]]:
    """Every stored signal, oldest first, unbounded (no display cap).

    For outcome resolution / reliability tracking, which needs to see signals
    older than the 200-record display window `build_signals` returns.
    """
    records: list[dict[str, Any]] = []
    with confined_audit_handle(root, SIGNALS_INBOX_PATH, create=False) as handle:
        if handle is not None:
            for line in handle:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
    return records


def build_signals(root: Path) -> dict[str, Any]:
    """Read-only projection of the signals inbox, newest first."""
    records = list(reversed(read_all_signals(root)))
    sources: dict[str, str] = {}
    for record in records:
        name = record.get("source", "")
        if name and name not in sources:
            sources[name] = record.get("received_at", "")
    return {
        "schema_version": 1,
        "signal_count": len(records),
        "signals": records[:_MAX_SIGNALS_RETURNED],
        "sources": [{"name": name, "last_received_at": ts} for name, ts in sources.items()],
        "ingest_enabled": _webhook_secret() is not None,
    }
