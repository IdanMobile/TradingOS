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
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
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


def instrument_qty_step(transport: pf.Transport) -> Decimal:
    url = f"{pf.DEMO_BASE}/v5/market/instruments-info?category=spot&symbol={SYMBOL}"
    payload = json.loads(transport(url, {}))
    rows = payload.get("result", {}).get("list", [])
    step = rows[0].get("lotSizeFilter", {}).get("basePrecision") if rows else None
    return Decimal(str(step)) if step else FALLBACK_QTY_STEP


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
    lane_base: Decimal, entry: Decimal | None, resting: dict[str, Any] | None
) -> str:
    """Idempotent venue-stop bookkeeping decision: 'place' | 'replace' | 'cancel' | 'noop'.

    Flat -> no stop should rest. Open with a known entry -> exactly one stop at the -15% level
    sized to the position; an already-matching resting stop is a no-op (idempotent), a stale
    level/qty is a replace. Unknown entry -> noop (the local stop still guards the position).
    """
    if lane_base <= 0:
        return "cancel" if resting else "noop"
    if entry is None or entry <= 0:
        return "noop"
    if resting is None:
        return "place"
    same = (
        Decimal(str(resting.get("trigger_price", "0"))) == disaster_stop_price(entry)
        and Decimal(str(resting.get("base_qty", "0"))) == lane_base
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
    api_key: str,
    secret: str,
    *,
    post_transport: rt.PostTransport = _live_post_transport,
) -> dict[str, Any]:
    """Rest a demo Sell stop at trigger_price via the quarantined order transport (rt.place_stop).

    The order-endpoint literals stay confined to scripts/demo_roundtrip.py; the lane only binds
    the symbol/params. Demo host only, no new authority.
    """
    return rt.place_stop(
        post_transport,
        api_key,
        secret,
        rt._now(),
        pf.DEMO_BASE,
        symbol=SYMBOL,
        trigger_price=str(trigger_price),
        base_qty=str(base_qty),
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


def apply_stop_decision(
    decision: str,
    resting: dict[str, Any] | None,
    lane_base: Decimal,
    entry: Decimal | None,
    api_key: str,
    secret: str,
    *,
    post_transport: rt.PostTransport = _live_post_transport,
) -> dict[str, Any] | None:
    """Execute a stop_reconcile_action decision; return the new resting-stop record (or None).

    Best-effort secondary protection: on any venue error the resting record is left unchanged
    (or cleared) and the NEXT cycle retries — the local disaster-stop remains primary throughout.
    """
    if decision == "noop":
        return resting
    if decision in {"cancel", "replace"} and resting and resting.get("order_id"):
        try:
            cancel_stop_order(
                str(resting["order_id"]), api_key, secret, post_transport=post_transport
            )
        except Exception as error:  # noqa: BLE001 - cancel is best-effort; local stop is primary
            print(f"venue stop cancel failed: {error}", file=sys.stderr)
        resting = None
    if decision in {"place", "replace"} and entry is not None and lane_base > 0:
        trigger = disaster_stop_price(entry)
        try:
            placed = place_stop_order(
                lane_base, trigger, api_key, secret, post_transport=post_transport
            )
        except Exception as error:  # noqa: BLE001 - place is best-effort; local stop is primary
            print(f"venue stop place failed: {error}", file=sys.stderr)
            return None
        if placed.get("retCode") == 0:
            return {
                "order_id": str(placed.get("result", {}).get("orderId", "")),
                "trigger_price": str(trigger),
                "base_qty": str(lane_base),
            }
        print(f"venue stop place rejected: {placed.get('retMsg')}", file=sys.stderr)
        return None
    return resting


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
    bars = fetch_closed_bars(get_transport)
    signals = canonical_signals(bars)
    state = read_state()
    cursor = state.get("cursor")
    lane_base = Decimal(str(state.get("lane_base", "0")))
    # Entry price drives the -15% stop. From state normally; reconstructed from the append-only
    # ledger for a position opened before this process started (restart safety).
    entry_price = resolve_entry_price(state, _read_ledger_records())
    resting_stop = state.get("resting_stop")
    fresh = [s for s in signals if cursor is None or s.observed_at.isoformat() > cursor]
    action: dict[str, Any] | None = None
    if cursor is None:
        fresh = []  # first start: arm the cursor, trade only future transitions
    for signal in fresh:
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
    if lane_base > 0 and entry_price is not None and disaster_stop_triggered(entry_price, mark):
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
    # cancelled when flat. Idempotent — an already-matching resting stop is left untouched.
    decision = stop_reconcile_action(lane_base, entry_price, resting_stop)
    resting_stop = apply_stop_decision(
        decision,
        resting_stop,
        lane_base,
        entry_price,
        api_key,
        secret,
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
