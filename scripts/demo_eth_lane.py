#!/usr/bin/env python3
"""D-104 stage-2 ETH demo measurement lane — typed intents, capped orders, canonical signals.

The ONLY sanctioned order path to the Bybit demo account. The raw demo scripts' POST
transports stay permanently quarantined (D-046); this module carries its own reviewed
transport with the same demo-host refusal property, and every order flows through a typed
`LaneIntent` with kill-switch, notional-cap, and quantization checks, then is reconciled
against wallet deltas and appended to an append-only ledger.

Signals are the D-103 canonical candidate (`SV-418ab5d64825c74b`, prior-40-bar Donchian with
1.5x volume confirmation) evaluated by the SAME `evaluate_strategy_signals` code that
reproduced the frozen 511-transition history — semantic parity by construction. Price feed is
the demo venue's own public klines, labeled `BYBIT_DEMO_SPOT`. The lane acts only on signals
NEWER than its persisted cursor: nothing re-fires on restart, and only transitions that occur
after lane start are traded (prospective discipline).

Execution-measurement mode: demo/fake money, candidate stays UNVALIDATED / NOT_ELIGIBLE,
demo P&L is not validation evidence, no live path exists. Stop everything by creating the
file artifacts/trading_domain/demo_lane/KILL_SWITCH.

Run: python scripts/demo_eth_lane.py --once      # one evaluation cycle
     python scripts/demo_eth_lane.py --loop      # hourly, until killed
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
from tios.strategy.evaluator import evaluate_strategy_signals  # noqa: E402
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402
from tios.trading_domain import (  # noqa: E402
    CreatorType,
    DatasetId,
    DomainRef,
    InstrumentId,
    Market,
    MarketBar,
    MarketName,
    Provenance,
    RunId,
    StrategyVersionId,
    Timeframe,
    VenueFamily,
)

LANE_DIR = pf.ROOT / "artifacts" / "trading_domain" / "demo_lane"
KILL_SWITCH = LANE_DIR / "KILL_SWITCH"
ORDERS_LEDGER = LANE_DIR / "orders.jsonl"
ACTIONS_LEDGER = pf.ROOT / "artifacts" / "human_decisions" / "demo_lane_actions.jsonl"
LANE_STATE = LANE_DIR / "lane_state.json"
HEARTBEAT = LANE_DIR / "heartbeat.json"
LANE_LOCK = LANE_DIR / "lane.lock"

SYMBOL = "ETHUSDT"
BUY_QUOTE_USDT = Decimal("25")
SELL_MAX_NOTIONAL = Decimal("120")  # independent sell cap (stage-1 review item)
FALLBACK_QTY_STEP = Decimal("0.00001")
_ORDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")

# Tail insurance, not an active constraint. Operator approved BOTH a local disaster-stop and a
# venue-resting stop for the demo lane on 2026-07-21 (D-104 demo-lane scope; no new authority).
# Evidence: MAE analysis over 259 demo trades showed median adverse excursion -2.67% and the
# -15% level was NEVER hit (SESSION_HANDOFF_2026_07_21.md item 3;
# docs/supervisor/STATISTICAL_REMEDIATION_PLAN_D112_2026-07-21.md, [OPERATOR] follow-up).
DEMO_DISASTER_STOP_PCT = Decimal("0.15")
SPEC_PATH = (
    pf.ROOT / "strategies/research/eth-volume-breakout-prospective/canonical_strategy_spec.yaml"
)
SPEC_PARAMETERS = {
    "instrument": "ETH-USDT.BINANCE_SPOT",
    "timeframe": "1h",
    "window": 40,
    "volume_multiplier": "1.5",
}
KLINE_LIMIT = 180  # 40-bar warmup + wide evaluation window

LANE_LABEL = {
    "environment": "VENUE_DEMO",
    "real_money": False,
    "validation_state": "UNVALIDATED",
    "promotion_eligible": False,
    "execution_authority_note": "D-104 execution-measurement mode; demo funds only",
}


def _live_post_transport(url: str, headers: dict[str, str], body: bytes) -> bytes:
    """The single sanctioned order POST (D-104 stage 2). Demo-host-locked, https only."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != pf.DEMO_HOST:
        raise ValueError(f"POST transport refuses a non-demo URL: {url}")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        return bytes(response.read())


@dataclass(frozen=True)
class LaneIntent:
    """Typed demo order intent. The adapter refuses anything not expressible here."""

    side: str  # "Buy" | "Sell"
    qty: Decimal  # quote USDT for Buy, base coin for Sell
    unit: str  # "quoteCoin" | "baseCoin"
    signal_ref: str
    reason: str

    def __post_init__(self) -> None:
        if self.side not in {"Buy", "Sell"}:
            raise ValueError("side must be Buy or Sell")
        if self.unit not in {"quoteCoin", "baseCoin"}:
            raise ValueError("unit must be quoteCoin or baseCoin")
        if (self.side == "Buy") != (self.unit == "quoteCoin"):
            raise ValueError("Buy must be quote-sized; Sell must be base-sized")
        if self.qty <= 0:
            raise ValueError("qty must be positive")


def kill_switch_active() -> bool:
    return KILL_SWITCH.exists()


@contextmanager
def exclusive_lane_lock() -> Iterator[bool]:
    """Hold the single-lane lock for this process's lifetime.

    Two concurrent lanes would race on the cursor/inventory state and could double-trade, so
    only one may run. Yields False if another lane already holds it. The lock releases
    automatically when the process exits, so a crashed lane never wedges the next start.
    """
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    handle = LANE_LOCK.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat()}))
        handle.flush()
        os.fsync(handle.fileno())
        yield True
    finally:
        handle.close()


