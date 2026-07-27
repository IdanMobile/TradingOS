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
import hashlib
import hmac
import json
import os
import re
import secrets
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
from typing import Any, cast

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import tios.evidence.demo_decision_evidence_v2 as stage_b  # noqa: E402
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

# Rolling per-coin close series persisted next to the heartbeat so the dashboard can draw a real
# price chart instead of inventing one. 288 points = 24h of 5m bars (the confluence lane's fastest
# reference timeframe); on the 1h ETH/multi lane the same cap is 12 days. Bounded so the file can
# never grow without limit. ponytail: one fixed cap for every timeframe, split it per-interval only
# if a lane ever needs a different window.
PRICE_HISTORY_MAX_POINTS = 288

# Stage B default-disabled evidence root. Absent => NOT_ACTIVATED => the lane behaves exactly as it
# does today (no sink, no latch, no client key). The runtime root is created only by a later,
# separately gated activation ceremony — never by this module or its tests.
STAGE_B_REPO_ROOT = pf.ROOT

SYMBOL = "ETHUSDT"
BUY_QUOTE_USDT = Decimal("25")
SELL_MAX_NOTIONAL = Decimal("120")  # independent sell cap (stage-1 review item)
FALLBACK_QTY_STEP = Decimal("0.00001")

# Bounded set of liquid demo coins for the multi-coin execution-measurement lane. Each trades the
# SAME already-screened volume-confirmed Donchian breakout, independently, under the SHARED kill
# switch and the SHARED total-capital cap below. Edit this list to change the universe. ETHUSDT is
# the default single-symbol lane; every coin uses the same BUY_QUOTE_USDT (25) per entry.
DEMO_COINS = [
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
]
# Shared cap on the sum of per-coin buy notional across the whole multi-coin lane. A new entry that
# would push total open buy notional past this is skipped (logged, never an error); risk-reducing
# exits/stops on already-open coins are NEVER gated by it. Demo/fake money only.
TOTAL_DEMO_CAPITAL_USDT = Decimal("300")
_ORDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")


class LocalRejection(ValueError):
    """A DETERMINISTIC pre-send local rejection (notional cap / quantize below-step, non-positive).

    We KNOW no venue POST occurred when this is raised. It subclasses ValueError so every existing
    `except ValueError` still catches it and the NOT_ACTIVATED path stays byte-identical. Stage B's
    risk-reduction `do_post` catches ONLY this — never a bare ValueError — so a POST-SEND failure
    (a malformed create response `json.loads` / a `_delta` wallet parse) can never be misclassified
    as a no-send and roll a reservation back into a duplicate create.
    """


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
    """Return a valid protective-sell quantity without ever exceeding inventory.

    Below-step / non-positive inputs raise `LocalRejection` (a ValueError subclass): these are
    deterministic pre-send rejections, so the Stage B stop path can fall back to the compensating
    control instead of freezing a POST_UNKNOWN reservation or crashing the lane.
    """
    if not qty.is_finite() or qty <= 0:
        raise LocalRejection("stop quantity must be finite and positive")
    if not step.is_finite() or step <= 0:
        raise LocalRejection("instrument quantity step must be finite and positive")
    venue_qty = quantize_down(qty, step)
    if not venue_qty.is_finite() or venue_qty <= 0:
        raise LocalRejection("stop quantity is below the instrument quantity step")
    return venue_qty


def quantize_price_up(price: Decimal, tick_size: Decimal) -> Decimal:
    """Round a long-position stop up to the next valid tick (never loosen the risk boundary).

    Non-positive price/tick raise `LocalRejection` (a ValueError subclass) — a deterministic
    pre-send rejection the Stage B stop path handles by falling back rather than crashing.
    """
    if not price.is_finite() or price <= 0:
        raise LocalRejection("stop price must be finite and positive")
    if not tick_size.is_finite() or tick_size <= 0:
        raise LocalRejection("instrument price tick must be finite and positive")
    return (price / tick_size).to_integral_value(rounding=ROUND_CEILING) * tick_size


def instrument_qty_step(transport: pf.Transport, symbol: str = SYMBOL) -> Decimal:
    url = f"{pf.DEMO_BASE}/v5/market/instruments-info?category=spot&symbol={symbol}"
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


def instrument_price_tick(transport: pf.Transport, symbol: str = SYMBOL) -> Decimal:
    """Return the venue-declared price tick, failing closed on missing/invalid metadata."""
    url = f"{pf.DEMO_BASE}/v5/market/instruments-info?category=spot&symbol={symbol}"
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


def last_price(transport: pf.Transport, symbol: str = SYMBOL) -> Decimal:
    url = f"{pf.DEMO_BASE}/v5/market/tickers?category=spot&symbol={symbol}"
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
    client_key: str | None = None,
    symbol: str = SYMBOL,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Kill-switch -> caps -> quantize -> order -> poll -> reconcile -> ledger.

    `client_key` (Stage B only): a persisted Bybit `orderLinkId` bound to this logical submission.
    It is reserved and fsynced by the caller BEFORE this POST, and validated inside `_order_create`.
    When None (the NOT_ACTIVATED path) the order body is byte-identical to today.

    `symbol` defaults to the ETH lane's SYMBOL, so the single-symbol path is byte-identical; the
    multi-coin lane passes a per-coin symbol that drives the instrument/ticker/order symbol, the
    base-coin reconciliation key, and the ledger record's `symbol`.

    `strategy` (confluence lane only): tags every ledger record so activity orders are attributable
    to the scored engine and separable from the untagged ETH/multi records. None keeps the record
    byte-identical to today.
    """
    stamp = datetime.now(UTC).isoformat()
    base_record: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at": stamp,
        "symbol": symbol,
        "side": intent.side,
        "unit": intent.unit,
        "signal_ref": intent.signal_ref,
        "reason": intent.reason,
        **LANE_LABEL,
    }
    if strategy is not None:
        base_record["strategy"] = strategy
    if kill_switch_active():
        record = {**base_record, "ok": False, "stage": "kill_switch", "qty": str(intent.qty)}
        _append_ledger(record)
        return record
    qty = intent.qty
    if intent.side == "Buy":
        if qty > Decimal(str(rt.MAX_NOTIONAL)):
            raise ValueError(f"buy notional {qty} exceeds the {rt.MAX_NOTIONAL} USDT cap")
    else:
        price = last_price(get_transport, symbol)
        if price <= 0:
            record = {**base_record, "ok": False, "stage": "price_unavailable"}
            _append_ledger(record)
            return record
        if qty * price > SELL_MAX_NOTIONAL:
            # Deterministic pre-send cap: LocalRejection (a ValueError subclass) so Stage B's
            # do_post can tell this KNOWN no-send apart from a post-send failure.
            raise LocalRejection(
                f"sell notional {qty * price:.2f} exceeds the {SELL_MAX_NOTIONAL} USDT cap"
            )
        qty = quantize_down(qty, instrument_qty_step(get_transport, symbol))
        if qty <= 0:
            record = {**base_record, "ok": False, "stage": "qty_below_step"}
            _append_ledger(record)
            return record
    before = rt.wallet(get_transport, api_key, secret, rt._now())
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": intent.side,
        "orderType": "Market",
        "qty": str(qty),
        "marketUnit": intent.unit,
    }
    if client_key is not None:
        order["orderLinkId"] = client_key  # validated in rt._order_create before it reaches venue
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
    status = rt._poll_filled(get_transport, api_key, secret, order_id, symbol, sleep)
    after = rt.wallet(get_transport, api_key, secret, rt._now())
    base_coin = symbol.removesuffix("USDT")
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


def entry_price_from_ledger(
    records: list[dict[str, Any]], symbol: str | None = None, strategy: str | None = None
) -> Decimal | None:
    """Most recent filled long-entry avg price from ledger records, or None.

    Restart safety: a position opened before this process started has no entry in
    lane_state; the append-only orders ledger is the authoritative record of what was paid.

    `symbol` filters to that coin's entries. The single append-only ledger is shared across the
    multi-coin lane, so each coin must reconstruct its OWN entry price. None (the default) keeps the
    legacy no-filter behavior for the symbol dimension. `strategy` is ALWAYS compared so each lane
    reconstructs only its OWN entries: untagged ETH/multi records read as None, so the default
    strategy=None still matches them exactly as before, while a legacy (strategy=None) call now
    correctly ignores a newer confluence-tagged record for the same coin, and vice versa — a restart
    never reconstructs one lane's entry (and therefore its protective-stop pricing) from another's.
    """
    for record in reversed(records):
        if symbol is not None and record.get("symbol") != symbol:
            continue
        if record.get("strategy") != strategy:
            continue
        if record.get("reason") == "ENTRY_LONG" and record.get("ok") and record.get("avg_price"):
            return Decimal(str(record["avg_price"]))
    return None


def resolve_entry_price(
    state: dict[str, Any],
    ledger_records: list[dict[str, Any]],
    symbol: str | None = None,
    strategy: str | None = None,
) -> Decimal | None:
    """Entry price for the open long: from state if present, else reconstructed from the ledger."""
    stored = state.get("entry_price")
    if stored not in (None, "", "0"):
        return Decimal(str(stored))
    return entry_price_from_ledger(ledger_records, symbol, strategy)


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
    client_key: str | None = None,
    symbol: str = SYMBOL,
) -> dict[str, Any]:
    """Rest a demo Sell stop at trigger_price via the quarantined order transport (rt.place_stop).

    The order-endpoint literals stay confined to scripts/demo_roundtrip.py; the lane only binds
    the symbol/params. Demo host only, no new authority.

    `client_key` (Stage B only): the deterministic `orderLinkId` reserved+persisted before this one
    create POST, so a crash mid-create is reconcilable by key without a duplicate stop. None on the
    NOT_ACTIVATED compensating path keeps the order body byte-identical.

    `symbol` defaults to SYMBOL (byte-identical ETH path); the multi-coin lane binds each coin.
    """
    venue_trigger = quantize_price_up(trigger_price, price_tick)
    venue_qty = quantize_stop_qty_down(base_qty, qty_step)
    return rt.place_stop(
        post_transport,
        api_key,
        secret,
        rt._now(),
        pf.DEMO_BASE,
        symbol=symbol,
        trigger_price=str(venue_trigger),
        base_qty=str(venue_qty),
        client_key=client_key,
    )


def cancel_stop_order(
    order_id: str,
    api_key: str,
    secret: str,
    *,
    post_transport: rt.PostTransport = _live_post_transport,
    symbol: str = SYMBOL,
) -> dict[str, Any]:
    """Cancel a resting demo stop by order id via the quarantined transport (rt.cancel_order)."""
    return rt.cancel_order(
        post_transport, api_key, secret, rt._now(), pf.DEMO_BASE, order_id=order_id, symbol=symbol
    )


_ACTIVE_STOP_STATUSES = {"New", "Untriggered"}
_CLEARED_STOP_STATUSES = {"Cancelled", "Deactivated", "Rejected"}


def stop_order_status(
    order_id: str, api_key: str, secret: str, transport: pf.Transport, symbol: str = SYMBOL
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
            "symbol": symbol,
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


def _confirmed_stop_state(
    order_id: str, api_key: str, secret: str, transport: pf.Transport, symbol: str = SYMBOL
) -> str:
    """Return active/cleared/unknown; empty realtime responses are never assumed cancelled."""
    return _confirmed_stop_snapshot(order_id, api_key, secret, transport, symbol=symbol)[0]


def _confirmed_stop_snapshot(
    order_id: str,
    api_key: str,
    secret: str,
    transport: pf.Transport,
    *,
    expected_trigger: Any = None,
    expected_qty: Any = None,
    symbol: str = SYMBOL,
) -> tuple[str, dict[str, Any]]:
    """Return normalized state plus the exact venue row used for that conclusion."""
    try:
        row = stop_order_status(order_id, api_key, secret, transport, symbol)
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
            symbol=symbol,
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
    symbol: str = SYMBOL,
) -> bool:
    """Strict spot identity for a row returned by the fixed StopOrder query above."""
    trigger_direction = row.get("triggerDirection")
    if (
        (requested_order_id is not None and str(row.get("orderId", "")) != requested_order_id)
        or row.get("symbol") != symbol
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
    symbol: str = SYMBOL,
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
            symbol=symbol,
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
    symbol: str = SYMBOL,
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
            symbol=symbol,
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
    resting: dict[str, Any],
    api_key: str,
    secret: str,
    transport: pf.Transport,
    symbol: str = SYMBOL,
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
            symbol=symbol,
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
    client_key: str | None = None,
    symbol: str = SYMBOL,
) -> dict[str, Any] | None:
    """Execute a stop_reconcile_action decision; return the new resting-stop record (or None).

    Best-effort secondary protection: metadata and replacement are validated before any existing
    stop is touched. Replacement places the new protection first, then cancels the old stop.

    `client_key` (Stage B only): binds the persisted `orderLinkId` to the primary stop CREATE POST
    (place/replace); the old-stop cancel and any rollback still target their ORIGINAL correlation by
    orderId. None on the NOT_ACTIVATED compensating path keeps every venue request byte-identical.

    `symbol` defaults to SYMBOL (byte-identical ETH path); the multi-coin lane binds each coin so a
    coin's protective stop is priced, quantized, and confirmed against its OWN instrument.
    """
    if decision == "reconcile" and resting:
        return _reconcile_ambiguous_stop(resting, api_key, secret, get_transport, symbol)
    if decision == "noop":
        return resting
    if decision == "cancel":
        if not resting or not resting.get("order_id"):
            return None
        try:
            cancelled = cancel_stop_order(
                str(resting["order_id"]),
                api_key,
                secret,
                post_transport=post_transport,
                symbol=symbol,
            )
        except Exception as error:  # noqa: BLE001 - preserve state for retry
            print(f"venue stop cancel failed: {error}", file=sys.stderr)
            return resting
        if cancelled.get("retCode") != 0:
            print(f"venue stop cancel rejected: {cancelled.get('retMsg')}", file=sys.stderr)
            return resting
        state = _confirmed_stop_state(
            str(resting["order_id"]), api_key, secret, get_transport, symbol
        )
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
            price_tick if price_tick is not None else instrument_price_tick(get_transport, symbol)
        )
        resolved_qty_step = (
            qty_step if qty_step is not None else instrument_qty_step(get_transport, symbol)
        )
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
            client_key=client_key,
            symbol=symbol,
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
        symbol=symbol,
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
        cancelled = cancel_stop_order(
            old_order_id, api_key, secret, post_transport=post_transport, symbol=symbol
        )
        if cancelled.get("retCode") == 0:
            old_state = _confirmed_stop_state(old_order_id, api_key, secret, get_transport, symbol)
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
        rollback = cancel_stop_order(
            new_order_id, api_key, secret, post_transport=post_transport, symbol=symbol
        )
        if rollback.get("retCode") == 0:
            rollback_state = _confirmed_stop_state(
                new_order_id, api_key, secret, get_transport, symbol
            )
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


def _state_path(symbol: str) -> Path:
    """Per-coin lane-state path. The default ETH lane keeps the original lane_state.json (so its
    state is preserved and tests that monkeypatch LANE_STATE still hit it); every other coin gets
    its own lane_state_<symbol>.json so each position/cursor is independent."""
    return LANE_STATE if symbol == SYMBOL else LANE_DIR / f"lane_state_{symbol}.json"


def _heartbeat_path(symbol: str) -> Path:
    """Per-coin heartbeat path. Default ETH keeps heartbeat.json; other coins get their own."""
    return HEARTBEAT if symbol == SYMBOL else LANE_DIR / f"heartbeat_{symbol}.json"


def read_state(symbol: str = SYMBOL) -> dict[str, Any]:
    path = _state_path(symbol)
    if not path.is_file():
        return {"lane_base": "0", "cursor": None}
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else {"lane_base": "0", "cursor": None}


def write_state(state: dict[str, Any], symbol: str = SYMBOL) -> None:
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(symbol)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)


def write_state_durable(state: dict[str, Any]) -> None:
    """Persist lane state with an fsync of the file AND its directory.

    The risk-reduction durability protocol (Appendix B) requires each phase transition to survive a
    crash BEFORE the next step runs, so it uses this instead of the plain rename above.
    """
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LANE_STATE.with_suffix(".tmp")
    raw = json.dumps(state, sort_keys=True).encode("utf-8")
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(tmp, LANE_STATE)
    dir_descriptor = os.open(LANE_DIR, os.O_RDONLY)
    try:
        os.fsync(dir_descriptor)
    finally:
        os.close(dir_descriptor)


# --- Stage B default-disabled evidence integration --------------------------------------------
# Everything below engages ONLY while Stage B is ACTIVE (runtime root present and valid). When
# NOT_ACTIVATED every helper is a no-op or reports the legacy state, so the lane is byte-identical
# to today. The one safety invariant that overrides all of it: evidence-store failure or an
# unresolved attempted create may NEVER block the first risk-reducing sell/exit, protective-stop
# create/replace/cleanup, cancel, kill-switch, or reconciliation.

_RISK_REDUCTION_CREATE_KINDS = frozenset({"EXIT_CREATE", "STOP_CREATE", "STOP_REPLACE_CREATE"})
_RISK_REDUCTION_KINDS = _RISK_REDUCTION_CREATE_KINDS | {"CANCEL_TARGET"}
# place() stages that mean it rejected the order LOCALLY, before ever reaching the venue. These are
# deterministic no-sends: we KNOW no POST occurred, so a reserved risk reduction that hits one may
# be rolled back to a clean (non-frozen) state instead of being stranded at POST_UNKNOWN. The
# SELL_MAX_NOTIONAL cap is also a pre-send local rejection but surfaces as a raised ValueError.
_PLACE_LOCAL_NO_SEND_STAGES = frozenset({"kill_switch", "price_unavailable", "qty_below_step"})
_PENDING_SCHEMA = "tios.demo_decision_evidence.pending_risk_reduction.v1"
_ORD_ALIAS = re.compile(r"^ord_[a-f0-9]{64}$")


def stage_b_active(repo_root: Path | None = None) -> bool:
    """True only when the Stage B runtime root is present AND passes the activation reader."""
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    try:
        return stage_b.activation_check(root).state is stage_b.ActivationState.ACTIVE
    except stage_b.StageBEvidenceError:
        return False


def stage_b_latch(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the validated `stage_b_v2` latch object, or None when absent/legacy."""
    latch = state.get("stage_b_v2")
    return latch if isinstance(latch, dict) else None


