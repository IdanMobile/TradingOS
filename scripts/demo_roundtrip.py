#!/usr/bin/env python3
"""Bybit DEMO execution — prove order -> fill -> reconcile, and run an observable session.

Reuses the preflight's signing + demo-host lock, adds signed POSTs to place small spot market
orders on the Bybit demo account, polls to Filled, and reconciles wallet balances.

  * `run_roundtrip` — one market BUY, reconciled (leaves a tiny demo position).
  * `open_and_close_cycle` / `session` — a DUMMY signal that opens then closes a position each
    cycle, so it stays flat; run it to watch the lane work (also visible in the Bybit demo UI).

Safety rails: demo host only (api-demo.bybit.com); a GREEN preflight is required before any
order; every order is capped at MAX_NOTIONAL USDT. MACHINERY test — no strategy is validated;
real execution_authority stays NONE. See docs/program/DEMO_LANE_PLAN.md.

Run: python scripts/demo_roundtrip.py --cycles 3     # open+close 3 times, end flat

ponytail: stdlib only; transports are injectable so the flow is unit-tested offline with no
network. BTCUSDT base step is hardcoded (1e-6) — add an instrument-info lookup for more symbols.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402

MAX_NOTIONAL = 50.0  # hard cap (USDT) on any single demo order
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_QUOTE_QTY = 25.0  # spend this many (fake) USDT on the market buy
BASE_STEP_DECIMALS = 6  # BTCUSDT base precision (1e-6); lookup instrument-info for other symbols

PostTransport = Callable[[str, dict[str, str], bytes], bytes]

# --- Stage B (default-disabled) Bybit V5 client-key + reconciliation adapter --------------------
# The venue-supported client correlation field is `orderLinkId` (Spot: optional at the API, but
# Stage B makes it mandatory and validates it). Bybit does NOT document exactly-once delivery, so
# the key is correlation only: persist before POST (owned by the lane), reuse for the same logical
# attempt, never blindly resubmit, and reconcile. Acknowledgements are asynchronous. These helpers
# are pure request/response adapters — they carry no persistence and no order-creation authority.

_CLIENT_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,36}$")
# Stage B applies the stricter internal cap of 50 rows/page to ALL three endpoints and at most 100
# pages per endpoint (official maxima are 50 for realtime/history and 100 for execution). A cursor
# loop, oversized page, or remaining cursor at the bound is UNRESOLVED, never an empty result.
_INTERNAL_ROWS_PER_PAGE = 50
_MAX_PAGES_PER_ENDPOINT = 100
CREATE_ACK_ACCEPTED = "ACKNOWLEDGED_PENDING"
CREATE_ACK_REJECTED = "VENUE_REJECTED"


class ReconciliationUnresolved(RuntimeError):
    """Pagination could not be safely exhausted (cursor loop, oversized page, page/row overflow)."""


class ExecutionConflict(RuntimeError):
    """A duplicate execId carried conflicting economics — a fail-closed reconciliation incident."""


def validate_client_key(value: object) -> str:
    """Enforce the Bybit `orderLinkId` contract: ^[A-Za-z0-9_-]{1,36}$ (length 1..36)."""
    if not isinstance(value, str) or not _CLIENT_KEY_RE.fullmatch(value):
        raise ValueError(f"orderLinkId must match ^[A-Za-z0-9_-]{{1,36}}$: {value!r}")
    return value


def classify_create_ack(response: dict[str, Any]) -> str:
    """A create/cancel ack means ACCEPTED/PENDING, never FILLED/terminal. retCode==0 => pending."""
    return CREATE_ACK_ACCEPTED if response.get("retCode") == 0 else CREATE_ACK_REJECTED


def dedupe_executions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate execution rows by `execId` and return them in deterministic order.

    An identical duplicate row is dropped; a duplicate `execId` with conflicting content is a
    fail-closed incident. Equal `execTime` rows are ordered by the documented
    `execId`+`orderId`+`leavesQty` guidance before raw IDs are ever sanitized.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        exec_id = row.get("execId")
        if not isinstance(exec_id, str) or not exec_id:
            raise ReconciliationUnresolved("execution row missing execId")
        prior = by_id.get(exec_id)
        if prior is None:
            by_id[exec_id] = row
        elif prior != row:
            raise ExecutionConflict(f"conflicting duplicate execId {exec_id}")
    return sorted(
        by_id.values(),
        key=lambda r: (
            str(r.get("execTime", "")),
            str(r.get("execId", "")),
            str(r.get("orderId", "")),
            str(r.get("leavesQty", "")),
        ),
    )


def _paged_by_client_key(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    base: str,
    path: str,
    client_key: str,
    symbol: str,
) -> list[dict[str, Any]]:
    """Exhaust one endpoint filtered by `orderLinkId`, honoring the internal page/row caps.

    Returns every row across pages; raises ReconciliationUnresolved on a cursor loop, an oversized
    page, or an unfinished cursor at the page bound (never a silent empty result).
    """
    validate_client_key(client_key)
    rows: list[dict[str, Any]] = []
    cursor = ""
    seen_cursors: set[str] = set()
    for _page in range(_MAX_PAGES_PER_ENDPOINT):
        params = {
            "category": "spot",
            "symbol": symbol,
            "orderLinkId": client_key,
            "limit": str(_INTERNAL_ROWS_PER_PAGE),
        }
        if cursor:
            params["cursor"] = cursor
        resp = pf._signed_get(transport, base, path, params, api_key, secret, _now())
        result = resp.get("result") or {}
        page_rows = result.get("list") or []
        if len(page_rows) > _INTERNAL_ROWS_PER_PAGE:
            raise ReconciliationUnresolved(f"{path} page exceeded the internal 50-row cap")
        rows.extend(page_rows)
        cursor = str(result.get("nextPageCursor") or "")
        if not cursor:
            return rows
        if cursor in seen_cursors:
            raise ReconciliationUnresolved(f"{path} pagination cursor loop")
        seen_cursors.add(cursor)
    raise ReconciliationUnresolved(f"{path} pagination exceeded the internal 100-page cap")


def orders_by_client_key(
    transport: pf.Transport, api_key: str, secret: str, base: str, client_key: str, symbol: str
) -> list[dict[str, Any]]:
    """Open/closed orders from /v5/order/realtime for one client key."""
    return _paged_by_client_key(
        transport, api_key, secret, base, "/v5/order/realtime", client_key, symbol
    )


def order_history_by_client_key(
    transport: pf.Transport, api_key: str, secret: str, base: str, client_key: str, symbol: str
) -> list[dict[str, Any]]:
    """Durable closed history from /v5/order/history for one client key (realtime-miss fallback)."""
    return _paged_by_client_key(
        transport, api_key, secret, base, "/v5/order/history", client_key, symbol
    )


def executions_by_client_key(
    transport: pf.Transport, api_key: str, secret: str, base: str, client_key: str, symbol: str
) -> list[dict[str, Any]]:
    """Economic execution rows from /v5/execution/list for one client key (deduplicated)."""
    rows = _paged_by_client_key(
        transport, api_key, secret, base, "/v5/execution/list", client_key, symbol
    )
    return dedupe_executions(rows)


def _match_by_client_key(rows: list[dict[str, Any]], client_key: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("orderLinkId", "")) == client_key:
            return row
    return None


def reconcile_by_client_key(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    base: str,
    client_key: str,
    symbol: str,
) -> dict[str, Any]:
    """Reconcile one logical submission by its client key: realtime, then history, then executions.

    A realtime miss is not "no order" — history and executions are always consulted. The create is
    NEVER replayed here. Returns status/source/order/executions; pagination that cannot be
    exhausted raises ReconciliationUnresolved rather than returning an empty (falsely terminal) set.
    """
    realtime = orders_by_client_key(transport, api_key, secret, base, client_key, symbol)
    order_row = _match_by_client_key(realtime, client_key)
    source = "REALTIME"
    if order_row is None:
        history = order_history_by_client_key(transport, api_key, secret, base, client_key, symbol)
        order_row = _match_by_client_key(history, client_key)
        source = "HISTORY"
    executions = executions_by_client_key(transport, api_key, secret, base, client_key, symbol)
    return {
        "status": order_row.get("orderStatus") if order_row else None,
        "source": source if order_row else None,
        "order": order_row,
        "executions": executions,
        "all_pages_complete": True,
    }


def sign_post(secret: str, timestamp: str, api_key: str, body: str) -> str:
    """Bybit V5 POST signature: HMAC-SHA256 over timestamp + apiKey + recvWindow + rawBody."""
    payload = f"{timestamp}{api_key}{pf.RECV_WINDOW}{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _order_create(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    order: dict[str, str],
) -> dict[str, Any]:
    pf.require_demo_base(base)
    if "orderLinkId" in order:
        # Stage B (or any caller) may bind a persisted client key; it is validated before it is
        # ever sent so a malformed key can never reach the venue. The key is persisted upstream.
        validate_client_key(order["orderLinkId"])
    body = json.dumps(order)
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": pf.RECV_WINDOW,
        "X-BAPI-SIGN": sign_post(secret, timestamp, api_key, body),
        "Content-Type": "application/json",
    }
    decoded = json.loads(post_transport(f"{base}/v5/order/create", headers, body.encode()))
    return decoded if isinstance(decoded, dict) else {}


def place_stop(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    *,
    symbol: str,
    trigger_price: str,
    base_qty: str,
    client_key: str | None = None,
) -> dict[str, Any]:
    """Rest a spot Sell stop (Bybit V5 conditional order) via the quarantined create transport.

    orderFilter=StopOrder, triggerDirection=2 (fire when the last price falls to/through
    triggerPrice), Market exit. The order-create endpoint literal stays confined to this module.

    `client_key` (Stage B only): a persisted `orderLinkId` bound to this logical stop create; it is
    validated inside `_order_create` before it can reach the venue. The retCode=0 acknowledgement is
    ASYNC (accepted/pending, never resting-confirmed) — the caller confirms by query. When None the
    order body is byte-identical to the legacy compensating stop.
    """
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": base_qty,
        "marketUnit": "baseCoin",
        "orderFilter": "StopOrder",
        "triggerPrice": trigger_price,
        "triggerDirection": "2",
    }
    if client_key is not None:
        order["orderLinkId"] = client_key  # validated in _order_create before it reaches venue
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def cancel_order(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    base: str,
    *,
    order_id: str = "",
    symbol: str,
    order_filter: str = "StopOrder",
    order_link_id: str | None = None,
) -> dict[str, Any]:
    """Cancel an order by its ORIGINAL correlation (Bybit V5 /v5/order/cancel). Demo-host-locked.

    Targets exactly one of the venue `orderId` or the original `orderLinkId` (client key) — the
    cancel NEVER derives a new correlation. The retCode=0 acknowledgement is ASYNC; the caller must
    confirm the terminal/cleared state by query and never clears state on the ack alone.
    """
    pf.require_demo_base(base)
    if order_link_id is not None:
        validate_client_key(order_link_id)
    if bool(order_id) == bool(order_link_id):
        raise ValueError("cancel_order needs exactly one of order_id / order_link_id")
    target = {"orderId": order_id} if order_id else {"orderLinkId": str(order_link_id)}
    # Key order matters: the legacy by-orderId body must stay byte-identical to pre-Wave-2
    # (category, symbol, orderId, orderFilter). The new orderLinkId path slots in the same slot.
    body = json.dumps({"category": "spot", "symbol": symbol, **target, "orderFilter": order_filter})
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": pf.RECV_WINDOW,
        "X-BAPI-SIGN": sign_post(secret, timestamp, api_key, body),
        "Content-Type": "application/json",
    }
    decoded = json.loads(post_transport(f"{base}/v5/order/cancel", headers, body.encode()))
    return decoded if isinstance(decoded, dict) else {}


def place_market_buy(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
) -> dict[str, Any]:
    """Spot market BUY sized in quote (USDT). Demo-host-locked and notional-capped."""
    if quote_qty > MAX_NOTIONAL:
        raise ValueError(f"order notional {quote_qty} exceeds the {MAX_NOTIONAL} USDT cap")
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Buy",
        "orderType": "Market",
        "qty": str(quote_qty),
        "marketUnit": "quoteCoin",  # qty is the USDT amount to spend
    }
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def place_market_sell(
    post_transport: PostTransport,
    api_key: str,
    secret: str,
    timestamp: str,
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
    base_qty: float,
) -> dict[str, Any]:
    """Spot market SELL sized in base (e.g. BTC) — closes a position back to cash."""
    order = {
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": str(base_qty),
        "marketUnit": "baseCoin",
    }
    return _order_create(post_transport, api_key, secret, timestamp, base, order)


def order_status(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    timestamp: str,
    order_id: str = "",
    *,
    base: str = pf.DEMO_BASE,
    symbol: str = DEFAULT_SYMBOL,
    client_key: str | None = None,
) -> dict[str, Any]:
    """Fetch one order's live status (signed GET /v5/order/realtime).

    `client_key` (Stage B only): query by the persisted `orderLinkId` instead of the venue orderId,
    so a create whose orderId was never observed is still reconcilable by its original correlation.
    Exactly one of order_id / client_key is used.
    """
    if client_key is not None:
        if order_id:
            raise ValueError("order_status needs exactly one of order_id / client_key")
        validate_client_key(client_key)
        selector = {"orderLinkId": client_key}
    else:
        # Legacy positional call (no client_key): stay byte-identical to pre-Wave-2. An empty
        # orderId (e.g. a create ack that returned no orderId) queries by "" and returns {} silently
        # rather than raising; exactly-one enforcement applies ONLY to the new client_key usage.
        selector = {"orderId": order_id}
    resp = pf._signed_get(
        transport,
        base,
        "/v5/order/realtime",
        {"category": "spot", "symbol": symbol, **selector},
        api_key,
        secret,
        timestamp,
    )
    orders = resp.get("result", {}).get("list", [])
    return orders[0] if orders else {}


def wallet(transport: pf.Transport, api_key: str, secret: str, timestamp: str) -> dict[str, str]:
    resp = pf._signed_get(
        transport,
        pf.DEMO_BASE,
        "/v5/account/wallet-balance",
        {"accountType": "UNIFIED"},
        api_key,
        secret,
        timestamp,
    )
    return pf._balances(resp)


def _now() -> str:
    return str(int(time.time() * 1000))


def _round_down(value: float, decimals: int) -> float:
    factor = 10**decimals
    return math.floor(value * factor) / factor


_TERMINAL = {"Filled", "Cancelled", "Rejected", "PartiallyFilledCanceled"}


def _poll_filled(
    transport: pf.Transport,
    api_key: str,
    secret: str,
    order_id: str,
    symbol: str,
    sleep: Callable[[float], None],
    *,
    client_key: str | None = None,
) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for _ in range(12):
        sleep(0.5)
        status = order_status(
            transport, api_key, secret, _now(), order_id, symbol=symbol, client_key=client_key
        )
        if status.get("orderStatus") in _TERMINAL:
            break
    return status


def _post_transport(url: str, headers: dict[str, str], body: bytes) -> bytes:
    raise RuntimeError(pf.NETWORK_QUARANTINE)


def _delta(before: dict[str, str], after: dict[str, str], coin: str) -> float:
    return float(after.get(coin, "0") or 0) - float(before.get(coin, "0") or 0)


def run_roundtrip(
    api_key: str,
    secret: str,
    *,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Preflight -> snapshot -> market buy -> poll to Filled -> snapshot -> reconcile."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    before = pre["balances"]
    placed = place_market_buy(
        post_transport, api_key, secret, _now(), symbol=symbol, quote_qty=quote_qty
    )
    if placed.get("retCode") != 0:
        return {"ok": False, "stage": "place", "error": str(placed.get("retMsg")), "raw": placed}
    order_id = str(placed.get("result", {}).get("orderId", ""))
    status = _poll_filled(get_transport, api_key, secret, order_id, symbol, sleep)
    after = wallet(get_transport, api_key, secret, _now())
    base_coin = symbol.removesuffix("USDT")
    return {
        "ok": status.get("orderStatus") == "Filled",
        "stage": "done",
        "order_id": order_id,
        "order_status": status.get("orderStatus"),
        "symbol": symbol,
        "filled_qty": status.get("cumExecQty"),
        "avg_price": status.get("avgPrice"),
        "fee": status.get("cumExecFee"),
        "reconcile": {
            f"{base_coin}_delta": round(_delta(before, after, base_coin), 8),
            "USDT_delta": round(_delta(before, after, "USDT"), 4),
        },
        "balances_before": before,
        "balances_after": after,
    }


def open_and_close_cycle(
    api_key: str,
    secret: str,
    *,
    symbol: str = DEFAULT_SYMBOL,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """One dummy-signal cycle: BUY a small amount, then SELL it back to flat. Reconciled."""
    base_coin = symbol.removesuffix("USDT")
    before = wallet(get_transport, api_key, secret, _now())
    buy = place_market_buy(
        post_transport, api_key, secret, _now(), symbol=symbol, quote_qty=quote_qty
    )
    if buy.get("retCode") != 0:
        return {"ok": False, "stage": "buy", "error": str(buy.get("retMsg"))}
    buy_status = _poll_filled(
        get_transport, api_key, secret, str(buy["result"]["orderId"]), symbol, sleep
    )
    mid = wallet(get_transport, api_key, secret, _now())
    net_base = _round_down(_delta(before, mid, base_coin), BASE_STEP_DECIMALS)
    if net_base <= 0:
        return {"ok": False, "stage": "sell", "error": "no base received to close"}
    sell = place_market_sell(
        post_transport, api_key, secret, _now(), symbol=symbol, base_qty=net_base
    )
    if sell.get("retCode") != 0:
        return {"ok": False, "stage": "sell", "error": str(sell.get("retMsg")), "held": net_base}
    sell_status = _poll_filled(
        get_transport, api_key, secret, str(sell["result"]["orderId"]), symbol, sleep
    )
    after = wallet(get_transport, api_key, secret, _now())
    return {
        "ok": sell_status.get("orderStatus") == "Filled",
        "qty": net_base,
        "entry_price": buy_status.get("avgPrice"),
        "exit_price": sell_status.get("avgPrice"),
        "buy_fee": buy_status.get("cumExecFee"),
        "sell_fee": sell_status.get("cumExecFee"),
        "usdt_net": round(_delta(before, after, "USDT"), 4),
        "residual_base": round(_delta(before, after, base_coin), 8),
    }


def session(
    api_key: str,
    secret: str,
    *,
    cycles: int = 3,
    quote_qty: float = DEFAULT_QUOTE_QTY,
    log: Callable[[str], None] = print,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: PostTransport = _post_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run `cycles` dummy open+close cycles, logging each. Ends flat. Requires a GREEN preflight."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    log(f"preflight GREEN on {pre['host']} — running {cycles} demo open+close cycle(s)")
    results: list[dict[str, Any]] = []
    for index in range(1, cycles + 1):
        cycle = open_and_close_cycle(
            api_key,
            secret,
            quote_qty=quote_qty,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
        )
        results.append(cycle)
        if cycle.get("ok"):
            log(
                f"cycle {index}: BUY {cycle['qty']} BTC @ {cycle['entry_price']} -> "
                f"SELL @ {cycle['exit_price']}  net {cycle['usdt_net']} USDT (fees)"
            )
        else:
            log(f"cycle {index}: STOPPED at {cycle.get('stage')} — {cycle.get('error')}")
        sleep(1.0)
    filled = sum(1 for c in results if c.get("ok"))
    return {
        "ok": filled == cycles,
        "cycles_requested": cycles,
        "cycles_filled": filled,
        "total_usdt_net": round(sum(float(c.get("usdt_net", 0) or 0) for c in results), 4),
        "cycles": results,
        "note": "Demo/fake money, ends flat. Machinery test only — no strategy is validated; "
        "real execution_authority stays NONE.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bybit demo execution round-trip / session.")
    parser.add_argument("--cycles", type=int, default=3, help="open+close cycles to run")
    parser.add_argument("--quote", type=float, default=DEFAULT_QUOTE_QTY, help="USDT per order")
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = session(api_key, secret, cycles=args.cycles, quote_qty=args.quote)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