def _append_ledger(record: dict[str, Any]) -> None:
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    with ORDERS_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def quantize_down(qty: Decimal, step: Decimal) -> Decimal:
    return (qty / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_stop_qty_down(qty: Decimal, step: Decimal) -> Decimal:
    """Return a valid protective-sell quantity without ever exceeding inventory."""
    if not qty.is_finite() or qty <= 0:
        raise ValueError("stop quantity must be finite and positive")
    if not step.is_finite() or step <= 0:
        raise ValueError("instrument quantity step must be finite and positive")
    venue_qty = quantize_down(qty, step)
    if not venue_qty.is_finite() or venue_qty <= 0:
        raise ValueError("stop quantity is below the instrument quantity step")
    return venue_qty


def quantize_price_up(price: Decimal, tick_size: Decimal) -> Decimal:
    """Round a long-position stop up to the next valid tick (never loosen the risk boundary)."""
    if not price.is_finite() or price <= 0:
        raise ValueError("stop price must be finite and positive")
    if not tick_size.is_finite() or tick_size <= 0:
        raise ValueError("instrument price tick must be finite and positive")
    return (price / tick_size).to_integral_value(rounding=ROUND_CEILING) * tick_size


def instrument_qty_step(transport: pf.Transport) -> Decimal:
    url = f"{pf.DEMO_BASE}/v5/market/instruments-info?category=spot&symbol={SYMBOL}"
    payload = json.loads(transport(url, {}))
    try:
        raw_step = payload["result"]["list"][0]["lotSizeFilter"]["basePrecision"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("instrument quantity step is missing or invalid") from error
    try:
        step = Decimal(str(raw_step))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("instrument quantity step is missing or invalid") from error
    if not step.is_finite() or step <= 0:
        raise ValueError("instrument quantity step must be finite and positive")
    return step


def instrument_price_tick(transport: pf.Transport) -> Decimal:
    """Return the venue-declared price tick, failing closed on missing/invalid metadata."""
    url = f"{pf.DEMO_BASE}/v5/market/instruments-info?category=spot&symbol={SYMBOL}"
    payload = json.loads(transport(url, {}))
    try:
        raw_tick = payload["result"]["list"][0]["priceFilter"]["tickSize"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("instrument price tick is missing or invalid") from error
    try:
        tick = Decimal(str(raw_tick))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("instrument price tick is missing or invalid") from error
    if not tick.is_finite() or tick <= 0:
        raise ValueError("instrument price tick must be finite and positive")
    return tick


def last_price(transport: pf.Transport) -> Decimal:
    url = f"{pf.DEMO_BASE}/v5/market/tickers?category=spot&symbol={SYMBOL}"
    payload = json.loads(transport(url, {}))
    rows = payload.get("result", {}).get("list", [])
    return Decimal(str(rows[0]["lastPrice"])) if rows else Decimal("0")


def place(
    intent: LaneIntent,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: rt.PostTransport = _live_post_transport,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """Kill-switch -> caps -> quantize -> order -> poll -> reconcile -> ledger."""
    stamp = datetime.now(UTC).isoformat()
    base_record: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at": stamp,
        "symbol": SYMBOL,
        "side": intent.side,
        "unit": intent.unit,
        "signal_ref": intent.signal_ref,
        "reason": intent.reason,
        **LANE_LABEL,
    }
    if kill_switch_active():
        record = {**base_record, "ok": False, "stage": "kill_switch", "qty": str(intent.qty)}
        _append_ledger(record)
        return record
    qty = intent.qty
    if intent.side == "Buy":
        if qty > Decimal(str(rt.MAX_NOTIONAL)):
            raise ValueError(f"buy notional {qty} exceeds the {rt.MAX_NOTIONAL} USDT cap")
    else:
        price = last_price(get_transport)
        if price <= 0:
            record = {**base_record, "ok": False, "stage": "price_unavailable"}
            _append_ledger(record)
            return record
        if qty * price > SELL_MAX_NOTIONAL:
            raise ValueError(
                f"sell notional {qty * price:.2f} exceeds the {SELL_MAX_NOTIONAL} USDT cap"
            )
        qty = quantize_down(qty, instrument_qty_step(get_transport))
        if qty <= 0:
            record = {**base_record, "ok": False, "stage": "qty_below_step"}
            _append_ledger(record)
            return record
    before = rt.wallet(get_transport, api_key, secret, rt._now())
    order = {
        "category": "spot",
        "symbol": SYMBOL,
        "side": intent.side,
        "orderType": "Market",
        "qty": str(qty),
        "marketUnit": intent.unit,
    }
    placed = rt._order_create(post_transport, api_key, secret, rt._now(), pf.DEMO_BASE, order)
    if placed.get("retCode") != 0:
        record = {
            **base_record,
            "ok": False,
            "stage": "place",
            "qty": str(qty),
            "error": str(placed.get("retMsg")),
        }
        _append_ledger(record)
        return record
    order_id = str(placed.get("result", {}).get("orderId", ""))
    status = rt._poll_filled(get_transport, api_key, secret, order_id, SYMBOL, sleep)
    after = rt.wallet(get_transport, api_key, secret, rt._now())
    base_coin = SYMBOL.removesuffix("USDT")
    record = {
        **base_record,
        "ok": status.get("orderStatus") == "Filled",
        "stage": "done",
        "qty": str(qty),
        "order_id": order_id,
        "order_status": status.get("orderStatus"),
        "avg_price": status.get("avgPrice"),
        "cum_exec_qty": status.get("cumExecQty"),
        "fee": status.get("cumExecFee"),
        "reconcile": {
            f"{base_coin}_delta": round(rt._delta(before, after, base_coin), 8),
            "USDT_delta": round(rt._delta(before, after, "USDT"), 4),
        },
        # Absolute balances, not just the delta: the delta answers "what did this order
        # move", the snapshot answers "what is in the wallet". Both are needed to show
        # money, and only this process holds the credential to ask.
        "wallet_after": dict(after),
    }
    _append_ledger(record)
    return record


# --- Disaster-stop logic (pure; unit-tested offline in tests/test_demo_disaster_stop.py) ---


def disaster_stop_price(entry: Decimal) -> Decimal:
    """Price at which an open long is DEMO_DISASTER_STOP_PCT underwater from entry."""
    return entry * (Decimal("1") - DEMO_DISASTER_STOP_PCT)


def disaster_stop_triggered(entry: Decimal, mark: Decimal) -> bool:
    """True once the mark has fallen to/through the -15%-from-entry level."""
    return entry > 0 and mark > 0 and mark <= disaster_stop_price(entry)


def entry_price_from_ledger(records: list[dict[str, Any]]) -> Decimal | None:
    """Most recent filled long-entry avg price from ledger records, or None.

    Restart safety: a position opened before this process started has no entry in
    lane_state; the append-only orders ledger is the authoritative record of what was paid.
    """
    for record in reversed(records):
        if record.get("reason") == "ENTRY_LONG" and record.get("ok") and record.get("avg_price"):
            return Decimal(str(record["avg_price"]))
    return None


def resolve_entry_price(
    state: dict[str, Any], ledger_records: list[dict[str, Any]]
) -> Decimal | None:
    """Entry price for the open long: from state if present, else reconstructed from the ledger."""
    stored = state.get("entry_price")
    if stored not in (None, "", "0"):
        return Decimal(str(stored))
    return entry_price_from_ledger(ledger_records)


def stop_reconcile_action(
    lane_base: Decimal,
    entry: Decimal | None,
    resting: dict[str, Any] | None,
    price_tick: Decimal | None = None,
    qty_step: Decimal | None = None,
) -> str:
    """Idempotent venue-stop bookkeeping decision: 'place' | 'replace' | 'cancel' | 'noop'.

    Flat -> no stop should rest. Open with a known entry -> exactly one stop at the -15% level
    sized to the position; an already-matching resting stop is a no-op (idempotent), a stale
    level/qty is a replace. Unknown entry -> noop (the local stop still guards the position).
    """
    if resting and resting.get("state") == "AMBIGUOUS":
        return "reconcile"
    if resting and resting.get("state") == "BLOCKED_UNKNOWN_ORDER_ID":
        return "noop"
    if resting and resting.get("state") == "FILLED_PENDING_RECONCILIATION":
        return "noop"
    if lane_base <= 0:
        return "cancel" if resting else "noop"
    if entry is None or entry <= 0:
        return "noop"
    if resting is None:
        return "place"
    expected_trigger = disaster_stop_price(entry)
    if price_tick is not None:
        expected_trigger = quantize_price_up(expected_trigger, price_tick)
    expected_qty = lane_base
    if qty_step is not None:
        expected_qty = quantize_stop_qty_down(lane_base, qty_step)
    same = (
        Decimal(str(resting.get("trigger_price", "0"))) == expected_trigger
        and Decimal(str(resting.get("base_qty", "0"))) == expected_qty
    )
    return "noop" if same else "replace"


def _read_ledger_records() -> list[dict[str, Any]]:
    if not ORDERS_LEDGER.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in ORDERS_LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _append_action(record: dict[str, Any]) -> None:
    ACTIONS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with ACTIONS_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


# --- Venue-resting stop adapter (thin; same demo-host POST path, no new credential/venue) ---


def place_stop_order(
    base_qty: Decimal,
    trigger_price: Decimal,
    price_tick: Decimal,
    qty_step: Decimal,
    api_key: str,
    secret: str,
    *,
    post_transport: rt.PostTransport = _live_post_transport,
) -> dict[str, Any]:
    """Rest a demo Sell stop at trigger_price via the quarantined order transport (rt.place_stop).

    The order-endpoint literals stay confined to scripts/demo_roundtrip.py; the lane only binds
    the symbol/params. Demo host only, no new authority.
    """
    venue_trigger = quantize_price_up(trigger_price, price_tick)
    venue_qty = quantize_stop_qty_down(base_qty, qty_step)
    return rt.place_stop(
        post_transport,
        api_key,
        secret,
        rt._now(),
        pf.DEMO_BASE,
        symbol=SYMBOL,
        trigger_price=str(venue_trigger),
        base_qty=str(venue_qty),
    )


def cancel_stop_order(
    order_id: str,
    api_key: str,
    secret: str,
    *,
    post_transport: rt.PostTransport = _live_post_transport,
) -> dict[str, Any]:
    """Cancel a resting demo stop by order id via the quarantined transport (rt.cancel_order)."""
    return rt.cancel_order(
        post_transport, api_key, secret, rt._now(), pf.DEMO_BASE, order_id=order_id, symbol=SYMBOL
    )


_ACTIVE_STOP_STATUSES = {"New", "Untriggered"}
_CLEARED_STOP_STATUSES = {"Cancelled", "Deactivated", "Rejected"}


def stop_order_status(
    order_id: str, api_key: str, secret: str, transport: pf.Transport
) -> dict[str, Any]:
    """Fetch one stop through a fixed, non-overridable spot StopOrder query.

    The response does not always echo `orderFilter`; this request provenance is therefore
    part of conditional-order identity together with the strict response checks below.
    """
    response = pf._signed_get(
        transport,
        pf.DEMO_BASE,
        "/v5/order/realtime",
        {
            "category": "spot",
            "symbol": SYMBOL,
            "orderId": order_id,
            "orderFilter": "StopOrder",
        },
        api_key,
        secret,
        rt._now(),
    )
    rows = response.get("result", {}).get("list", [])
    return next(
        (row for row in rows if isinstance(row, dict) and str(row.get("orderId", "")) == order_id),
        {},
    )


def _confirmed_stop_state(order_id: str, api_key: str, secret: str, transport: pf.Transport) -> str:
    """Return active/cleared/unknown; empty realtime responses are never assumed cancelled."""
    return _confirmed_stop_snapshot(order_id, api_key, secret, transport)[0]


def _confirmed_stop_snapshot(
    order_id: str,
    api_key: str,
    secret: str,
    transport: pf.Transport,
    *,
    expected_trigger: Any = None,
    expected_qty: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Return normalized state plus the exact venue row used for that conclusion."""
    try:
        row = stop_order_status(order_id, api_key, secret, transport)
        if str(row.get("orderId", "")) != order_id:
            return "unknown", row
        status = str(row.get("orderStatus", ""))
    except Exception as error:  # noqa: BLE001 - uncertainty must be represented, not guessed
        print(f"venue stop status unavailable for {order_id}: {error}", file=sys.stderr)
        return "unknown", {}
    if status in _ACTIVE_STOP_STATUSES:
        if _protective_venue_row_identity(
            row,
            order_id,
            expected_trigger=expected_trigger,
            expected_qty=expected_qty,
        ):
            return "active", row
        return "unknown", row
    if status == "Filled":
        return "filled", row
    if status in _CLEARED_STOP_STATUSES:
        return "cleared", row
    return "unknown", row


def _protective_venue_row_identity(
    row: dict[str, Any],
    requested_order_id: str | None,
    *,
    expected_trigger: Any = None,
    expected_qty: Any = None,
) -> bool:
    """Strict spot identity for a row returned by the fixed StopOrder query above."""
    trigger_direction = row.get("triggerDirection")
    if (
        (requested_order_id is not None and str(row.get("orderId", "")) != requested_order_id)
        or row.get("symbol") != SYMBOL
        or row.get("side") != "Sell"
        or row.get("orderType") != "Market"
        or ("orderFilter" in row and row.get("orderFilter") != "StopOrder")
        or row.get("stopOrderType") != "Stop"
        or not isinstance(trigger_direction, int)
        or isinstance(trigger_direction, bool)
        # Spot reports 0 (venue-default/unspecified); 2 is also accepted for a falling
        # trigger. Conditional identity comes from the fixed filtered query,
        # stopOrderType=Stop, and the exact retained trigger bound—not direction alone.
        or trigger_direction not in {0, 2}
        # Observed spot rows include marketUnit, but some responses may omit it. When
        # present, it must prove the quantity is denominated in the base coin.
        or ("marketUnit" in row and row.get("marketUnit") != "baseCoin")
    ):
        return False
    try:
        venue_trigger = Decimal(str(row["triggerPrice"]))
        venue_qty = Decimal(str(row["qty"]))
        bound_trigger = Decimal(str(expected_trigger)) if expected_trigger is not None else None
        bound_qty = Decimal(str(expected_qty)) if expected_qty is not None else None
    except (KeyError, ArithmeticError, ValueError):
        return False
    if not all(value.is_finite() and value > 0 for value in (venue_trigger, venue_qty)):
        return False
    return (bound_trigger is None or venue_trigger == bound_trigger) and (
        bound_qty is None or venue_qty == bound_qty
    )


def _strict_positive_decimal(value: Any) -> Decimal | None:
    """Parse bound venue evidence without accepting bools, NaN, infinity, or zero."""
    if isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _canonical_order_id(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    return value if _ORDER_ID.fullmatch(value) else None


def _ambiguous_expected_records(
    resting: dict[str, Any],
) -> dict[str, tuple[Decimal, Decimal]] | None:
    raw_ids = resting.get("order_ids")
    records = resting.get("order_records")
    if not isinstance(raw_ids, list) or not raw_ids or not isinstance(records, dict):
        return None
    if any(_canonical_order_id(value) is None for value in raw_ids):
        return None
    order_ids = [str(value) for value in raw_ids]
    if len(set(order_ids)) != len(order_ids):
        return None
    expected: dict[str, tuple[Decimal, Decimal]] = {}
    for order_id in order_ids:
        record = records.get(order_id)
        if not isinstance(record, dict):
            return None
        trigger = _strict_positive_decimal(record.get("trigger_price"))
        qty = _strict_positive_decimal(record.get("base_qty"))
        if trigger is None or qty is None:
            return None
        expected[order_id] = (trigger, qty)
    return expected


def _active_stop_record(
    order_id: str,
    trigger: Decimal,
    risk_boundary: Decimal,
    base_qty: Decimal,
    position_base_qty: Decimal,
    risk_fraction: Decimal,
    price_tick: Decimal,
) -> dict[str, Any]:
    return {
        "state": "ACTIVE",
        "order_id": order_id,
        "trigger_price": str(trigger),
        "risk_boundary_price": str(risk_boundary),
        "base_qty": str(base_qty),
        "position_base_qty": str(position_base_qty),
        # Bind projection/audit semantics to the exact policy and venue metadata used
        # for this order. Consumers must never infer either value from current defaults.
        "risk_fraction": str(risk_fraction),
        "price_tick": str(price_tick),
    }


def _filled_stop_record(
    resting: dict[str, Any], order_id: str, status: str = "Filled"
) -> dict[str, Any]:
    """Latch a filled tracked stop until a separate reconciliation workflow resolves it."""
    record = dict(resting)
    record.update(
        {
            "state": "FILLED_PENDING_RECONCILIATION",
            "filled_order_id": order_id,
            "filled_order_status": status,
        }
    )
    return record


def preflight_tracked_stop(
    resting: dict[str, Any] | None,
    api_key: str,
    secret: str,
    transport: pf.Transport,
) -> tuple[dict[str, Any] | None, bool, dict[str, Any] | None]:
    """Resolve status, POST safety, and a non-ambiguous active venue confirmation row."""
    if resting is None:
        return None, True, None
    if not isinstance(resting, dict):
        return None, False, None
    if not resting:
        return resting, False, None
    state = resting.get("state")
    if state in {"BLOCKED_UNKNOWN_ORDER_ID", "FILLED_PENDING_RECONCILIATION"}:
        return resting, False, None
    if state == "AMBIGUOUS":
        expected_by_order = _ambiguous_expected_records(resting)
        if expected_by_order is None:
            return resting, False, None
    elif state in {None, "ACTIVE"}:
        order_id = _canonical_order_id(resting.get("order_id"))
        if order_id is None:
            return resting, False, None
        expected_trigger = _strict_positive_decimal(resting.get("trigger_price"))
        expected_qty = _strict_positive_decimal(resting.get("base_qty"))
        if expected_trigger is None or expected_qty is None:
            return resting, False, None
        expected_by_order = {order_id: (expected_trigger, expected_qty)}
    else:
        return resting, False, None

    snapshots: dict[str, tuple[str, dict[str, Any]]] = {}
    for order_id, (expected_trigger, expected_qty) in expected_by_order.items():
        snapshots[order_id] = _confirmed_stop_snapshot(
            order_id,
            api_key,
            secret,
            transport,
            expected_trigger=expected_trigger,
            expected_qty=expected_qty,
        )
    states = {order_id: snapshot[0] for order_id, snapshot in snapshots.items()}
    filled = [order_id for order_id, status in states.items() if status == "filled"]
    if filled:
        return _filled_stop_record(resting, filled[0]), False, None
    active = [order_id for order_id, status in states.items() if status == "active"]
    unknown = [order_id for order_id, status in states.items() if status == "unknown"]
    if state != "AMBIGUOUS":
        if active:
            return resting, True, snapshots[active[0]][1]
        if unknown:
            return resting, False, None
        return None, True, None
    if len(active) == 1 and not unknown:
        resolved = dict(resting.get("order_records", {}).get(active[0], resting))
        resolved.pop("order_ids", None)
        resolved.pop("order_records", None)
        resolved.pop("ambiguity_reason", None)
        resolved.update({"state": "ACTIVE", "order_id": active[0]})
        return resolved, True, None
    if not active and not unknown:
        return None, True, None
    return resting, False, None


def _backfill_confirmed_stop_metadata(
    resting: dict[str, Any] | None,
    venue_confirmation: dict[str, Any] | None,
    lane_base: Decimal,
    entry: Decimal,
    price_tick: Decimal,
    qty_step: Decimal,
) -> dict[str, Any] | None:
    """Enrich a legacy record only when the venue row confirms this exact active stop."""
    if not resting or (
        resting.get("risk_fraction") is not None and resting.get("price_tick") is not None
    ):
        return resting
    if resting.get("state") not in {None, "ACTIVE"} or not venue_confirmation:
        return resting
    order_id = str(resting.get("order_id", "")).strip()
    if (
        not order_id
        or str(venue_confirmation.get("orderStatus", "")) not in _ACTIVE_STOP_STATUSES
        or not _protective_venue_row_identity(
            venue_confirmation,
            order_id,
            expected_trigger=resting.get("trigger_price"),
            expected_qty=resting.get("base_qty"),
        )
    ):
        return resting
    try:
        boundary = disaster_stop_price(entry)
        expected_trigger = quantize_price_up(boundary, price_tick)
        expected_qty = quantize_stop_qty_down(lane_base, qty_step)
        venue_trigger = Decimal(str(venue_confirmation["triggerPrice"]))
        venue_qty = Decimal(str(venue_confirmation["qty"]))
        retained_trigger = Decimal(str(resting["trigger_price"]))
        retained_qty = Decimal(str(resting["base_qty"]))
    except (KeyError, ArithmeticError, ValueError):
        return resting
    if not all(value.is_finite() and value > 0 for value in (venue_trigger, venue_qty)):
        return resting
    if (
        venue_trigger != expected_trigger
        or retained_trigger != expected_trigger
        or venue_qty != expected_qty
        or retained_qty != expected_qty
    ):
        return resting
    return {
        **resting,
        "risk_boundary_price": str(boundary),
        "position_base_qty": str(lane_base),
        "risk_fraction": str(DEMO_DISASTER_STOP_PCT),
        "price_tick": str(price_tick),
    }


def _ambiguous_stop_record(
    order_ids: list[str],
    template: dict[str, Any] | None,
    reason: str,
    order_records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record = dict(template or {})
    records = dict(record.get("order_records", {}))
    if record.get("order_id"):
        records[str(record["order_id"])] = dict(record)
    records.update(order_records or {})
    record.pop("order_id", None)
    record.update(
        {
            "state": "AMBIGUOUS" if order_ids else "BLOCKED_UNKNOWN_ORDER_ID",
            "order_ids": list(dict.fromkeys(order_id for order_id in order_ids if order_id)),
            "order_records": records,
            "ambiguity_reason": reason,
        }
    )
    return record


def _reconcile_ambiguous_stop(
    resting: dict[str, Any], api_key: str, secret: str, transport: pf.Transport
) -> dict[str, Any] | None:
    expected_by_order = _ambiguous_expected_records(resting)
    if expected_by_order is None:
        return resting
    snapshots = {
        order_id: _confirmed_stop_snapshot(
            order_id,
            api_key,
            secret,
            transport,
            expected_trigger=trigger,
            expected_qty=qty,
        )
        for order_id, (trigger, qty) in expected_by_order.items()
    }
    states = {order_id: snapshot[0] for order_id, snapshot in snapshots.items()}
    filled = [order_id for order_id, state in states.items() if state == "filled"]
    if filled:
        return _filled_stop_record(resting, filled[0])
    active = [order_id for order_id, state in states.items() if state == "active"]
    unknown = [order_id for order_id, state in states.items() if state == "unknown"]
    if len(active) == 1 and not unknown:
        resolved = dict(resting.get("order_records", {}).get(active[0], resting))
        resolved.pop("order_ids", None)
        resolved.pop("order_records", None)
        resolved.pop("ambiguity_reason", None)
        resolved.update({"state": "ACTIVE", "order_id": active[0]})
        return resolved
    if not active and not unknown:
        return None
    return _ambiguous_stop_record(
        active + unknown,
        resting,
        "multiple or unconfirmed stop orders remain after status reconciliation",
    )


def apply_stop_decision(
    decision: str,
    resting: dict[str, Any] | None,
    lane_base: Decimal,
    entry: Decimal | None,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport = pf._urllib_transport,
    price_tick: Decimal | None = None,
    qty_step: Decimal | None = None,
    post_transport: rt.PostTransport = _live_post_transport,
) -> dict[str, Any] | None:
    """Execute a stop_reconcile_action decision; return the new resting-stop record (or None).

    Best-effort secondary protection: metadata and replacement are validated before any existing
    stop is touched. Replacement places the new protection first, then cancels the old stop.
    """
    if decision == "reconcile" and resting:
        return _reconcile_ambiguous_stop(resting, api_key, secret, get_transport)
    if decision == "noop":
        return resting
    if decision == "cancel":
        if not resting or not resting.get("order_id"):
            return None
        try:
            cancelled = cancel_stop_order(
                str(resting["order_id"]), api_key, secret, post_transport=post_transport
            )
        except Exception as error:  # noqa: BLE001 - preserve state for retry
            print(f"venue stop cancel failed: {error}", file=sys.stderr)
            return resting
        if cancelled.get("retCode") != 0:
            print(f"venue stop cancel rejected: {cancelled.get('retMsg')}", file=sys.stderr)
            return resting
        state = _confirmed_stop_state(str(resting["order_id"]), api_key, secret, get_transport)
        if state == "cleared":
            return None
        if state == "filled":
            return _filled_stop_record(resting, str(resting["order_id"]))
        if state == "active":
            return resting
        return _ambiguous_stop_record(
            [str(resting["order_id"])], resting, "cancel acknowledged but not confirmed cleared"
        )

    if decision not in {"place", "replace"} or entry is None or lane_base <= 0:
        return resting

    risk_boundary = disaster_stop_price(entry)
    try:
        resolved_tick = (
            price_tick if price_tick is not None else instrument_price_tick(get_transport)
        )
        resolved_qty_step = qty_step if qty_step is not None else instrument_qty_step(get_transport)
        venue_trigger = quantize_price_up(risk_boundary, resolved_tick)
        venue_qty = quantize_stop_qty_down(lane_base, resolved_qty_step)
    except Exception as error:  # noqa: BLE001 - metadata failure must never mutate venue state
        print(f"venue stop metadata invalid: {error}", file=sys.stderr)
        return resting

    try:
        placed = place_stop_order(
            lane_base,
            risk_boundary,
            resolved_tick,
            resolved_qty_step,
            api_key,
            secret,
            post_transport=post_transport,
        )
    except Exception as error:  # noqa: BLE001 - preserve existing stop on place failure
        print(f"venue stop place failed: {error}", file=sys.stderr)
        return resting
    if placed.get("retCode") != 0:
        print(f"venue stop place rejected: {placed.get('retMsg')}", file=sys.stderr)
        return resting

    new_order_id = str(placed.get("result", {}).get("orderId", "")).strip()
    if not new_order_id:
        blocked_template = {
            "trigger_price": str(venue_trigger),
            "risk_boundary_price": str(risk_boundary),
            "base_qty": str(venue_qty),
            "position_base_qty": str(lane_base),
            "risk_fraction": str(DEMO_DISASTER_STOP_PCT),
            "price_tick": str(resolved_tick),
        }
        blocked = _ambiguous_stop_record(
            [str(resting["order_id"])] if resting and resting.get("order_id") else [],
            resting or blocked_template,
            "create acknowledged without an orderId; automated placement blocked",
        )
        blocked["state"] = "BLOCKED_UNKNOWN_ORDER_ID"
        return blocked

    new_resting = _active_stop_record(
        new_order_id,
        venue_trigger,
        risk_boundary,
        venue_qty,
        lane_base,
        DEMO_DISASTER_STOP_PCT,
        resolved_tick,
    )
    new_state, _new_snapshot = _confirmed_stop_snapshot(
        new_order_id,
        api_key,
        secret,
        get_transport,
        expected_trigger=venue_trigger,
        expected_qty=venue_qty,
    )
    old_order_id = str(resting.get("order_id", "")) if resting else ""
    if new_state == "cleared":
        return resting
    if new_state == "filled":
        return _filled_stop_record(new_resting, new_order_id)
    if new_state == "unknown":
        known_ids = ([old_order_id] if old_order_id else []) + [new_order_id]
        return _ambiguous_stop_record(
            known_ids,
            resting or new_resting,
            "create acknowledged but active stop not confirmed",
            {new_order_id: new_resting},
        )
    if decision == "place" or not old_order_id:
        return new_resting

    old_state = "unknown"
    try:
        cancelled = cancel_stop_order(old_order_id, api_key, secret, post_transport=post_transport)
        if cancelled.get("retCode") == 0:
            old_state = _confirmed_stop_state(old_order_id, api_key, secret, get_transport)
        else:
            print(f"venue old-stop cancel rejected: {cancelled.get('retMsg')}", file=sys.stderr)
    except Exception as error:  # noqa: BLE001 - rollback new stop and preserve known IDs
        print(f"venue old-stop cancel failed: {error}", file=sys.stderr)

    if old_state == "cleared":
        return new_resting
    if old_state == "filled":
        replacement_set = _ambiguous_stop_record(
            [old_order_id, new_order_id],
            resting,
            "tracked old stop filled during replacement",
            {new_order_id: new_resting},
        )
        return _filled_stop_record(replacement_set, old_order_id)

    rollback_state = "unknown"
    try:
        rollback = cancel_stop_order(new_order_id, api_key, secret, post_transport=post_transport)
        if rollback.get("retCode") == 0:
            rollback_state = _confirmed_stop_state(new_order_id, api_key, secret, get_transport)
        else:
            print(
                f"venue replacement rollback rejected: {rollback.get('retMsg')}",
                file=sys.stderr,
            )
    except Exception as rollback_error:  # noqa: BLE001 - both IDs remain explicitly ambiguous
        print(f"venue replacement rollback failed: {rollback_error}", file=sys.stderr)

    if rollback_state == "cleared" and old_state == "active":
        return resting
    if rollback_state == "filled":
        replacement_set = _ambiguous_stop_record(
            [old_order_id, new_order_id],
            resting,
            "replacement stop filled during rollback",
            {new_order_id: new_resting},
        )
        return _filled_stop_record(replacement_set, new_order_id)
    remaining_ids = [old_order_id]
    if rollback_state != "cleared":
        remaining_ids.append(new_order_id)
    return _ambiguous_stop_record(
        remaining_ids,
        resting,
        "replacement cancellation/rollback not fully confirmed",
        {new_order_id: new_resting},
    )


def read_state() -> dict[str, Any]:
    if not LANE_STATE.is_file():
        return {"lane_base": "0", "cursor": None}
    payload = json.loads(LANE_STATE.read_text())
    return payload if isinstance(payload, dict) else {"lane_base": "0", "cursor": None}


def write_state(state: dict[str, Any]) -> None:
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LANE_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(LANE_STATE)


def fetch_closed_bars(transport: pf.Transport, limit: int = KLINE_LIMIT) -> tuple[MarketBar, ...]:
    """Public demo-venue 1h klines -> chronological closed MarketBars (forming bar dropped)."""
    url = f"{pf.DEMO_BASE}/v5/market/kline?category=spot&symbol={SYMBOL}&interval=60&limit={limit}"
    rows = list(reversed(json.loads(transport(url, {}))["result"]["list"]))[:-1]
    market = Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BYBIT_DEMO_SPOT"),
        InstrumentId("ETH-USDT.BYBIT_DEMO_SPOT"),
        Timeframe.H1,
        DatasetId("DS-BYBIT-DEMO-ETHUSDT-1H-LIVE"),
    )
    provenance = Provenance((DomainRef("EV-BYBIT-DEMO-KLINE-LIVE"),))
    now = datetime.now(UTC)
    return tuple(
        MarketBar(
            market=market,
            open_time=(open_time := datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)),
            close_time=open_time + timedelta(hours=1),
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            volume=Decimal(row[5]),
            created_at=now,
            creator_type=CreatorType.SYSTEM,
            provenance=provenance,
        )
        for row in rows
    )


def canonical_signals(bars: tuple[MarketBar, ...]) -> list[Any]:
    raw_spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    spec = parse_spec(raw_spec)
    version = create_version(spec, SPEC_PARAMETERS)
    return list(
        evaluate_strategy_signals(
            spec=spec,
            bars=bars,
            strategy_version_ref=StrategyVersionId(version.sv_id),
            run_ref=RunId("RUN-DEMO-ETH-LANE-V1"),
            created_at=datetime.now(UTC),
            creator_type=CreatorType.SYSTEM,
            provenance=Provenance((DomainRef("EV-BYBIT-DEMO-KLINE-LIVE"),)),
        )
    )


def rule_levels(bars: tuple[MarketBar, ...]) -> dict[str, Any]:
    """Live values of the rule that actually governs entry and exit.

    This strategy has no stop loss and no take profit — its spec sets both to null and
    exits on `close < donchian_lower`. Surfacing that band is the honest equivalent of a
    stop level: it is the price at which the lane will actually sell. Publishing a
    fabricated stop instead would describe a strategy that is not the one running.
    """
    from tios.strategy.evaluator import _indicator_contexts

    if not bars:
        return {}
    raw_spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    spec = parse_spec(raw_spec)
    contexts = _indicator_contexts(spec, bars)
    context = contexts[-1] if contexts else None
    if context is None:
        return {"warming_up": True}

    return {
        "warming_up": False,
        "close": str(bars[-1].close),
        "donchian_upper": str(context.get("donchian_upper", "")),
        "donchian_lower": str(context.get("donchian_lower", "")),
        "volume_threshold": str(context.get("volume_threshold", "")),
        "volume_base": str(context.get("volume_base", "")),
        "bar_close_time": bars[-1].close_time.isoformat(),
    }


def run_cycle(
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: rt.PostTransport = _live_post_transport,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """One evaluation cycle: fresh signals newer than the cursor drive at most one action."""
    state = read_state()
    cursor = state.get("cursor")
    lane_base = Decimal(str(state.get("lane_base", "0")))
    # Entry price drives the -15% stop. From state normally; reconstructed from the append-only
    # ledger for a position opened before this process started (restart safety).
    entry_price = resolve_entry_price(state, _read_ledger_records())
    stored_resting_stop = state.get("resting_stop")
    resting_stop, post_paths_safe, venue_stop_confirmation = preflight_tracked_stop(
        stored_resting_stop, api_key, secret, get_transport
    )
    if resting_stop is not stored_resting_stop and (
        resting_stop and resting_stop.get("state") == "FILLED_PENDING_RECONCILIATION"
    ):
        # Persist before any later read can fail, so a restart cannot forget the filled-stop latch.
        write_state({**state, "resting_stop": resting_stop})
    bars = fetch_closed_bars(get_transport)
    signals = canonical_signals(bars)
    fresh = [s for s in signals if cursor is None or s.observed_at.isoformat() > cursor]
    action: dict[str, Any] | None = None
    if cursor is None:
        fresh = []  # first start: arm the cursor, trade only future transitions
    for signal in fresh if post_paths_safe else ():
        side = signal.side.value  # BUY | SELL
        if side == "BUY" and lane_base == 0:
            action = place(
                LaneIntent("Buy", BUY_QUOTE_USDT, "quoteCoin", str(signal.signal_id), "ENTRY_LONG"),
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
            )
            if action.get("ok"):
                lane_base += Decimal(str(action["reconcile"]["ETH_delta"]))
                entry_price = Decimal(str(action["avg_price"])) if action.get("avg_price") else None
        elif side == "SELL" and lane_base > 0:
            action = place(
                LaneIntent("Sell", lane_base, "baseCoin", str(signal.signal_id), "EXIT_LONG"),
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
            )
            if action.get("ok"):
                lane_base = Decimal("0")
                entry_price = None
    latest_bar_close = bars[-1].close_time.isoformat() if bars else cursor

    # Disaster-stop guard — runs every cycle independent of strategy signals, so it protects a
    # position opened before this process started and one no fresh signal would exit. The local
    # close is the primary tail insurance; the venue-resting stop below is the process-death backup.
    stop_event: dict[str, Any] | None = None
    try:
        mark = last_price(get_transport)
    except Exception as error:  # noqa: BLE001 - no mark means no basis to trigger; skip this cycle
        print(f"disaster-stop mark unavailable: {error}", file=sys.stderr)
        mark = Decimal("0")
    if (
        post_paths_safe
        and lane_base > 0
        and entry_price is not None
        and disaster_stop_triggered(entry_price, mark)
    ):
        closed = place(
            LaneIntent("Sell", lane_base, "baseCoin", "DISASTER_STOP_LOCAL", "DISASTER_STOP"),
            api_key,
            secret,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
        )
        if closed.get("ok"):
            stop_event = {
                "action": "DISASTER_STOP",
                "decided_at": datetime.now(UTC).isoformat(),
                "detail": (
                    f"local -{DEMO_DISASTER_STOP_PCT * 100:.0f}% disaster-stop fired: entry "
                    f"{entry_price} mark {mark} stop_price {disaster_stop_price(entry_price)}; "
                    f"closed via demo sell {closed.get('order_id')}"
                ),
                "environment": "VENUE_DEMO",
                "idempotency_key": str(closed.get("order_id") or latest_bar_close),
                "real_money": False,
                "schema_version": 1,
                "source": "demo_lane_disaster_stop",
            }
            _append_action(stop_event)
            lane_base = Decimal("0")
            entry_price = None
        action = action or closed

    # Venue-resting stop bookkeeping: exactly one stop at the -15% level while a position is open,
    # cancelled when flat. Idempotent — compare the actual venue-quantized trigger and quantity.
    price_tick: Decimal | None = None
    qty_step: Decimal | None = None
    if not post_paths_safe:
        # Preflight already performed one fully bound reconciliation read. Never issue a
        # second read that could promote a different snapshot in the same cycle.
        decision = "noop"
    elif lane_base > 0 and entry_price is not None:
        try:
            price_tick = instrument_price_tick(get_transport)
            qty_step = instrument_qty_step(get_transport)
            decision = stop_reconcile_action(
                lane_base, entry_price, resting_stop, price_tick, qty_step
            )
        except Exception as error:  # noqa: BLE001 - keep loop alive and venue state untouched
            print(f"venue stop metadata invalid: {error}", file=sys.stderr)
            decision = "noop"  # fail closed: do not create, cancel, or replace any venue stop
    else:
        decision = stop_reconcile_action(lane_base, entry_price, resting_stop)
    if (
        decision == "noop"
        and entry_price is not None
        and price_tick is not None
        and qty_step is not None
    ):
        resting_stop = _backfill_confirmed_stop_metadata(
            resting_stop,
            venue_stop_confirmation,
            lane_base,
            entry_price,
            price_tick,
            qty_step,
        )
    resting_stop = apply_stop_decision(
        decision,
        resting_stop,
        lane_base,
        entry_price,
        api_key,
        secret,
        get_transport=get_transport,
        price_tick=price_tick,
        qty_step=qty_step,
        post_transport=post_transport,
    )

    write_state(
        {
            "lane_base": str(lane_base),
            "cursor": latest_bar_close,
            "entry_price": str(entry_price) if entry_price is not None else None,
            "resting_stop": resting_stop,
        }
    )

    # Wallet and mark are captured every cycle, not only when an order fills. A lane that
    # trades rarely would otherwise show balances frozen at the last fill, and a stale
    # number presented as current is worse than no number.
    wallet_snapshot: dict[str, str] = {}
    mark_price = "0"
    try:
        wallet_snapshot = dict(rt.wallet(get_transport, api_key, secret, rt._now()))
        mark_price = str(last_price(get_transport))
    except Exception as error:  # noqa: BLE001 - snapshot is informational, never fatal
        wallet_snapshot = {}
        mark_price = "0"
        print(f"wallet/mark snapshot unavailable: {error}", file=sys.stderr)

    heartbeat = {
        "schema_version": 2,
        "at": datetime.now(UTC).isoformat(),
        "candidate": "ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1",
        "latest_closed_bar": latest_bar_close,
        "signals_in_window": len(signals),
        "fresh_signals": len(fresh),
        "lane_base": str(lane_base),
        "kill_switch": kill_switch_active(),
        "action": action,
        "wallet": wallet_snapshot,
        "mark_price": mark_price,
        "rule_levels": rule_levels(bars),
        "entry_price": str(entry_price) if entry_price is not None else None,
        "disaster_stop_price": str(disaster_stop_price(entry_price))
        if entry_price is not None
        else None,
        "disaster_stop_event": stop_event,
        "resting_stop": resting_stop,
        **LANE_LABEL,
    }
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT.with_suffix(".tmp")
    tmp.write_text(json.dumps(heartbeat, sort_keys=True, indent=2))
    tmp.replace(HEARTBEAT)
    return heartbeat


def main() -> int:
    parser = argparse.ArgumentParser(description="D-104 ETH demo measurement lane.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one evaluation cycle")
    mode.add_argument("--loop", action="store_true", help="run hourly until killed")
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    with exclusive_lane_lock() as acquired:
        if not acquired:
            print("another ETH demo lane is already running — refusing to start a second one.")
            return 3
        pre = pf.preflight(pf._urllib_transport, api_key, secret)
        if not pre.get("ok"):
            print(json.dumps({"ok": False, "stage": "preflight", "preflight": pre}, indent=2))
            return 1
        mode_label = "loop" if args.loop else "once"
        print(f"preflight GREEN on {pre['host']} — ETH measurement lane ({mode_label})")
        while True:
            heartbeat = run_cycle(api_key, secret)
            print(json.dumps(heartbeat, indent=2, sort_keys=True))
            if args.once:
                return 0
            if kill_switch_active():
                print("KILL_SWITCH present — lane stopped.")
                return 0
            now = datetime.now(UTC)
            next_hour = (now + timedelta(hours=1)).replace(minute=1, second=0, microsecond=0)
            time.sleep(max(60.0, (next_hour - now).total_seconds()))


if __name__ == "__main__":
    sys.exit(main())