def entry_blocked(state: dict[str, Any]) -> bool:
    """True when the Stage B latch forbids NEW risk-increasing entries.

    Risk-reducing actions are NEVER gated by this — only fresh entries are. Any non-READY evidence
    state (ENTRY_BLOCK, RECOVERY_AUTHORIZED, RECONCILED_PENDING_COMMIT) or an unresolved pending
    create blocks entries. An unknown/invalid latch fails closed (blocks entries).
    """
    latch = stage_b_latch(state)
    if latch is None:
        return False
    if latch.get("evidence_state") not in {None, "READY"}:
        return True
    pending = latch.get("pending_risk_reduction")
    if isinstance(pending, dict) and pending.get("phase") in {"POST_UNKNOWN", "ACK_PENDING"}:
        # An unresolved attempted create stays query/recovery-only and blocks fresh signals.
        return True
    return False


def _pending_core(
    *,
    subject_intent_event_id: str,
    action_kind: str,
    sequence: int,
    payload: dict[str, Any],
    payload_sha256: str,
    client_key_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema": _PENDING_SCHEMA,
        "subject_intent_event_id": subject_intent_event_id,
        "action_kind": action_kind,
        "sequence": sequence,
        "payload": payload,
        "payload_sha256": payload_sha256,
        "client_key_sha256": client_key_sha256,
    }


def build_pending_risk_reduction(
    *,
    activation_epoch: str,
    subject_intent_event_id: str,
    action_kind: str,
    sequence: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Construct a RESERVED `pending_risk_reduction` record (Appendix A/B), fully self-checked.

    The deterministic client key is derived for the three create kinds; CANCEL_TARGET derives none
    and targets the original correlation. The raw key is never stored in lane state — only its
    SHA-256 — and is recomputed from this verified record when needed.
    """
    if action_kind not in _RISK_REDUCTION_KINDS:
        raise ValueError(f"unknown risk-reduction action kind: {action_kind}")
    _validate_pending_payload(action_kind, payload)
    payload_sha256 = stage_b.canonical_sha256(payload)
    client_key_sha256: str | None = None
    if action_kind in _RISK_REDUCTION_CREATE_KINDS:
        client_key = stage_b.derive_risk_reduction_client_key(
            activation_epoch=activation_epoch,
            subject_intent_event_id=subject_intent_event_id,
            action_kind=action_kind,
            sequence=sequence,
            payload_sha256=payload_sha256,
        )
        client_key_sha256 = stage_b.sha256_bytes(client_key.encode("ascii"))
    core = _pending_core(
        subject_intent_event_id=subject_intent_event_id,
        action_kind=action_kind,
        sequence=sequence,
        payload=payload,
        payload_sha256=payload_sha256,
        client_key_sha256=client_key_sha256,
    )
    action_id = f"rr_{stage_b.canonical_sha256(core)}"
    return {**core, "action_id": action_id, "phase": "RESERVED", "terminal_status": None}


def _validate_pending_payload(action_kind: str, payload: dict[str, Any]) -> None:
    expected = {
        "side",
        "order_type",
        "qty",
        "quantity_unit",
        "trigger_price",
        "order_filter",
        "target_order_alias",
    }
    if set(payload) != expected:
        raise ValueError("pending risk-reduction payload has unexpected fields")
    target = payload["target_order_alias"]
    if action_kind in {"EXIT_CREATE", "STOP_CREATE"}:
        if target is not None:
            raise ValueError(f"{action_kind} requires a null target_order_alias")
    elif not (isinstance(target, str) and _ORD_ALIAS.fullmatch(target)):
        raise ValueError(f"{action_kind} requires the tracked target order alias")
    if action_kind == "CANCEL_TARGET" and (
        payload["order_type"] != "MARKET"
        or payload["qty"] != "0"
        or payload["quantity_unit"] != "BASE"
        or payload["trigger_price"] is not None
    ):
        # CANCEL_TARGET is a typed non-create placeholder: MARKET / qty 0 / null trigger. Any other
        # combination is a create smuggled in as a cancel, so fail closed.
        raise ValueError("CANCEL_TARGET must use the MARKET/qty-0/null-trigger placeholder")


def pending_client_key(pending: dict[str, Any], activation_epoch: str) -> str:
    """Recompute the raw client key from a verified pending record (create kinds only)."""
    if pending.get("action_kind") not in _RISK_REDUCTION_CREATE_KINDS:
        raise ValueError("CANCEL_TARGET derives no client key")
    key = stage_b.derive_risk_reduction_client_key(
        activation_epoch=activation_epoch,
        subject_intent_event_id=str(pending["subject_intent_event_id"]),
        action_kind=str(pending["action_kind"]),
        sequence=int(pending["sequence"]),
        payload_sha256=str(pending["payload_sha256"]),
    )
    if stage_b.sha256_bytes(key.encode("ascii")) != pending.get("client_key_sha256"):
        raise ValueError("pending record client-key hash does not match the derived key")
    return key


def reserve_risk_reduction(state: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    """Persist phase RESERVED durably (fsync file + directory) before any risk-increasing POST."""
    latch = dict(stage_b_latch(state) or {})
    latch["pending_risk_reduction"] = pending
    latch["risk_reduction_sequence"] = int(pending["sequence"])
    new_state = {**state, "stage_b_v2": latch}
    write_state_durable(new_state)
    return new_state


def advance_pending(
    state: dict[str, Any], phase: str, *, terminal_status: str | None = None
) -> dict[str, Any]:
    """Durably move the pending record to a new phase (POST_UNKNOWN/ACK_PENDING/TERMINAL)."""
    latch = dict(stage_b_latch(state) or {})
    pending = latch.get("pending_risk_reduction")
    if not isinstance(pending, dict):
        raise ValueError("no pending risk reduction to advance")
    updated = {**pending, "phase": phase}
    if phase == "TERMINAL":
        updated["terminal_status"] = terminal_status
    latch["pending_risk_reduction"] = updated
    new_state = {**state, "stage_b_v2": latch}
    write_state_durable(new_state)
    return new_state


def clear_pending(state: dict[str, Any]) -> dict[str, Any]:
    """Durably clear a TERMINAL pending record so the next logical submission can start fresh."""
    latch = dict(stage_b_latch(state) or {})
    latch["pending_risk_reduction"] = None
    new_state = {**state, "stage_b_v2": latch}
    write_state_durable(new_state)
    return new_state


def close_open_episode(state: dict[str, Any]) -> dict[str, Any]:
    """Null the durable open-episode anchor once the lane is confirmed flat via an exit.

    Nulling `open_episode_event_id` (a documented nullable latch field) is what keeps the Finding H
    entry-recovery net from resurrecting a position a completed exit already closed. In-memory only;
    run_cycle's end-of-cycle write persists it alongside lane_base=0.
    """
    latch = stage_b_latch(state)
    if latch is None or latch.get("open_episode_event_id") is None:
        return state
    new_latch = dict(latch)
    new_latch["open_episode_event_id"] = None
    return {**state, "stage_b_v2": new_latch}


def pending_permits_create_post(pending: dict[str, Any]) -> bool:
    """Only a RESERVED create may proceed (exactly once) to its single POST.

    POST_UNKNOWN/ACK_PENDING are query/recovery-only — a lost ack NEVER authorizes a duplicate
    create, in the same process or after restart. This is the core no-duplicate-create invariant.
    """
    return (
        pending.get("action_kind") in _RISK_REDUCTION_CREATE_KINDS
        and pending.get("phase") == "RESERVED"
    )


def execute_risk_reduction_create(
    state: dict[str, Any],
    do_post: Any,
    do_query: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Drive a reserved create through RESERVED -> POST_UNKNOWN -> (one POST) -> ACK_PENDING.

    `do_post()` issues the single create POST; `do_query()` reconciles by the persisted key without
    ever posting. Returns (new_state, result). A record already in POST_UNKNOWN/ACK_PENDING (crash
    after the pre-POST marker, or after POST before the ack was persisted) is query-only and posts
    nothing — proving zero create retries across a same-process fault and a restart.
    """
    latch = stage_b_latch(state) or {}
    pending = latch.get("pending_risk_reduction")
    if not isinstance(pending, dict):
        raise ValueError("no reserved risk reduction to execute")
    if pending_permits_create_post(pending):
        # Persist POST_UNKNOWN *before* the one permitted POST: a crash here stays query-only.
        state = advance_pending(state, "POST_UNKNOWN")
        result = do_post()
        if result.get("no_send"):
            # do_post proved place() rejected the order LOCALLY (kill switch, dust, price/notional
            # cap) with no network send. Since we KNOW no POST occurred — unlike an empty
            # reconciliation, which never proves non-creation — roll the reservation back to a
            # clean, non-frozen state so a routine reject can never freeze future risk reduction.
            return clear_pending(state), result
        if rt.classify_create_ack(result) == rt.CREATE_ACK_ACCEPTED:
            state = advance_pending(state, "ACK_PENDING")
        return state, result
    # Unresolved (POST_UNKNOWN/ACK_PENDING) or non-create: reconcile by key, never replay create.
    return state, do_query()


def economics_from_execution_rows(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    """Exact Appendix F economics from deduplicated Bybit execution rows (never wallet deltas).

    Base fees change the reconciled quantity (and thus real exit cashflow); quote fees subtract
    from net; a third-currency fee makes the episode ineligible upstream. Exact `execValue` owns
    entry/exit quote cashflow.
    """
    buy_qty = sell_qty = Decimal("0")
    entry_value = exit_value = Decimal("0")
    quote_fee = base_fee = Decimal("0")
    buy_base_fee = sell_base_fee = Decimal("0")
    third_fee_present = False
    for row in rows:
        side = row.get("side")
        qty = _exact_nonnegative(row.get("execQty"))
        value = _exact_nonnegative(row.get("execValue"))
        fee = _exact_nonnegative(row.get("execFee"))
        currency = row.get("feeCurrency")
        if side == "Buy":
            buy_qty += qty
            entry_value += value
        elif side == "Sell":
            sell_qty += qty
            exit_value += value
        else:
            raise ValueError(f"execution row has an invalid side: {side!r}")
        if currency == "USDT":
            quote_fee += fee
        elif currency == "ETH":
            base_fee += fee
            if side == "Buy":
                buy_base_fee += fee
            else:
                sell_base_fee += fee
        elif fee != 0:
            third_fee_present = True
    position = (buy_qty - buy_base_fee) - (sell_qty + sell_base_fee)
    return {
        "buy_exec_qty": buy_qty,
        "sell_exec_qty": sell_qty,
        "entry_exec_value": entry_value,
        "exit_exec_value": exit_value,
        "quote_fee": quote_fee,
        "base_fee": base_fee,
        "third_fee_present": Decimal("1") if third_fee_present else Decimal("0"),
        "position_base_qty": position,
    }


def _exact_nonnegative(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("economic field must not be a boolean")
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError) as error:
        raise ValueError(f"economic field is not an exact decimal: {value!r}") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"economic field must be finite and nonnegative: {value!r}")
    return parsed


def record_stage_b_events(
    events: list[stage_b.EvidenceEvent],
    capability: stage_b.LaneLockCapability,
    *,
    repo_root: Path | None = None,
) -> str:
    """Best-effort commit of Stage B evidence while holding the exclusive lane lock.

    Returns "READY" on a durable commit and "ENTRY_BLOCK" on any evidence-store failure — the sink
    is invoked ONLY through the capability, which the Wave 1 sink independently re-validates. This
    never raises: an evidence outage latches ENTRY_BLOCK but must not obstruct risk reduction.
    """
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    try:
        stage_b.StageBEvidenceSink(root).append(events, capability=capability)
        return "READY"
    except stage_b.StageBEvidenceError as error:
        print(f"stage B evidence unavailable; latching ENTRY_BLOCK: {error}", file=sys.stderr)
        return "ENTRY_BLOCK"


def stage_b_epoch(repo_root: Path | None = None) -> str | None:
    """Return the active activation epoch, or None when NOT_ACTIVATED/unavailable."""
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    try:
        return stage_b.load_activation(root).activation_epoch
    except stage_b.StageBEvidenceError:
        return None


def entry_client_key() -> str:
    """One 36-char `tios2_` client key per logical entry submission.

    A CSPRNG token (no explicit collision check): ~144 bits of `secrets` entropy in the 30-char
    suffix make a collision negligible, and the venue independently rejects a duplicate orderLinkId.
    """
    key = ("tios2_" + secrets.token_urlsafe(24).replace("=", ""))[:36]
    return rt.validate_client_key(key)


def _entry_price_from_economics(economics: dict[str, Decimal]) -> Decimal | None:
    buy_qty = economics["buy_exec_qty"]
    if buy_qty <= 0:
        return None
    return economics["entry_exec_value"] / buy_qty


def _reconcile_entry_by_key(
    state: dict[str, Any],
    client_key: str,
    api_key: str,
    secret: str,
    get_transport: pf.Transport,
) -> tuple[Decimal, Decimal | None, dict[str, Any]]:
    recon = rt.reconcile_by_client_key(
        get_transport, api_key, secret, pf.DEMO_BASE, client_key, SYMBOL
    )
    economics = economics_from_execution_rows(recon["executions"])
    return economics["position_base_qty"], _entry_price_from_economics(economics), state


# Fixed series-identity inputs for the demo lane's single candidate; aliased via the install key.
_STRATEGY_VALUE = "ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1"
_COST_VALUE = "DEMO_COST_MODEL_V1"
_RISK_VALUE = "DEMO_RISK_POLICY_V1"


def _alias_material(activation: stage_b.ActivationContext) -> bytes:
    return (activation.private_root / "private/install_alias.key").read_bytes()


def _alias(material: bytes, tag: str, value: str) -> str:
    """Appendix D private alias: tag_ + HMAC-SHA256(install_key, domain\\0tag\\0value)."""
    digest = hmac.new(
        material,
        b"tios.demo_decision_evidence.v2\0" + tag.encode("ascii") + b"\0" + value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{tag}_{digest}"


def _bound_payload(activation: stage_b.ActivationContext) -> dict[str, Any]:
    return {
        "activation_receipt_sha256": activation.receipt_sha256,
        "config_sha256": activation.config_sha256,
        "independent_review_sha256": activation.independent_review_sha256,
        "flat_reconciliation_sha256": activation.flat_reconciliation_sha256,
        "rollback_config_sha256": activation.rollback_config_sha256,
        "controlled_restart_id": activation.receipt["controlled_restart_id"],
        "repo_commit": activation.receipt["repo_commit"],
    }


def _entry_presubmission_events(
    activation: stage_b.ActivationContext,
    prior: stage_b.EvidenceEvent | None,
    material: bytes,
    client_key: str,
) -> tuple[list[stage_b.EvidenceEvent], str, str]:
    """[genesis?] DECISION -> RISK_VERDICT -> IDEMPOTENCY_KEY -> SUBMISSION_INTENT.

    This committed generation is the DURABLE HOME of the entry client key (inside
    IDEMPOTENCY_KEY_RESERVED) and the persistence-precedes-POST proof. The raw key never enters lane
    state. Returns (events, intent_event_id, order_alias).
    """
    epoch = activation.activation_epoch
    events: list[stage_b.EvidenceEvent] = []
    tip = prior
    if tip is None:
        tip = stage_b.next_event(
            None,
            activation_epoch=epoch,
            event_type=stage_b.EventType.ACTIVATION_BOUND,
            payload=_bound_payload(activation),
        )
        events.append(tip)
    decision = stage_b.next_event(
        tip,
        activation_epoch=epoch,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        payload={
            "strategy_alias": _alias(material, "strategy", _STRATEGY_VALUE),
            "cost_alias": _alias(material, "cost", _COST_VALUE),
            "risk_alias": _alias(material, "risk", _RISK_VALUE),
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "ENTRY",
            "side": "BUY",
            "requested_qty": str(BUY_QUOTE_USDT),
            "quantity_unit": "QUOTE",
        },
    )
    risk = stage_b.next_event(
        decision,
        activation_epoch=epoch,
        event_type=stage_b.EventType.RISK_VERDICT_OBSERVED,
        payload={
            "decision_event_id": decision.event_id,
            "verdict": "ALLOW_RISK_INCREASE",
            "reason_code": "POLICY_PASS",
            "approved_qty": str(BUY_QUOTE_USDT),
            "quantity_unit": "QUOTE",
            "quote_cap": str(BUY_QUOTE_USDT),
        },
    )
    order_alias = _alias(material, "ord", client_key)
    key_event = stage_b.next_event(
        risk,
        activation_epoch=epoch,
        event_type=stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        payload={
            "decision_event_id": decision.event_id,
            "risk_event_id": risk.event_id,
            "order_alias": order_alias,
            "client_key": client_key,
            "client_key_sha256": stage_b.sha256_bytes(client_key.encode("ascii")),
        },
    )
    intent = stage_b.next_event(
        key_event,
        activation_epoch=epoch,
        event_type=stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        payload={
            "key_event_id": key_event.event_id,
            "order_alias": order_alias,
            "order_kind": "ENTRY",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": str(BUY_QUOTE_USDT),
            "quantity_unit": "QUOTE",
            "trigger_price": None,
            "risk_increasing": True,
        },
    )
    events += [decision, risk, key_event, intent]
    return events, intent.event_id, order_alias


def _entry_attempt_events(
    activation: stage_b.ActivationContext,
    prior: stage_b.EvidenceEvent,
    material: bytes,
    client_key: str,
    intent_event_id: str,
    order_alias: str,
    accepted: bool,
) -> list[stage_b.EvidenceEvent]:
    """SUBMISSION_ATTEMPTED + (VENUE_ACKNOWLEDGED | SUBMISSION_RESULT_UNKNOWN), marking the create.

    Committing this resolves the intent as attempted so restart recovery only re-reconciles a truly
    mid-flight entry (a committed intent with no attempt).
    """
    epoch = activation.activation_epoch
    attempt = stage_b.next_event(
        prior,
        activation_epoch=epoch,
        event_type=stage_b.EventType.SUBMISSION_ATTEMPTED,
        payload={
            "intent_event_id": intent_event_id,
            "order_alias": order_alias,
            "client_key_sha256": stage_b.sha256_bytes(client_key.encode("ascii")),
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
    )
    if accepted:
        result = stage_b.next_event(
            attempt,
            activation_epoch=epoch,
            event_type=stage_b.EventType.VENUE_ACKNOWLEDGED,
            payload={
                "attempt_event_id": attempt.event_id,
                "order_alias": order_alias,
                "venue_code": 0,
                "result_code": "ACCEPTED_PENDING",
            },
        )
    else:
        result = stage_b.next_event(
            attempt,
            activation_epoch=epoch,
            event_type=stage_b.EventType.SUBMISSION_RESULT_UNKNOWN,
            payload={
                "attempt_event_id": attempt.event_id,
                "order_alias": order_alias,
                "venue_code": 0,
                "result_code": "UNKNOWN",
            },
        )
    return [attempt, result]


def _latch_entry_block(state: dict[str, Any]) -> dict[str, Any]:
    latch = dict(stage_b_latch(state) or {})
    latch["evidence_state"] = "ENTRY_BLOCK"
    new_state = {**state, "stage_b_v2": latch}
    write_state_durable(new_state)
    return new_state


def active_entry(
    signal_ref: str,
    state: dict[str, Any],
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
    capability: stage_b.LaneLockCapability | None,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any] | None, Decimal, Decimal | None, dict[str, Any]]:
    """ACTIVE entry: commit the pre-submission chain (key home) UNDER the held lock BEFORE the POST.

    The committed generation is the durable client-key persistence and the persistence-precedes
    -POST proof; if it cannot commit, the lane latches ENTRY_BLOCK and issues NO POST. lane_base
    comes from exact executions (Appendix F), never a wallet delta. No raw client key is in lane
    state — only open_episode_event_id (the intent anchor); the key is recovered from committed
    evidence on restart. The sink is invoked through the ALREADY-HELD lane lock (never re-acquired).
    """
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    if capability is None:
        # ACTIVE but no held lock threaded down: cannot durably persist the key -> fail closed.
        return None, Decimal("0"), None, _latch_entry_block(state)
    try:
        activation = stage_b.load_activation(root)
        material = _alias_material(activation)
        sink = stage_b.StageBEvidenceSink(root)
        committed = sink.load().events
        key = entry_client_key()
        pre_events, intent_event_id, order_alias = _entry_presubmission_events(
            activation, committed[-1] if committed else None, material, key
        )
        snapshot = sink.append(pre_events, capability=capability)  # durable key home BEFORE POST
    except (stage_b.StageBEvidenceError, OSError) as error:
        print(
            f"stage B pre-submission commit failed; ENTRY_BLOCK, no POST: {error}", file=sys.stderr
        )
        return None, Decimal("0"), None, _latch_entry_block(state)
    # Durably anchor the open episode BEFORE the POST. lane_base is still 0 here (no position yet),
    # but this on-disk anchor is what lets restart recovery reconcile a filled position by its
    # committed key if we crash after the venue create but before the reconciled write below —
    # so a lost lane_state can never silently drop a real position (Finding H defense in depth).
    anchor_latch = dict(stage_b_latch(state) or {})
    anchor_latch["open_episode_event_id"] = intent_event_id
    state = {**state, "stage_b_v2": anchor_latch}
    write_state_durable(state)
    action = place(
        LaneIntent("Buy", BUY_QUOTE_USDT, "quoteCoin", signal_ref, "ENTRY_LONG"),
        api_key,
        secret,
        get_transport=get_transport,
        post_transport=post_transport,
        sleep=sleep,
        client_key=key,
    )
    try:  # best-effort: mark the intent attempted so restart only re-reconciles a mid-flight entry
        record_stage_b_events(
            _entry_attempt_events(
                activation,
                snapshot.events[-1],
                material,
                key,
                intent_event_id,
                order_alias,
                bool(action.get("order_id")),
            ),
            capability,
            repo_root=root,
        )
    except stage_b.StageBEvidenceError:
        pass
    lane_base, entry_price, _ = _reconcile_entry_by_key(state, key, api_key, secret, get_transport)
    latch = dict(stage_b_latch(state) or {})
    latch["open_episode_event_id"] = intent_event_id
    latch["evidence_state"] = "READY"
    # Carry the reconciled position into this durable write (Finding H): clobbering the file with a
    # stale in-memory snapshot that still holds the pre-entry lane_base ("0") would, on a crash
    # before run_cycle's end-of-cycle write, leave lane_state flat while the position is real.
    new_state = {
        **state,
        "lane_base": str(lane_base),
        "entry_price": str(entry_price) if entry_price is not None else None,
        "stage_b_v2": latch,
    }
    write_state_durable(new_state)
    return action, lane_base, entry_price, new_state


def _outstanding_entry_key(repo_root: Path) -> str | None:
    """Client key of a committed entry intent with no SUBMISSION_ATTEMPTED yet (mid-flight)."""
    try:
        events = stage_b.StageBEvidenceSink(repo_root).load().events
    except stage_b.StageBEvidenceError:
        return None
    attempted = {
        e.payload.get("intent_event_id")
        for e in events
        if e.event_type is stage_b.EventType.SUBMISSION_ATTEMPTED
    }
    by_id = {e.event_id: e for e in events}
    for intent in events:
        if (
            intent.event_type is stage_b.EventType.SUBMISSION_INTENT_COMMITTED
            and intent.payload.get("order_kind") == "ENTRY"
            and intent.event_id not in attempted
        ):
            key_event = by_id.get(cast(str, intent.payload.get("key_event_id")))
            if key_event is not None:
                return str(key_event.payload.get("client_key"))
    return None


def _episode_entry_key(repo_root: Path, intent_event_id: str) -> str | None:
    """Client key of the ENTRY intent anchored by `intent_event_id`, from committed evidence."""
    try:
        events = stage_b.StageBEvidenceSink(repo_root).load().events
    except stage_b.StageBEvidenceError:
        return None
    by_id = {e.event_id: e for e in events}
    intent = by_id.get(intent_event_id)
    if (
        intent is None
        or intent.event_type is not stage_b.EventType.SUBMISSION_INTENT_COMMITTED
        or intent.payload.get("order_kind") != "ENTRY"
    ):
        return None
    key_event = by_id.get(cast(str, intent.payload.get("key_event_id")))
    return str(key_event.payload.get("client_key")) if key_event is not None else None


def recover_unresolved_entry(
    state: dict[str, Any],
    api_key: str,
    secret: str,
    get_transport: pf.Transport,
    *,
    repo_root: Path | None = None,
) -> tuple[Decimal | None, Decimal | None, dict[str, Any]]:
    """Restart safety: reconcile a mid-flight entry by its COMMITTED-EVIDENCE key and NEVER repost.

    The key is recovered from the committed IDEMPOTENCY_KEY_RESERVED event (not lane state). Returns
    (lane_base, entry_price, state) with lane_base None when there is nothing to recover.

    Two layers: (1) an entry intent with no SUBMISSION_ATTEMPTED yet (truly mid-flight); and, as
    defense in depth for Finding H, (2) an ALREADY-ATTEMPTED entry whose durable open-episode
    anchor is set but whose position is not reflected in lane_base (lane_base==0) — the crash window
    between the venue create and the reconciled durable write. Reconciliation is query-only; it
    never reposts, and it only overrides lane_base when the venue actually shows an open position,
    so a genuinely flat episode (anchor cleared on exit) can never be resurrected.
    """
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    key = _outstanding_entry_key(root)
    if key is not None:
        lane_base, entry_price, _ = _reconcile_entry_by_key(
            state, key, api_key, secret, get_transport
        )
        return lane_base, entry_price, state
    subject = (stage_b_latch(state) or {}).get("open_episode_event_id")
    if isinstance(subject, str) and Decimal(str(state.get("lane_base", "0"))) == 0:
        entry_key = _episode_entry_key(root, subject)
        if entry_key is not None:
            lane_base, entry_price, _ = _reconcile_entry_by_key(
                state, entry_key, api_key, secret, get_transport
            )
            if lane_base > 0:
                return lane_base, entry_price, state
    return None, None, state


_TERMINAL_STATUS_MAP = {
    "Filled": "FILLED",
    "Cancelled": "CANCELLED",
    "Rejected": "REJECTED",
    "PartiallyFilledCanceled": "PARTIALLY_FILLED_CANCELED",
}
# A confirmed resting stop (not yet triggered/terminal) proves a stop CREATE succeeded — for the
# two stop-create kinds that resolves the durability pending even though it carries no terminal
# status. It is NOT resolution for an EXIT_CREATE market order, which is still working while active.
_RESTING_STOP_STATUSES = {"New", "Untriggered", "Triggered"}


def _venue_terminal_status(
    get_transport: pf.Transport, api_key: str, secret: str, client_key: str
) -> str | None:
    """Reconcile by key and map the venue status to a terminal enum, or None when non-terminal."""
    recon = rt.reconcile_by_client_key(
        get_transport, api_key, secret, pf.DEMO_BASE, client_key, SYMBOL
    )
    return _TERMINAL_STATUS_MAP.get(cast(str, recon.get("status")))


def active_risk_reduction(
    intent: LaneIntent,
    action_kind: str,
    state: dict[str, Any],
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """ACTIVE risk reduction (exit/stop): the lane-owned durability protocol governs the one POST.

    The deterministic key is anchored to the episode's committed entry intent. Evidence-store
    failure can NEVER block this: the record is owned by the already-durable lane state, so the
    single create POST proceeds even with no evidence write. The terminal status is derived from the
    ACTUAL reconciliation — it is only cleared on a genuinely terminal venue status; an
    ambiguous/non-terminal result is LEFT pending (query/recovery-only), never fabricated as FILLED
    and never auto-duplicated.
    """
    epoch = stage_b_epoch(repo_root)
    latch = stage_b_latch(state) or {}
    subject = latch.get("open_episode_event_id")
    if epoch is None or not isinstance(subject, str):
        # No activation epoch or no anchored entry intent -> fall back to the plain risk-reducing
        # place (still available; safety never depends on evidence being present).
        action = place(
            intent,
            api_key,
            secret,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
        )
        return action, state
    prior = latch.get("pending_risk_reduction")
    if isinstance(prior, dict) and prior.get("phase") in {"POST_UNKNOWN", "ACK_PENDING"}:
        # A prior unresolved risk reduction is query/recovery-only; do not start a new create.
        return None, state
    sequence = int(latch.get("risk_reduction_sequence", 0)) + 1
    payload = {
        "side": "SELL",
        "order_type": "MARKET",
        "qty": str(intent.qty),
        "quantity_unit": "BASE",
        "trigger_price": None,
        "order_filter": "Order",
        "target_order_alias": None,
    }
    pending = build_pending_risk_reduction(
        activation_epoch=epoch,
        subject_intent_event_id=subject,
        action_kind=action_kind,
        sequence=sequence,
        payload=payload,
    )
    state = reserve_risk_reduction(state, pending)
    key = pending_client_key(pending, epoch)
    captured: dict[str, Any] = {}

    def do_post() -> dict[str, Any]:
        try:
            record = place(
                intent,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                client_key=key,
            )
        except LocalRejection as error:
            # DETERMINISTIC pre-send rejection only (SELL_MAX_NOTIONAL cap): place() raised BEFORE
            # any network send, so signal a no-send and roll the reservation back rather than freeze
            # it at POST_UNKNOWN. A POST-SEND failure (malformed create-response json.loads, or a
            # _delta wallet parse after retCode==0) is a plain ValueError/JSONDecodeError — NOT a
            # LocalRejection — so it is NOT caught here: it propagates, and because POST_UNKNOWN was
            # already durably persisted before place(), restart recovery reconciles it query-only
            # (never a duplicate create), exactly like the entry path.
            print(
                f"risk-reduction create locally rejected before any send: {error}", file=sys.stderr
            )
            captured["record"] = None
            return {"retCode": 1, "no_send": True}
        captured["record"] = record
        if record.get("stage") in _PLACE_LOCAL_NO_SEND_STAGES:
            # place() rejected locally (kill switch, price unavailable, dust) — no POST reached the
            # venue, so this reserved create must not be stranded as an unresolved attempt.
            return {"retCode": 1, "no_send": True}
        return {"retCode": 0 if (record.get("ok") or record.get("order_id")) else 1}

    def do_query() -> dict[str, Any]:
        return rt.reconcile_by_client_key(get_transport, api_key, secret, pf.DEMO_BASE, key, SYMBOL)

    state, result = execute_risk_reduction_create(state, do_post, do_query)
    if result.get("no_send"):
        # Deterministic local rejection: no POST occurred and the reservation was already rolled
        # back, so there is nothing to reconcile and nothing left frozen. Return the ledger record
        # (or None for a raised cap) without touching the now-clear pending slot.
        return captured.get("record"), state
    terminal = _venue_terminal_status(get_transport, api_key, secret, key)
    if terminal is not None:
        state = advance_pending(state, "TERMINAL", terminal_status=terminal)
        state = clear_pending(state)
    # else: ambiguous/non-terminal -> LEAVE the pending record for next-cycle query-only recovery.
    return captured.get("record"), state


def recover_unresolved_risk_reduction(
    state: dict[str, Any],
    api_key: str,
    secret: str,
    get_transport: pf.Transport,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Query-only reconciliation of an unresolved risk reduction; never auto-duplicates a create.

    Covers every pending kind. Create kinds (exit/stop) reconcile by the derived key: a terminal
    status clears the pending, and for the two stop-create kinds a confirmed resting stop also
    resolves it (a successful protective rest carries no terminal status). CANCEL_TARGET derives no
    key, so it re-confirms the tracked stop by its ORIGINAL venue orderId. An unknown/ambiguous
    result is left query-only — an empty lookup never becomes terminal nor authorizes a create.

    ponytail: query-only reconciliation by key; the ceiling is that it never auto-issues a create.
    The legacy unconditional venue-resting stop (apply_stop_decision, run every cycle) stays the
    compensating protective control while a risk reduction is frozen unresolved. Upgrade path when
    that ceiling matters: operator-reviewed recovery (Appendix E `recover` CLI) plus a fresh full
    position/order/stop reconciliation authorizes a genuinely new logical submission. A
    deterministic pre-send local rejection on the stop path no longer reaches this sweep at all:
    active_stop_decision now catches LocalRejection before reserving, so it falls back to the
    compensating control leaving no frozen POST_UNKNOWN here to recover.
    """
    epoch = stage_b_epoch(repo_root)
    latch = stage_b_latch(state) or {}
    pending = latch.get("pending_risk_reduction")
    if (
        epoch is None
        or not isinstance(pending, dict)
        or pending.get("phase") not in {"POST_UNKNOWN", "ACK_PENDING"}
    ):
        return state
    kind = pending.get("action_kind")
    if kind == "CANCEL_TARGET":
        resting = state.get("resting_stop")
        order_id = str(resting.get("order_id") or "") if isinstance(resting, dict) else ""
        if not order_id:
            # No tracked target referenced -> the cancel's objective (stop gone) already holds.
            return clear_pending(state)
        stop_state = _confirmed_stop_state(order_id, api_key, secret, get_transport)
        if stop_state in {"cleared", "filled"}:
            return clear_pending(state)
        return state  # active/unknown -> leave query-only; no blind cancel retry
    if kind not in _RISK_REDUCTION_CREATE_KINDS:
        return state
    key = pending_client_key(pending, epoch)
    recon = rt.reconcile_by_client_key(get_transport, api_key, secret, pf.DEMO_BASE, key, SYMBOL)
    status = cast(str, recon.get("status"))
    terminal = _TERMINAL_STATUS_MAP.get(status)
    if terminal is not None:
        state = advance_pending(state, "TERMINAL", terminal_status=terminal)
        return clear_pending(state)
    if kind in {"STOP_CREATE", "STOP_REPLACE_CREATE"} and status in _RESTING_STOP_STATUSES:
        # FINDING M: a confirmed resting stop means the create succeeded (no terminal status), but
        # clearing the pending ALONE leaves resting_stop untracked. preflight_tracked_stop does not
        # rediscover an untracked venue stop, and stop_reconcile_action returns "place" whenever
        # resting_stop is None -> the next cycle would issue a SECOND stop-create POST (duplicate
        # over-protection). Write the recovered stop's identity back so the next cycle sees it
        # tracked and reconciles it instead of re-placing.
        restored = _restore_recovered_resting_stop(state, pending, recon.get("order"))
        if restored is None:
            # Cannot track the recovered stop (malformed venue row / payload) -> do NOT clear the
            # pending. Leaving it at POST_UNKNOWN keeps the prior_unresolved guard active so the
            # next cycle cannot issue a blind second create; recovery retries query-only.
            return state
        return clear_pending(restored)  # confirmed resting AND tracked -> the create succeeded
    return state


def _restore_recovered_resting_stop(
    state: dict[str, Any], pending: dict[str, Any], order_row: Any
) -> dict[str, Any] | None:
    """Track a recovery-confirmed resting stop (Finding M) so the next cycle does not re-place it.

    Builds the minimal ACTIVE resting record — the recovered venue orderId plus the exact posted
    trigger/qty from the pending payload — that preflight_tracked_stop and stop_reconcile_action
    consume; the remaining audit metadata is backfilled on the next confirmed cycle. Only returns a
    tracked resting_stop when the reconciled venue row carries a canonical orderId and the payload a
    positive trigger/qty; otherwise returns None (never guesses an identity), signalling the caller
    to keep the pending unresolved rather than clear it against an untracked stop.
    """
    payload = pending.get("payload")
    if not isinstance(order_row, dict) or not isinstance(payload, dict):
        return None
    order_id = _canonical_order_id(order_row.get("orderId"))
    trigger = _strict_positive_decimal(payload.get("trigger_price"))
    qty = _strict_positive_decimal(payload.get("qty"))
    if order_id is None or trigger is None or qty is None:
        return None
    return {
        **state,
        "resting_stop": {
            "state": "ACTIVE",
            "order_id": order_id,
            "trigger_price": str(trigger),
            "base_qty": str(qty),
        },
    }


_STOP_DECISION_KIND = {
    "place": "STOP_CREATE",
    "replace": "STOP_REPLACE_CREATE",
    "cancel": "CANCEL_TARGET",
}


def _stop_pending_resolved(
    decision: str, prior_resting: dict[str, Any] | None, new_resting: dict[str, Any] | None
) -> bool:
    """Reuse apply_stop_decision's own confirm-by-query result to resolve the durability pending.

    A confirmed ACTIVE/filled resting stop (place/replace) or a confirmed-cleared/filled target
    (cancel) resolves the pending; an AMBIGUOUS/BLOCKED_UNKNOWN outcome leaves it query-only so
    the next-cycle recover sweep reconciles it by key. Never fabricated: the state comes from the
    venue confirmation apply_stop_decision already performed.

    FINDING L: for a create (place/replace), apply_stop_decision returns the STALE prior `resting`
    record UNCHANGED when its create wraps a swallowed post-send failure (e.g. a malformed create
    response whose `json.loads` raised after the POST reached the venue). That stale record still
    reads ACTIVE, so trusting it here would clear a pending whose NEW create outcome is genuinely
    unknown — and the next cycle could then issue a second create (duplicate). A create is therefore
    resolved ONLY by a genuinely FRESH confirmed record: `new_resting` must be a NEW object
    (identity distinct from the prior) that apply_stop_decision built from a fresh query of the new
    stop. When it is the unchanged prior object, LEAVE the pending POST_UNKNOWN for the query-only
    recover sweep (the prior_unresolved guard prevents an automatic duplicate meanwhile).
    """
    if decision == "cancel":
        return new_resting is None or (
            isinstance(new_resting, dict)
            and new_resting.get("state") == "FILLED_PENDING_RECONCILIATION"
        )
    if not isinstance(new_resting, dict) or new_resting is prior_resting:
        # cleared-after-create, or the stale unchanged record from a swallowed post-send failure:
        # the NEW stop was never freshly confirmed -> ambiguous outcome, leave pending.
        return False
    return new_resting.get("state") in {"ACTIVE", "FILLED_PENDING_RECONCILIATION"}


def active_stop_decision(
    decision: str,
    resting: dict[str, Any] | None,
    lane_base: Decimal,
    entry: Decimal | None,
    state: dict[str, Any],
    api_key: str,
    secret: str,
    *,
    epoch: str | None,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    price_tick: Decimal | None,
    qty_step: Decimal | None,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """ACTIVE protective-stop/cancel via the lane-owned pending_risk_reduction durability protocol.

    The legacy apply_stop_decision stays the venue-resting compensating control and performs the
    actual create/cancel plus confirm-by-query. When a fresh create/replace/cancel is warranted and
    no prior risk reduction is unresolved, a pending record is reserved (a deterministic key for the
    two stop-create kinds; the ORIGINAL correlation for CANCEL_TARGET) and POST_UNKNOWN is persisted
    BEFORE the one POST — so a crash mid-create is reconcilable by key without a duplicate stop.
    Resolution reuses apply_stop_decision's confirmation. Evidence never gates this: the record is
    lane-owned. A prior unresolved attempt blocks a new create/cancel (query/recovery-only).
    """
    kind = _STOP_DECISION_KIND.get(decision)
    root = repo_root if repo_root is not None else STAGE_B_REPO_ROOT
    latch = stage_b_latch(state) or {}
    subject = latch.get("open_episode_event_id")
    prior = latch.get("pending_risk_reduction")
    prior_unresolved = isinstance(prior, dict) and prior.get("phase") in {
        "POST_UNKNOWN",
        "ACK_PENDING",
    }

    def _legacy(client_key: str | None = None) -> dict[str, Any] | None:
        return apply_stop_decision(
            decision,
            resting,
            lane_base,
            entry,
            api_key,
            secret,
            get_transport=get_transport,
            price_tick=price_tick,
            qty_step=qty_step,
            post_transport=post_transport,
            client_key=client_key,
        )

    if prior_unresolved:
        # No blind duplicate stop creation or cancel retry while an attempt is unresolved. A create/
        # replace/cancel is suppressed (recover sweep resolves it by key); noop/reconcile still run.
        return (resting if kind is not None else _legacy()), state
    if kind is None or epoch is None or not isinstance(subject, str):
        return _legacy(), state  # noop/reconcile, or no epoch/anchor -> compensating control only
    try:
        activation = stage_b.load_activation(root)
    except stage_b.StageBEvidenceError:
        return _legacy(), state
    target_alias: str | None = None
    if kind in {"STOP_REPLACE_CREATE", "CANCEL_TARGET"}:
        order_id = str(resting.get("order_id") or "") if isinstance(resting, dict) else ""
        if not order_id:
            return _legacy(), state  # no tracked target to anchor a replace/cancel -> legacy path
        target_alias = _alias(_alias_material(activation), "ord", order_id)
    if kind == "CANCEL_TARGET":
        # Appendix B: a fresh status query precedes any cancel POST. If the tracked target is
        # already confirmed cleared/filled, the cancel objective already holds — reconcile the
        # resting record and reserve no pending rather than issue a needless cancel. Any other
        # state (active/unknown) falls through to the reserved, POST_UNKNOWN-guarded cancel below,
        # whose legacy path confirms the terminal/cleared state by a second query after the POST.
        pre_state = _confirmed_stop_state(order_id, api_key, secret, get_transport)
        if pre_state == "cleared":
            return None, state
        if pre_state == "filled":
            return _filled_stop_record(cast(dict[str, Any], resting), order_id), state
    sequence = int(latch.get("risk_reduction_sequence", 0)) + 1
    if kind in _RISK_REDUCTION_CREATE_KINDS:
        if entry is None or lane_base <= 0 or price_tick is None or qty_step is None:
            return _legacy(), state  # a create needs bound economics; fall back rather than guess
        boundary = disaster_stop_price(entry)
        try:
            # Compute the quantized payload BEFORE reserving. A below-step qty / non-positive tick
            # is a deterministic pre-send LocalRejection: fall back to the compensating control (no
            # reservation, no POST_UNKNOWN, no uncaught exception crashing run_cycle's while loop),
            # mirroring the `entry is None or lane_base <= 0 ...` guard above.
            payload = {
                "side": "SELL",
                "order_type": "STOP_MARKET",
                "qty": str(quantize_stop_qty_down(lane_base, qty_step)),
                "quantity_unit": "BASE",
                "trigger_price": str(quantize_price_up(boundary, price_tick)),
                "order_filter": "StopOrder",
                "target_order_alias": target_alias,
            }
        except LocalRejection as error:
            print(
                f"protective-stop create locally rejected before any send: {error}", file=sys.stderr
            )
            return _legacy(), state
    else:  # CANCEL_TARGET placeholder (typed non-create)
        payload = {
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "0",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "order_filter": "StopOrder",
            "target_order_alias": target_alias,
        }
    pending = build_pending_risk_reduction(
        activation_epoch=epoch,
        subject_intent_event_id=subject,
        action_kind=kind,
        sequence=sequence,
        payload=payload,
    )
    state = reserve_risk_reduction(state, pending)
    client_key = (
        pending_client_key(pending, epoch) if kind in _RISK_REDUCTION_CREATE_KINDS else None
    )
    # Persist POST_UNKNOWN BEFORE the one create/cancel POST: a crash here stays query-only.
    state = advance_pending(state, "POST_UNKNOWN")
    new_resting = _legacy(client_key)
    if _stop_pending_resolved(decision, resting, new_resting):
        # Carry the freshly created/cleared resting stop into `state` BEFORE the latch-only
        # ACK_PENDING/clear writes (Finding H): otherwise those durable writes clobber the file
        # from a snapshot that still holds the OLD resting_stop, and a crash after clear_pending
        # would orphan the just-created venue stop (untracked next cycle).
        state = {**state, "resting_stop": new_resting}
        state = advance_pending(state, "ACK_PENDING")
        state = clear_pending(state)
    # else: leave POST_UNKNOWN -> blocks entries; the recover sweep reconciles it next cycle.
    return new_resting, state


# Bybit kline interval code -> (bar minutes, Timeframe, dataset-id label). The default "60" (1h)
# reproduces the original single-timeframe behavior EXACTLY (Timeframe.H1, +1h close, -1H- dataset
# id). The confluence activity lane also fetches 5m/15m/4h; every other path is byte-identical.
_INTERVAL_META: dict[str, tuple[int, Timeframe, str]] = {
    "5": (5, Timeframe.M5, "5M"),
    "15": (15, Timeframe.M15, "15M"),
    "60": (60, Timeframe.H1, "1H"),
    "240": (240, Timeframe.H4, "4H"),
}


def fetch_closed_bars(
    transport: pf.Transport, limit: int = KLINE_LIMIT, symbol: str = SYMBOL, interval: str = "60"
) -> tuple[MarketBar, ...]:
    """Public demo-venue klines -> chronological closed MarketBars (forming bar dropped).

    `symbol` defaults to SYMBOL (byte-identical ETH path); the multi-coin lane passes each coin, so
    the kline request and the MarketBar instrument/dataset identity are that coin's own.
    `interval` is the Bybit kline code; it defaults to "60" (1h) so the ETH/multi paths are
    byte-identical. The confluence lane passes 5m/15m/4h to evaluate a coin across timeframes.
    """
    try:
        minutes, timeframe, label = _INTERVAL_META[interval]
    except KeyError as error:
        raise ValueError(f"unsupported kline interval: {interval}") from error
    url = (
        f"{pf.DEMO_BASE}/v5/market/kline?category=spot&symbol={symbol}"
        f"&interval={interval}&limit={limit}"
    )
    rows = list(reversed(json.loads(transport(url, {}))["result"]["list"]))[:-1]
    base_coin = symbol.removesuffix("USDT")
    market = Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BYBIT_DEMO_SPOT"),
        InstrumentId(f"{base_coin}-USDT.BYBIT_DEMO_SPOT"),
        timeframe,
        DatasetId(f"DS-BYBIT-DEMO-{symbol}-{label}-LIVE"),
    )
    provenance = Provenance((DomainRef("EV-BYBIT-DEMO-KLINE-LIVE"),))
    now = datetime.now(UTC)
    return tuple(
        MarketBar(
            market=market,
            open_time=(open_time := datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)),
            close_time=open_time + timedelta(minutes=minutes),
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


def _price_history_path(symbol: str) -> Path:
    """Per-coin price-history path, next to that coin's heartbeat."""
    return LANE_DIR / f"price_history_{symbol}.json"


def _price_history_interval(interval: str) -> str:
    """Bybit kline code -> the compact timeframe label stored in the price-history file."""
    minutes = _INTERVAL_META[interval][0]
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h"


def write_price_history(
    symbol: str,
    interval: str,
    bars: tuple[MarketBar, ...],
    *,
    max_points: int = PRICE_HISTORY_MAX_POINTS,
) -> None:
    """Persist the closed-bar window the cycle ALREADY fetched as this coin's chart series.

    Reuses `bars` verbatim — this never issues a venue or network call of its own. The first write
    seeds the whole fetched window (real history immediately, not accumulated from zero); later
    cycles merge only genuinely new bars, de-duplicated by bar close time, so a re-fetched bar can
    never double-append. Points stay oldest->newest and are capped at `max_points` (oldest dropped),
    and the file is replaced atomically so a reader never observes a partial write.

    Non-critical bookkeeping: the caller runs this with the heartbeat write, AFTER every order path,
    and swallows any failure — it must never block, delay, or fail an order.
    """
    if not bars:
        return
    path = _price_history_path(symbol)
    label = _price_history_interval(interval)
    points: list[dict[str, str]] = []
    if path.is_file():
        existing = json.loads(path.read_text())
        # Only merge a series of the SAME timeframe; interleaving 5m and 1h closes would draw a
        # chart of bars that are not comparable, so a timeframe change restarts the series.
        if isinstance(existing, dict) and existing.get("interval") == label:
            points = [
                point
                for point in existing.get("points", [])
                if isinstance(point, dict) and "at" in point and "close" in point
            ]
    seen = {point["at"] for point in points}
    for bar in bars:
        at = bar.close_time.isoformat()
        if at not in seen:
            seen.add(at)
            points.append({"at": at, "close": str(bar.close)})
    points.sort(key=lambda point: point["at"])
    payload = {
        "schema_version": 1,
        "symbol": symbol,
        "interval": label,
        "updated_at": datetime.now(UTC).isoformat(),
        "max_points": max_points,
        "points": points[-max_points:],
    }
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


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


def _exit_create_or_freeze(
    intent: LaneIntent,
    state: dict[str, Any],
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Run an ACTIVE EXIT_CREATE risk reduction, degrading to the durable POST_UNKNOWN on failure
    instead of crashing the cycle.

    ponytail: ACCEPTED PRE-ACTIVATION DEBT (do NOT refactor place() to fix now). place()'s exit/Sell
    branch has pre-send calls that raise PLAIN ValueError, not LocalRejection — last_price (json
    parse), instrument_qty_step (metadata validation), and the pre-order wallet "before" read.
    active_risk_reduction's do_post catches ONLY LocalRejection, so such a deterministic pre-send
    metadata/parse error propagates AFTER POST_UNKNOWN was durably persisted, FREEZING the
    reservation query-only (never a clean rollback) and blocking further risk reduction until
    operator recovery. That freeze is FAIL-SAFE (never a duplicate create) and inert while
    NOT_ACTIVATED. Ceiling: an exit-path pre-send error freezes POST_UNKNOWN instead of rolling
    back. Upgrade path (activation hardening only): move the pre-send metadata/parse validation
    ahead of the reservation, OR convert THESE specific pre-send raises to LocalRejection — but NOT
    a blanket conversion, since last_price/wallet are also shared with POST-SEND contexts that MUST
    keep propagating (see the K1/K2 post-send tests that assert the raise directly). We only degrade
    the cycle here by re-reading the durable POST_UNKNOWN state; we NEVER clear or retry it, so a
    genuine post-send create can never be duplicated by this path.
    """
    try:
        return active_risk_reduction(
            intent,
            "EXIT_CREATE",
            state,
            api_key,
            secret,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
        )
    except ValueError as error:
        print(f"ACTIVE exit create froze at POST_UNKNOWN (pre-send debt): {error}", file=sys.stderr)
        return None, read_state()


def run_cycle(
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: rt.PostTransport = _live_post_transport,
    sleep: Any = time.sleep,
    capability: stage_b.LaneLockCapability | None = None,
    symbol: str = SYMBOL,
    entry_notional_budget: Decimal | None = None,
    interval: str = "60",
    signals_fn: Any = None,
    state_key: str | None = None,
    strategy: str | None = None,
    prefetched_bars: tuple[MarketBar, ...] | None = None,
    heartbeat_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One evaluation cycle: fresh signals newer than the cursor drive at most one action.

    `capability` (Stage B only): the exclusive lane-lock capability already held by `main()`. It is
    threaded into the sink-invoking entry path so evidence is committed UNDER the held lock, never
    re-acquiring it. None when NOT_ACTIVATED, or when ACTIVE but no lock was threaded (entries then
    fail closed rather than POST without a durable key).

    `symbol` defaults to the ETH lane's SYMBOL, so the single-symbol cycle is byte-identical (same
    state file, heartbeat, requests). The multi-coin lane calls this per coin.
    `entry_notional_budget` is the shared-total-capital headroom for a NEW entry: None (the default)
    means unlimited (legacy single lane); when set, a fresh entry whose BUY_QUOTE_USDT would exceed
    it is skipped (logged, never an error) while risk-reducing exits/stops on an already-open
    position still run.

    Confluence-lane hooks (ALL default to the byte-identical legacy behavior; the confluence lane is
    the only caller that sets them, and it always runs the NOT_ACTIVATED path):
      * `interval` — Bybit kline code fetched for the reference bar (default "60"=1h).
      * `signals_fn(bars) -> list` — replaces `canonical_signals` when set, so the caller injects a
        pre-computed decision instead of the ETH volume-breakout evaluation.
      * `state_key` — the per-coin state/heartbeat file key; defaults to `symbol`. The confluence
        lane passes `<SYMBOL>_activity` so its position is independent of the ETH/multi state.
      * `strategy` — tags order/ledger records and isolates this lane's ledger entry-price
        reconstruction from the untagged ETH/multi records.
      * `prefetched_bars` — reference bars already fetched by the caller (per-coin fetch cache), so
        N confluence evaluations reuse one reference fetch instead of re-requesting.
      * `heartbeat_extra` — merged into the heartbeat (the confluence score + contributing signals).
    """
    base_coin = symbol.removesuffix("USDT")
    key = state_key if state_key is not None else symbol
    state = read_state(key)
    cursor = state.get("cursor")
    lane_base = Decimal(str(state.get("lane_base", "0")))
    # Entry price drives the -15% stop. From state normally; reconstructed from the append-only
    # ledger for a position opened before this process started (restart safety). The ledger is
    # shared across coins, so it is filtered to THIS coin's (and, for the confluence lane, this
    # strategy's) own entries.
    entry_price = resolve_entry_price(state, _read_ledger_records(), symbol, strategy)
    stored_resting_stop = state.get("resting_stop")
    resting_stop, post_paths_safe, venue_stop_confirmation = preflight_tracked_stop(
        stored_resting_stop, api_key, secret, get_transport, symbol
    )
    if resting_stop is not stored_resting_stop and (
        resting_stop and resting_stop.get("state") == "FILLED_PENDING_RECONCILIATION"
    ):
        # Persist before any later read can fail, so a restart cannot forget the filled-stop latch.
        write_state({**state, "resting_stop": resting_stop}, key)
    bars = (
        prefetched_bars
        if prefetched_bars is not None
        else fetch_closed_bars(get_transport, symbol=symbol, interval=interval)
    )
    signals = signals_fn(bars) if signals_fn is not None else canonical_signals(bars)
    fresh = [s for s in signals if cursor is None or s.observed_at.isoformat() > cursor]
    action: dict[str, Any] | None = None
    if cursor is None:
        fresh = []  # first start: arm the cursor, trade only future transitions
    # Stage B (when ACTIVE) may latch ENTRY_BLOCK on evidence degradation or an unresolved attempted
    # create. That gate suppresses NEW risk-increasing entries ONLY — every risk-reducing path
    # (SELL exit, disaster stop, venue-stop reconciliation) below stays fully available. When
    # NOT_ACTIVATED this is always False, so the legacy flow is unchanged. Stage B is bound to the
    # single ETH lane only: the multi-coin path (any non-default symbol) always runs NOT_ACTIVATED,
    # so a non-ETH signal can never route through the ETH-hardcoded Stage B evidence chain.
    # The confluence lane (state_key/strategy set) ALWAYS runs NOT_ACTIVATED, so its injected
    # signals can never route through the ETH-hardcoded Stage B evidence chain.
    stage_b_on = stage_b_active() and symbol == SYMBOL and state_key is None and strategy is None
    # ACTIVE without a threaded lock cannot durably persist an entry key -> block new entries.
    new_entries_blocked = stage_b_on and (entry_blocked(state) or capability is None)
    if stage_b_on:
        # Restart safety (query-only, never reposts): reconcile a mid-flight entry by its committed
        # key, and reconcile any unresolved risk reduction by its derived key.
        recovered_base, recovered_entry, state = recover_unresolved_entry(
            state, api_key, secret, get_transport
        )
        if recovered_base is not None:
            lane_base, entry_price = recovered_base, recovered_entry
        pre_recovery_resting = state.get("resting_stop")
        state = recover_unresolved_risk_reduction(state, api_key, secret, get_transport)
        # Blocker 1: when recovery restores a tracked resting stop (Finding M), re-sync the LOCAL
        # resting_stop (mirrors the entry-recovery re-sync above). Otherwise stop_reconcile_action
        # below would see the stale pre-recovery value (typically None) and re-place a stop that
        # already rests on the venue -> a second create POST for one logical submission.
        if state.get("resting_stop") is not pre_recovery_resting:
            resting_stop = state.get("resting_stop")
    for signal in fresh if post_paths_safe else ():
        side = signal.side.value  # BUY | SELL
        if side == "BUY" and lane_base == 0 and not new_entries_blocked:
            if entry_notional_budget is not None and BUY_QUOTE_USDT > entry_notional_budget:
                # Shared total-capital cap reached: skip this NEW entry (logged, never an error).
                # Risk-reducing exits/stops below are never gated by the cap.
                print(
                    f"{symbol}: entry skipped — shared demo capital cap reached "
                    f"(need {BUY_QUOTE_USDT} USDT, budget {entry_notional_budget} USDT)",
                    file=sys.stderr,
                )
            elif stage_b_on:
                # ACTIVE: pre-submission chain committed (key home) before the POST; lane_base from
                # exact executions. The held capability is threaded so the sink runs under it.
                action, lane_base, entry_price, state = active_entry(
                    str(signal.signal_id),
                    state,
                    api_key,
                    secret,
                    get_transport=get_transport,
                    post_transport=post_transport,
                    sleep=sleep,
                    capability=capability,
                )
            else:
                action = place(
                    LaneIntent(
                        "Buy", BUY_QUOTE_USDT, "quoteCoin", str(signal.signal_id), "ENTRY_LONG"
                    ),
                    api_key,
                    secret,
                    get_transport=get_transport,
                    post_transport=post_transport,
                    sleep=sleep,
                    symbol=symbol,
                    strategy=strategy,
                )
                if action.get("ok"):
                    lane_base += Decimal(str(action["reconcile"][f"{base_coin}_delta"]))
                    entry_price = (
                        Decimal(str(action["avg_price"])) if action.get("avg_price") else None
                    )
        elif side == "SELL" and lane_base > 0:
            sell_intent = LaneIntent(
                "Sell", lane_base, "baseCoin", str(signal.signal_id), "EXIT_LONG"
            )
            if stage_b_on:
                action, state = _exit_create_or_freeze(
                    sell_intent,
                    state,
                    api_key,
                    secret,
                    get_transport=get_transport,
                    post_transport=post_transport,
                    sleep=sleep,
                )
            else:
                action = place(
                    sell_intent,
                    api_key,
                    secret,
                    get_transport=get_transport,
                    post_transport=post_transport,
                    sleep=sleep,
                    symbol=symbol,
                    strategy=strategy,
                )
            if action is not None and action.get("ok"):
                lane_base = Decimal("0")
                entry_price = None
                state = close_open_episode(state)
    latest_bar_close = bars[-1].close_time.isoformat() if bars else cursor

    # Disaster-stop guard — runs every cycle independent of strategy signals, so it protects a
    # position opened before this process started and one no fresh signal would exit. The local
    # close is the primary tail insurance; the venue-resting stop below is the process-death backup.
    stop_event: dict[str, Any] | None = None
    try:
        mark = last_price(get_transport, symbol)
    except Exception as error:  # noqa: BLE001 - no mark means no basis to trigger; skip this cycle
        print(f"disaster-stop mark unavailable: {error}", file=sys.stderr)
        mark = Decimal("0")
    if (
        post_paths_safe
        and lane_base > 0
        and entry_price is not None
        and disaster_stop_triggered(entry_price, mark)
    ):
        disaster_intent = LaneIntent(
            "Sell", lane_base, "baseCoin", "DISASTER_STOP_LOCAL", "DISASTER_STOP"
        )
        if stage_b_on:
            # Risk-reducing: lane-owned durability governs the create; evidence never blocks it. The
            # exit-create routes through _exit_create_or_freeze so an exit-path pre-send metadata/
            # parse error degrades to the durable POST_UNKNOWN (accepted debt) instead of crashing.
            closed, state = _exit_create_or_freeze(
                disaster_intent,
                state,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
            )
            closed = closed or {}
        else:
            closed = place(
                disaster_intent,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                symbol=symbol,
                strategy=strategy,
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
            state = close_open_episode(state)
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
            price_tick = instrument_price_tick(get_transport, symbol)
            qty_step = instrument_qty_step(get_transport, symbol)
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
            symbol=symbol,
        )
    if stage_b_on:
        # ACTIVE: the protective-stop create/replace/cleanup and cancel are routed through the
        # lane-owned durability protocol (deterministic key persisted before the one POST, then
        # reconciled). apply_stop_decision remains the unconditional compensating control inside it.
        resting_stop, state = active_stop_decision(
            decision,
            resting_stop,
            lane_base,
            entry_price,
            state,
            api_key,
            secret,
            epoch=stage_b_epoch(),
            get_transport=get_transport,
            post_transport=post_transport,
            price_tick=price_tick,
            qty_step=qty_step,
        )
    else:
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
            symbol=symbol,
        )

    final_state: dict[str, Any] = {
        "lane_base": str(lane_base),
        "cursor": latest_bar_close,
        "entry_price": str(entry_price) if entry_price is not None else None,
        "resting_stop": resting_stop,
    }
    # Carry the Stage B latch (pending records, evidence_state, episode anchor) forward when ACTIVE;
    # absent when NOT_ACTIVATED, so the persisted state stays byte-identical to today. When present,
    # persist through the durable 0600 writer so the final write never regresses the latch's mode.
    # (write_state_durable targets the ETH LANE_STATE; Stage B is bound to the single ETH lane, so
    # this branch is never reached on a non-default symbol.)
    stage_b_state = stage_b_latch(state)
    if stage_b_state is not None:
        final_state["stage_b_v2"] = stage_b_state
        write_state_durable(final_state)
    else:
        write_state(final_state, key)

    # Wallet and mark are captured every cycle, not only when an order fills. A lane that
    # trades rarely would otherwise show balances frozen at the last fill, and a stale
    # number presented as current is worse than no number.
    wallet_snapshot: dict[str, str] = {}
    mark_price = "0"
    try:
        wallet_snapshot = dict(rt.wallet(get_transport, api_key, secret, rt._now()))
        mark_price = str(last_price(get_transport, symbol))
    except Exception as error:  # noqa: BLE001 - snapshot is informational, never fatal
        wallet_snapshot = {}
        mark_price = "0"
        print(f"wallet/mark snapshot unavailable: {error}", file=sys.stderr)

    heartbeat = {
        "schema_version": 2,
        "at": datetime.now(UTC).isoformat(),
        # Default single/multi lane: the ETH volume-breakout candidate. The confluence lane names
        # its scored engine instead so the heartbeat is honestly attributed.
        "candidate": strategy if strategy is not None else "ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1",
        # The coin this heartbeat is for (ETHUSDT on the default single lane). The SAME already-
        # screened strategy runs on every coin; this is execution measurement ACROSS coins, NOT
        # validated per-coin edge.
        "symbol": symbol,
        "measurement_note": "execution-measurement across coins; NOT validated edge",
        "latest_closed_bar": latest_bar_close,
        "signals_in_window": len(signals),
        "fresh_signals": len(fresh),
        "lane_base": str(lane_base),
        "kill_switch": kill_switch_active(),
        "action": action,
        "wallet": wallet_snapshot,
        "mark_price": mark_price,
        # rule_levels evaluates the ETH volume-breakout band; it is meaningless for the confluence
        # roster, whose contributing signals are surfaced via heartbeat_extra instead.
        "rule_levels": rule_levels(bars) if strategy is None else {},
        "entry_price": str(entry_price) if entry_price is not None else None,
        "disaster_stop_price": str(disaster_stop_price(entry_price))
        if entry_price is not None
        else None,
        "disaster_stop_event": stop_event,
        "resting_stop": resting_stop,
        **LANE_LABEL,
    }
    # Surface the Stage B latch so an operator can see a frozen/unresolved risk reduction and the
    # evidence state. Only added when ACTIVE; NOT_ACTIVATED heartbeat stays byte-identical.
    final_latch = stage_b_latch(state)
    if final_latch is not None:
        pending_rr = final_latch.get("pending_risk_reduction")
        heartbeat["stage_b"] = {
            "evidence_state": final_latch.get("evidence_state"),
            "entry_blocked": entry_blocked(state),
            "open_episode_event_id": final_latch.get("open_episode_event_id"),
            "risk_reduction_phase": pending_rr.get("phase")
            if isinstance(pending_rr, dict)
            else None,
            # Surface which risk-reducing action (exit/stop-create/replace/cancel) is unresolved so
            # an operator can see a frozen protective-stop or cancel, not just a bare exit.
            "risk_reduction_kind": pending_rr.get("action_kind")
            if isinstance(pending_rr, dict)
            else None,
        }
    if strategy is not None:
        heartbeat["strategy"] = strategy
    if heartbeat_extra is not None:
        # Confluence score + contributing bullish/bearish signals, so the dashboard/report can show
        # WHY the coin is (or is not) in a position this cycle.
        heartbeat.update(heartbeat_extra)
    # Price history for the dashboard chart, written HERE with the heartbeat: every order path
    # (entry, exit, disaster stop, venue-stop reconcile/cancel) has already completed above, and the
    # final state has already been persisted, so nothing below can delay or fail an order. It reuses
    # `bars` — the window already fetched for signal evaluation — so it adds NO venue call. Any
    # failure is logged and swallowed: a broken chart file must never break the lane, least of all a
    # risk-reducing action.
    try:
        write_price_history(symbol, interval, bars)
    except Exception as error:  # noqa: BLE001 - chart series is informational, never fatal
        print(f"price history unavailable: {error}", file=sys.stderr)

    LANE_DIR.mkdir(parents=True, exist_ok=True)
    heartbeat_path = _heartbeat_path(key)
    tmp = heartbeat_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(heartbeat, sort_keys=True, indent=2))
    tmp.replace(heartbeat_path)
    return heartbeat


def open_demo_exposure(symbols: list[str]) -> Decimal:
    """Sum of per-coin buy notional currently open across the multi-coin lane.

    Each open position was entered at BUY_QUOTE_USDT, so an open coin contributes exactly that to
    the shared total-capital exposure regardless of subsequent mark drift. A coin never run has no
    state file and contributes nothing.
    """
    total = Decimal("0")
    for symbol in symbols:
        if Decimal(str(read_state(symbol).get("lane_base", "0"))) > 0:
            total += BUY_QUOTE_USDT
    return total


def run_multi_cycle(
    api_key: str,
    secret: str,
    *,
    symbols: list[str] | None = None,
    total_cap: Decimal = TOTAL_DEMO_CAPITAL_USDT,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: rt.PostTransport = _live_post_transport,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """One multi-coin cycle: run the per-symbol `run_cycle` for each coin in the universe.

    Demo/fake money, execution-measurement only — the SAME already-screened strategy on every coin,
    NOT validated per-coin edge. Safety composition:
      * SHARED kill switch — checked ONCE up front; if set, ALL coins halt and nothing runs.
      * SHARED total-capital cap — a new entry that would push total open buy notional past
        `total_cap` is skipped (logged, not an error); already-open coins still run their
        risk-reducing exits/stops.
      * one coin's failure never aborts the others (caught, logged, the cycle continues).
    Every per-coin position, stop, and the -15% disaster stop remain fully independent and apply
    per coin, inheriting the same kill-switch/notional-cap/quantize guards as the single ETH lane.
    """
    coin_list = list(symbols if symbols is not None else DEMO_COINS)
    if kill_switch_active():
        # Shared kill switch halts ALL coins: do nothing, place no order for any coin.
        return {
            "kill_switch": True,
            "coins": {symbol: {"stage": "kill_switch"} for symbol in coin_list},
            **LANE_LABEL,
        }
    # Seed the shared budget from exposure already open, then decrement as coins enter this cycle.
    remaining = total_cap - open_demo_exposure(coin_list)
    coins: dict[str, Any] = {}
    for symbol in coin_list:
        was_open = Decimal(str(read_state(symbol).get("lane_base", "0"))) > 0
        try:
            heartbeat = run_cycle(
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                symbol=symbol,
                entry_notional_budget=remaining,
            )
            coins[symbol] = {
                "lane_base": heartbeat["lane_base"],
                "fresh_signals": heartbeat["fresh_signals"],
                "action": heartbeat.get("action"),
                "entry_price": heartbeat.get("entry_price"),
                "resting_stop": heartbeat.get("resting_stop"),
            }
            now_open = Decimal(str(heartbeat["lane_base"])) > 0
            if now_open and not was_open:
                # A fresh entry consumed one BUY_QUOTE_USDT of the shared cap this cycle.
                remaining -= BUY_QUOTE_USDT
        except Exception as error:  # noqa: BLE001 - one coin must never abort the whole cycle
            print(f"{symbol}: cycle failed, continuing other coins: {error}", file=sys.stderr)
            coins[symbol] = {"error": str(error)}
    return {
        "kill_switch": False,
        "total_cap": str(total_cap),
        "remaining_budget": str(remaining),
        "coins": coins,
        **LANE_LABEL,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="D-104 demo measurement lane (ETH or multi-coin).")
    # --once / --multi / --activity select the lane; --loop is an orthogonal cadence modifier so it
    # can combine with --activity. Bare `--loop` (dashboard START) and bare `--once` (RUN_ONCE) both
    # still resolve to the ETH lane, so the dashboard spawn contract is unchanged.
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one ETH evaluation cycle")
    mode.add_argument(
        "--multi",
        action="store_true",
        help="run one multi-coin cycle across the demo coin universe (shared cap + kill switch)",
    )
    mode.add_argument(
        "--activity",
        action="store_true",
        help="run a multi-timeframe confluence cycle across the ~40-coin universe (one scored "
        "long per coin; shared cap + kill switch). Add --loop to keep scoring until killed",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="repeat cycles until killed — the ETH lane hourly, or the confluence lane per bar "
        "when combined with --activity",
    )
    parser.add_argument(
        "--interval",
        default="15m",
        choices=("5m", "15m", "1h", "4h"),
        help="confluence reference/fastest timeframe (default 15m); 1h and 4h are always added",
    )
    # DEFAULT OFF. Without this flag nothing in the perp short path is ever reached and every lane
    # below behaves exactly as it did before shorts existed.
    parser.add_argument(
        "--shorts",
        action="store_true",
        help="--activity only: also run the DEFAULT-DISABLED Bybit perp SHORT side (1x, isolated, "
        "verified per symbol; shares the SAME total capital cap as the long side)",
    )
    # Absent (the default) => the FULL universe, exactly as before. Present => a validated subset,
    # which is how a first live --shorts contact is kept to one symbol.
    parser.add_argument(
        "--symbols",
        default=None,
        help="--activity only: comma-separated subset of the activity universe to score, e.g. "
        "BTCUSDT. Every value must already be in ACTIVITY_UNIVERSE. Default: the full universe",
    )
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    if args.activity:
        # The confluence activity lane is execution-measurement, always NOT_ACTIVATED. It shares
        # the single lane.lock so it can never run alongside the ETH/multi lanes and double-trade.
        import scripts.demo_activity_lane as activity  # local import avoids an import cycle

        # Validated BEFORE the lane lock: a bad --symbols is a usage error, not a lane run.
        try:
            symbols = (
                activity.ACTIVITY_UNIVERSE
                if args.symbols is None
                else activity.parse_symbols(args.symbols)
            )
        except ValueError as error:
            print(str(error))
            return 2
        with exclusive_lane_lock() as acquired:
            if not acquired:
                print("another demo lane is already running — refusing to start a second one.")
                return 3
            # `demo_perp_short.SHORTS_ENABLED` is the single default (False); --shorts can only
            # ever turn shorts ON, never off, so the two switches cannot drift into "enabled".
            return activity.run_activity_lane(
                api_key,
                secret,
                interval=args.interval,
                loop=args.loop,
                shorts=args.shorts or activity.perp.SHORTS_ENABLED,
                symbols=symbols,
            )
    if args.multi:
        # Multi-coin is execution-measurement, always NOT_ACTIVATED (per-coin Stage B is out of
        # scope). It shares the single lane.lock with the ETH lane so the two can never run at once
        # and double-trade ETHUSDT (which is one of the coins in the universe).
        with exclusive_lane_lock() as acquired:
            if not acquired:
                print("another demo lane is already running — refusing to start a second one.")
                return 3
            return _run_multi_lane(api_key, secret)
    # When Stage B is ACTIVE, hold the Wave 1 lane-lock CAPABILITY (same lane.lock, exclusive) and
    # thread it into run_cycle so the sink is invoked under the already-held lock — never a second
    # flock on the same file. When NOT_ACTIVATED, keep the legacy boolean lock, byte-identical.
    if stage_b_active():
        try:
            with stage_b.exclusive_lane_lock_capability(STAGE_B_REPO_ROOT) as capability:
                return _run_lane(api_key, secret, loop=args.loop, capability=capability)
        except stage_b.StageBEvidenceError:
            print("another ETH demo lane is already running — refusing to start a second one.")
            return 3
    with exclusive_lane_lock() as acquired:
        if not acquired:
            print("another ETH demo lane is already running — refusing to start a second one.")
            return 3
        return _run_lane(api_key, secret, loop=args.loop, capability=None)


def _run_lane(
    api_key: str,
    secret: str,
    *,
    loop: bool,
    capability: stage_b.LaneLockCapability | None,
) -> int:
    """Preflight then run the cycle loop, threading the held Stage B capability (if any)."""
    pre = pf.preflight(pf._urllib_transport, api_key, secret)
    if not pre.get("ok"):
        print(json.dumps({"ok": False, "stage": "preflight", "preflight": pre}, indent=2))
        return 1
    mode_label = "loop" if loop else "once"
    print(f"preflight GREEN on {pre['host']} — ETH measurement lane ({mode_label})")
    while True:
        heartbeat = run_cycle(api_key, secret, capability=capability)
        print(json.dumps(heartbeat, indent=2, sort_keys=True))
        if not loop:
            return 0
        if kill_switch_active():
            print("KILL_SWITCH present — lane stopped.")
            return 0
        now = datetime.now(UTC)
        next_hour = (now + timedelta(hours=1)).replace(minute=1, second=0, microsecond=0)
        time.sleep(max(60.0, (next_hour - now).total_seconds()))


def _run_multi_lane(api_key: str, secret: str) -> int:
    """Preflight once, then run a single multi-coin cycle across the demo coin universe."""
    pre = pf.preflight(pf._urllib_transport, api_key, secret)
    if not pre.get("ok"):
        print(json.dumps({"ok": False, "stage": "preflight", "preflight": pre}, indent=2))
        return 1
    print(
        f"preflight GREEN on {pre['host']} — multi-coin demo measurement lane "
        f"({len(DEMO_COINS)} coins, shared cap {TOTAL_DEMO_CAPITAL_USDT} USDT)"
    )
    report = run_multi_cycle(api_key, secret)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
