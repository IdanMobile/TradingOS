#!/usr/bin/env python3
"""DEFAULT-DISABLED short side for the demo confluence lane — Bybit V5 USDT perpetuals, 5x.

WHY THIS EXISTS: the confluence lane is long-only on SPOT, so a bearish roster produces a wall of
un-actionable SELLs and an idle lane. A perp short is the only way to act on them.

WHY IT IS ITS OWN MODULE: perps are a NEW RISK CLASS (leverage, funding, liquidation) and NOTHING
here may perturb the reviewed spot path. `SHORTS_ENABLED` is False, so with the flag off this
module is imported but never called: no venue request, no state file, no ledger line.

SAFETY PROPERTIES (each has a test in tests/test_demo_perp_short.py):
  * DEFAULT OFF — `SHORTS_ENABLED = False`; the CLI `--shorts` flag is the only way to turn it on.
  * LEVERAGE PINNED AND VERIFIED — set, then RE-READ from `/v5/position/list`; anything other than
    a confirmed `REQUIRED_LEVERAGE` REFUSES the symbol and no order is sent, never assumed from an
    ack. 5x is the CEILING at which the -15% stop still fires before liquidation (~19.5%); an
    import-time assertion refuses any leverage that would put liquidation inside the stop.
  * ISOLATED margin, VERIFIED — the same set-then-re-read on `tradeMode == 1`. If isolated cannot
    be confirmed the symbol is REFUSED; cross is never used silently. (See ACCOUNT-MODE note below.)
  * ONE-WAY mode, VERIFIED — exactly one position row at `positionIdx == 0`. A hedge-mode account
    is refused rather than guessed at.
  * NEVER UNPROTECTED — a venue-side full-position stop is attached immediately after the fill and
    then RE-READ; if it cannot be confirmed the position is CLOSED immediately (reduceOnly). Every
    cycle re-sweeps every open short and closes any that is still unprotected.
  * MIRRORED DISASTER STOP — the same `DEMO_DISASTER_STOP_PCT` as the long side, ABOVE entry.
  * COVERS ARE reduceOnly — a cover can shrink a short to zero and can never open a reverse long.
  * SHARED CAP — a short consumes the same `BUY_QUOTE_USDT` slot out of the SAME
    `TOTAL_DEMO_CAPITAL_USDT`; longs and shorts share one budget, they do not each get one.
  * SEPARATE LEDGER — perp records go to `perp_orders.jsonl`, NEVER `orders.jsonl` (see FUNDING).

FUNDING: a perp pays/receives funding every 8h. It lands in the USDT wallet balance attached to NO
order, so a wallet-delta round-trip fold cannot attribute it. `scripts/report_demo_trades.py` folds
`orders.jsonl` only, so writing perp records to their OWN ledger keeps that report provably
untouched by funding rather than merely argued to be. Perp records deliberately do NOT reuse the
`reconcile.USDT_delta` key: a perp fill does not move the wallet by its notional at all (margin is
reserved, P&L and funding settle separately), so a spot-shaped delta would be a lie. What each perp
order moved is recorded from the POSITION rows the venue returns.

ACCOUNT-MODE OPEN QUESTION: on a Bybit UNIFIED (UTA) account, per-symbol `/v5/position/switch-
isolated` may be unavailable — isolated margin is an ACCOUNT-level setting there. This module will
NOT change an account-level setting (that would also affect the spot lane and is an operator
decision). If the venue refuses per-symbol isolation, every symbol is REFUSED and the short side
does nothing. That is the intended fail-closed outcome; see the report accompanying this change.

Demo/fake money, UNVALIDATED, promotion_eligible False, execution_authority NONE.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_eth_lane as lane  # noqa: E402
import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402

# THE master switch. False => this module is inert: `run_short_cycle` is never called by the
# activity lane, so no perp endpoint is ever contacted. Turn it on for one run with
# `python scripts/demo_eth_lane.py --activity --shorts`.
SHORTS_ENABLED = False

# MARGIN per short — one slot of the shared $300 cap, exactly like a long. This is what
# `short_exposure` contributes to the cap, so 12 slots still means 12 positions.
SHORT_MARGIN_USDT = lane.BUY_QUOTE_USDT
REQUIRED_LEVERAGE = Decimal("5")
# NOTIONAL actually sized = margin x leverage. At 1x these were the same number and the distinction
# never mattered; at 5x it is the difference between "no change at all" and "5x the exposure", so
# the two are named separately and never used interchangeably. $25 margin controls $125 of coin.
SHORT_NOTIONAL_USDT = SHORT_MARGIN_USDT * REQUIRED_LEVERAGE
# Back-compat alias: existing call sites that meant the cap contribution.
SHORT_QUOTE_USDT = SHORT_MARGIN_USDT

# HARD INVARIANT — the reason 5x and not more. Isolated liquidation happens at roughly
# (1/leverage - maintenance) of adverse move; the disaster stop must fire comfortably BEFORE that,
# or every stop in this module is decorative and the exchange decides the exit instead. At 25x
# liquidation is ~3.5% away against a 15% stop, so the stop could never fire. This check makes that
# unshippable rather than a comment someone can ignore: raising REQUIRED_LEVERAGE past ~5 fails
# import, not production.
MAINTENANCE_MARGIN_RATE = Decimal("0.005")  # ~0.5% on majors; conservative
STOP_LIQUIDATION_BUFFER = Decimal("1.25")  # the stop must sit at least 25% nearer than liquidation
_LIQUIDATION_DISTANCE = (Decimal("1") / REQUIRED_LEVERAGE) - MAINTENANCE_MARGIN_RATE
if _LIQUIDATION_DISTANCE <= lane.DEMO_DISASTER_STOP_PCT * STOP_LIQUIDATION_BUFFER:
    raise AssertionError(
        f"leverage {REQUIRED_LEVERAGE}x liquidates at ~{_LIQUIDATION_DISTANCE:.1%}, which is not "
        f"safely beyond the {lane.DEMO_DISASTER_STOP_PCT:.0%} disaster stop — the stop could never "
        "fire. Lower REQUIRED_LEVERAGE."
    )
ISOLATED_TRADE_MODE = 1  # Bybit tradeMode: 0 = cross, 1 = isolated
ONE_WAY_POSITION_IDX = 0

# Perp records NEVER share `orders.jsonl` — see FUNDING in the module docstring.
PERP_LEDGER_NAME = "perp_orders.jsonl"
SHORT_STRATEGY = "ACTIVITY-CONFLUENCE-SHORT"

# Bounded confirmation polling: the position, not the order, is the confirmation of a perp fill
# (`rt.order_status` is spot-only).
_CONFIRM_POLLS = 12
_CONFIRM_SLEEP_SECONDS = 0.5

# --- FEE-BURN HALT ------------------------------------------------------------------------------
# The failure this exists for: the venue ACCEPTS the short but rejects or never confirms the
# protective stop (e.g. a wrong `tpslMode`/`trading-stop` payload shape), so `open_short` force-
# closes on the spot. That outcome is SAFE — no unprotected perp exposure ever survives — but it
# costs TWO taker fees per attempt, and unattended it repeats every single cycle, forever, for
# every symbol. After this many such open-then-immediately-close round trips in ONE run, NEW short
# ENTRIES stop for the rest of the run.
#
# WHAT THIS DISABLES: new short entries, and nothing else. Covers, the local mirrored disaster
# stop, the every-cycle unprotected sweep and the kill switch all keep working for any short that is
# already open — risk REDUCTION is never gated by this, exactly as it is never gated by
# `verify_symbol` or by the shared cap.
#
# Per-PROCESS, like `demo_activity_lane._NO_DATA_WARNED`: a fresh run starts clean, so an operator
# who fixes the payload shape just re-runs the lane.
STOP_UNCONFIRMED_HALT_THRESHOLD = 2
_STOP_UNCONFIRMED_CLOSES = 0
_SHORT_ENTRIES_DISABLED = False


def reset_fee_burn_halt() -> None:
    """Clear the per-run fee-burn counter. Called once at the start of a lane run."""
    global _STOP_UNCONFIRMED_CLOSES, _SHORT_ENTRIES_DISABLED
    _STOP_UNCONFIRMED_CLOSES = 0
    _SHORT_ENTRIES_DISABLED = False


def short_entries_disabled() -> bool:
    """True once the fee-burn halt has tripped. Gates NEW ENTRIES ONLY, never risk reduction."""
    return _SHORT_ENTRIES_DISABLED


def _count_stop_unconfirmed_close(symbol: str) -> None:
    """Record one open-then-force-close round trip and trip the halt at the threshold."""
    global _STOP_UNCONFIRMED_CLOSES, _SHORT_ENTRIES_DISABLED
    _STOP_UNCONFIRMED_CLOSES += 1
    if _SHORT_ENTRIES_DISABLED or _STOP_UNCONFIRMED_CLOSES < STOP_UNCONFIRMED_HALT_THRESHOLD:
        return
    _SHORT_ENTRIES_DISABLED = True
    print(
        f"SHORT SIDE DISABLED for the rest of this run ({symbol} was the "
        f"{_STOP_UNCONFIRMED_CLOSES}th): a short opened and then had to be force-closed because "
        "the venue would not confirm its protective stop. The likely cause is that this account "
        "rejects the /v5/position/trading-stop payload shape this lane sends, so every attempt "
        "opens and closes a position for nothing and burns TWO taker fees. NEW SHORT ENTRIES ARE "
        "NOW SKIPPED. Covers, the disaster stop, the unprotected sweep and the kill switch all "
        "keep running for any short still open.",
        file=sys.stderr,
    )


def perp_ledger_path() -> Path:
    """Resolved at call time so tests that repoint `lane.LANE_DIR` are honoured."""
    return lane.LANE_DIR / PERP_LEDGER_NAME


def append_perp_ledger(record: dict[str, Any]) -> dict[str, Any]:
    """Append-only perp ledger, fsynced like the spot one. Returns the record for convenience."""
    lane.LANE_DIR.mkdir(parents=True, exist_ok=True)
    with perp_ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def _record(symbol: str, event: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "category": rt.PERP_CATEGORY,
        "symbol": symbol,
        "strategy": SHORT_STRATEGY,
        "event": event,
        # A perp fill does NOT move the wallet by its notional, and funding moves the wallet with no
        # order at all. Stated on every record so no downstream reader can mistake these for
        # spot-shaped, wallet-delta-reconciled trades.
        "wallet_delta_attributable": False,
        "funding_note": "perp funding settles to the wallet every 8h attached to no order",
        **lane.LANE_LABEL,
        **fields,
    }


def short_state_key(symbol: str) -> str:
    return f"{symbol}_activity_short"


def read_short_state(symbol: str) -> dict[str, Any]:
    return lane.read_state(short_state_key(symbol))


def write_short_state(symbol: str, state: dict[str, Any]) -> None:
    lane.write_state(state, short_state_key(symbol))


def _settle_short_close(symbol: str, state: dict[str, Any], closed: dict[str, Any]) -> None:
    """Zero the local short state ONLY when the venue confirmed the close.

    Zeroing unconditionally was a real defect: a rejected or unconfirmed reduce-only close would
    leave the state file claiming flat while the venue still held the short. Two things read that
    file and would then be wrong in the dangerous direction — `activity_open_exposure` would
    under-count the shared $300 cap, and the long/short mutual-exclusion gate (`short_open`) would
    stop withholding the spot BUY, so a real long could open against a still-live short on the same
    coin. Staying "short" until the venue says otherwise is the conservative direction, and it is
    self-correcting: `run_short_cycle` re-reads the live position row every cycle before any
    signal, so a close that actually did land is reconciled on the next pass.
    """
    if closed.get("ok"):
        write_short_state(symbol, {**state, "short_size": "0", "entry_price": None})


def short_open(symbol: str) -> bool:
    """True when this lane believes it holds a short on `symbol` (used by the shared cap)."""
    return Decimal(str(read_short_state(symbol).get("short_size", "0") or "0")) > 0


def short_exposure(symbols: list[str] | tuple[str, ...]) -> Decimal:
    """Shared-cap contribution: one MARGIN slot per open short (notional is 5x this)."""
    return SHORT_MARGIN_USDT * sum(1 for symbol in symbols if short_open(symbol))


# --- Mirrored disaster stop (pure) --------------------------------------------------------------
# Derived from the SAME DEMO_DISASTER_STOP_PCT the long side uses, so the two sides cannot drift.


def short_stop_price(entry: Decimal) -> Decimal:
    """Price at which an open SHORT is DEMO_DISASTER_STOP_PCT underwater — ABOVE entry."""
    return entry * (Decimal("1") + lane.DEMO_DISASTER_STOP_PCT)


def short_stop_triggered(entry: Decimal, mark: Decimal) -> bool:
    """True once the mark has risen to/through the +15%-from-entry level."""
    return entry > 0 and mark > 0 and mark >= short_stop_price(entry)


def quantize_short_stop_price(price: Decimal, tick: Decimal) -> Decimal:
    """Round a SHORT stop DOWN to a valid tick — never loosen the risk boundary.

    Mirror of the long side's `quantize_price_up`: a long's stop sits below entry so rounding UP is
    the tighter direction; a short's stop sits above entry so rounding DOWN is.
    """
    if not price.is_finite() or price <= 0:
        raise lane.LocalRejection("short stop price must be finite and positive")
    if not tick.is_finite() or tick <= 0:
        raise lane.LocalRejection("instrument price tick must be finite and positive")
    stop = lane.quantize_down(price, tick)
    if not stop.is_finite() or stop <= 0:
        raise lane.LocalRejection("short stop price is below one price tick")
    return stop


def short_size_for(
    notional: Decimal, mark: Decimal, qty_step: Decimal, min_qty: Decimal
) -> Decimal:
    """Base-coin size for `notional` USDT of short at `mark`, quantized DOWN to the venue step.

    Linear qty is BASE COIN — there is no spot-style `marketUnit=quoteCoin` on perps, so the
    conversion happens here and is refused (never rounded up) when it lands below the venue minimum.
    """
    if not mark.is_finite() or mark <= 0:
        raise lane.LocalRejection("perp mark price must be finite and positive")
    size = lane.quantize_down(notional / mark, qty_step)
    if size <= 0 or size < min_qty:
        raise lane.LocalRejection(
            f"short size {size} is below the venue minimum {min_qty} at mark {mark}"
        )
    return size


# --- Venue verification -------------------------------------------------------------------------


def _position_row(
    symbol: str, api_key: str, secret: str, get_transport: pf.Transport
) -> dict[str, Any] | None:
    """The single one-way position row for `symbol`, or None when the venue does not report one.

    A hedge-mode account returns rows at positionIdx 1/2 and therefore NO one-way row — which makes
    this return None and every caller fail closed, exactly as intended.
    """
    rows = rt.perp_positions(get_transport, api_key, secret, pf.DEMO_BASE, symbol)
    matches = [row for row in rows if str(row.get("positionIdx", "")) == str(ONE_WAY_POSITION_IDX)]
    if len(matches) != 1:
        return None
    return matches[0]


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - any unparsable venue value is "not confirmed"
        return Decimal("-1")


def verify_symbol(
    symbol: str,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
) -> tuple[bool, dict[str, Any]]:
    """SET then RE-READ 1x + isolated + one-way. Gates ENTRIES ONLY — never risk reduction.

    Nothing here trusts an acknowledgement. `switch-isolated` / `set-leverage` are asked for (a
    "not modified" retCode is a successful no-op), and the answer that counts is the position row
    read back afterwards. Any failure, any missing row, any value that is not exactly 1x /
    tradeMode 1 / positionIdx 0 returns (False, reason) and NO order is sent for this symbol.
    """
    leverage = str(REQUIRED_LEVERAGE)
    for name, call in (
        ("switch_isolated", rt.perp_switch_isolated),
        ("set_leverage", rt.perp_set_leverage),
    ):
        try:
            response = call(
                post_transport,
                api_key,
                secret,
                rt._now(),
                pf.DEMO_BASE,
                symbol=symbol,
                leverage=leverage,
            )
        except Exception as error:  # noqa: BLE001 - unreachable venue = unverified = refuse
            return False, {"refused": name, "error": str(error)}
        code = response.get("retCode")
        if code not in (0, rt.LEVERAGE_NOT_MODIFIED, rt.MARGIN_MODE_NOT_MODIFIED):
            return False, {"refused": name, "retCode": code, "retMsg": response.get("retMsg")}

    try:
        row = _position_row(symbol, api_key, secret, get_transport)
    except Exception as error:  # noqa: BLE001 - cannot read = cannot confirm = refuse
        return False, {"refused": "position_read", "error": str(error)}
    if row is None:
        return False, {"refused": "no_one_way_position_row"}
    observed = {
        "leverage": str(row.get("leverage")),
        "tradeMode": str(row.get("tradeMode")),
        "positionIdx": str(row.get("positionIdx")),
    }
    if _decimal(row.get("leverage")) != REQUIRED_LEVERAGE:
        return False, {"refused": "leverage_not_required_multiple", **observed}
    if str(row.get("tradeMode")) != str(ISOLATED_TRADE_MODE):
        return False, {"refused": "margin_not_isolated", **observed}
    return True, {"verified": True, **observed}


# --- Order path ---------------------------------------------------------------------------------


def _confirm_position(
    symbol: str,
    api_key: str,
    secret: str,
    get_transport: pf.Transport,
    sleep: Any,
    *,
    want_open: bool,
) -> dict[str, Any] | None:
    """Poll the POSITION until it matches `want_open`. The position is the fill confirmation."""
    row: dict[str, Any] | None = None
    for _ in range(_CONFIRM_POLLS):
        sleep(_CONFIRM_SLEEP_SECONDS)
        try:
            row = _position_row(symbol, api_key, secret, get_transport)
        except Exception as error:  # noqa: BLE001 - keep polling; unresolved is handled by caller
            print(f"{symbol}: perp position read failed: {error}", file=sys.stderr)
            continue
        size = _decimal((row or {}).get("size", "0"))
        if want_open and size > 0:
            return row
        if not want_open and row is not None and size <= 0:
            return row
    return row


def force_close_short(
    symbol: str,
    size: Decimal,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
    reason: str,
) -> dict[str, Any]:
    """reduceOnly market BUY that closes a short. RISK REDUCTION — never gated by verification.

    `reduceOnly` means the venue can only shrink the position with this order: even a stale `size`
    can never flip the short into a long.
    """
    response = rt.perp_market_order(
        post_transport,
        api_key,
        secret,
        rt._now(),
        pf.DEMO_BASE,
        symbol=symbol,
        side="Buy",
        base_qty=str(size),
        reduce_only=True,
    )
    ok = response.get("retCode") == 0
    row = (
        _confirm_position(symbol, api_key, secret, get_transport, sleep, want_open=False)
        if ok
        else None
    )
    closed = row is not None and _decimal(row.get("size", "0")) <= 0
    return append_perp_ledger(
        _record(
            symbol,
            "COVER",
            reason=reason,
            side="Buy",
            reduce_only=True,
            qty=str(size),
            ok=ok and closed,
            retCode=response.get("retCode"),
            retMsg=response.get("retMsg"),
            order_id=str(response.get("result", {}).get("orderId", "")),
            position_after=row,
        )
    )


def protect_short(
    symbol: str,
    entry: Decimal,
    tick: Decimal,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
) -> tuple[bool, Decimal]:
    """Attach the venue-side +15% stop and CONFIRM it by re-reading the position.

    Returns (confirmed, wanted_stop). The caller closes the position when this is not confirmed —
    a short is never allowed to remain open without venue-side protection.
    """
    wanted = quantize_short_stop_price(short_stop_price(entry), tick)
    try:
        response = rt.perp_trading_stop(
            post_transport,
            api_key,
            secret,
            rt._now(),
            pf.DEMO_BASE,
            symbol=symbol,
            stop_loss=str(wanted),
        )
    except Exception as error:  # noqa: BLE001 - unprotected until proven otherwise
        print(f"{symbol}: perp stop placement failed: {error}", file=sys.stderr)
        return False, wanted
    if response.get("retCode") != 0:
        print(f"{symbol}: perp stop rejected: {response.get('retMsg')}", file=sys.stderr)
        return False, wanted
    try:
        row = _position_row(symbol, api_key, secret, get_transport)
    except Exception as error:  # noqa: BLE001 - unconfirmed == unprotected
        print(f"{symbol}: perp stop confirmation read failed: {error}", file=sys.stderr)
        return False, wanted
    resting = _decimal((row or {}).get("stopLoss", "0"))
    # Confirmed only when a real stop rests at or below the level we asked for (lower = tighter for
    # a short). An empty/zero/looser stopLoss is NOT protection.
    return (resting > 0 and resting <= wanted), wanted


def open_short(
    symbol: str,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
    signal_ref: str,
    notional: Decimal = SHORT_NOTIONAL_USDT,
) -> dict[str, Any]:
    """Verify -> size -> short -> confirm -> protect (or close). Returns the ledger record.

    The ONLY risk-INCREASING path in this module, and therefore the only one behind
    `verify_symbol`. If any step after the fill fails to confirm protection, the position is closed
    immediately rather than left open.
    """
    if lane.kill_switch_active():
        return append_perp_ledger(_record(symbol, "SHORT_ENTRY", ok=False, stage="kill_switch"))
    verified, detail = verify_symbol(
        symbol,
        api_key,
        secret,
        get_transport=get_transport,
        post_transport=post_transport,
    )
    if not verified:
        return append_perp_ledger(
            _record(symbol, "SHORT_ENTRY", ok=False, stage="refused_unverified", detail=detail)
        )
    qty_step, min_qty, tick = rt.perp_instrument(get_transport, pf.DEMO_BASE, symbol)
    mark = rt.perp_last_price(get_transport, pf.DEMO_BASE, symbol)
    size = short_size_for(notional, mark, qty_step, min_qty)

    response = rt.perp_market_order(
        post_transport,
        api_key,
        secret,
        rt._now(),
        pf.DEMO_BASE,
        symbol=symbol,
        side="Sell",
        base_qty=str(size),
        reduce_only=False,
    )
    if response.get("retCode") != 0:
        return append_perp_ledger(
            _record(
                symbol,
                "SHORT_ENTRY",
                ok=False,
                stage="place",
                qty=str(size),
                retCode=response.get("retCode"),
                retMsg=response.get("retMsg"),
                signal_ref=signal_ref,
            )
        )
    row = _confirm_position(symbol, api_key, secret, get_transport, sleep, want_open=True)
    filled = _decimal((row or {}).get("size", "0"))
    if filled <= 0:
        # Acknowledged but no position observed. NEVER assumed flat: the next cycle's protective
        # sweep re-reads the venue and will protect-or-close anything that did materialise.
        return append_perp_ledger(
            _record(
                symbol,
                "SHORT_ENTRY",
                ok=False,
                stage="unconfirmed",
                qty=str(size),
                signal_ref=signal_ref,
                order_id=str(response.get("result", {}).get("orderId", "")),
            )
        )
    entry = _decimal((row or {}).get("avgPrice", "0"))
    protected, wanted = (False, Decimal("0"))
    if entry > 0:
        protected, wanted = protect_short(
            symbol,
            entry,
            tick,
            api_key,
            secret,
            get_transport=get_transport,
            post_transport=post_transport,
        )
    if not protected:
        # A short that cannot be protected is closed on the spot — no unprotected perp exposure.
        force_close_short(
            symbol,
            filled,
            api_key,
            secret,
            get_transport=get_transport,
            post_transport=post_transport,
            sleep=sleep,
            reason="STOP_UNCONFIRMED_IMMEDIATE_CLOSE",
        )
        # Two taker fees just went out for nothing. Count it; at the threshold this trips the
        # fee-burn halt and no further ENTRY is attempted this run.
        _count_stop_unconfirmed_close(symbol)
        return append_perp_ledger(
            _record(
                symbol,
                "SHORT_ENTRY",
                ok=False,
                stage="closed_unprotected",
                qty=str(filled),
                entry_price=str(entry),
                signal_ref=signal_ref,
            )
        )
    return append_perp_ledger(
        _record(
            symbol,
            "SHORT_ENTRY",
            ok=True,
            stage="done",
            side="Sell",
            reduce_only=False,
            qty=str(filled),
            entry_price=str(entry),
            stop_price=str(wanted),
            leverage=detail.get("leverage"),
            trade_mode=detail.get("tradeMode"),
            signal_ref=signal_ref,
            order_id=str(response.get("result", {}).get("orderId", "")),
        )
    )


# --- Per-coin cycle -----------------------------------------------------------------------------


def run_short_cycle(
    symbol: str,
    decision: str | None,
    api_key: str,
    secret: str,
    *,
    get_transport: pf.Transport,
    post_transport: rt.PostTransport,
    sleep: Any,
    long_open: bool,
    entry_notional_budget: Decimal | None,
    signal_ref: str,
) -> dict[str, Any]:
    """One coin's short-side cycle. Order: PROTECT -> STOP -> COVER -> ENTER.

    Risk reduction always runs first and is never gated by the shared cap or by `verify_symbol`;
    only a NEW short is gated. `decision` is "SHORT" / "COVER" / None from
    `demo_activity_lane.short_decision`.
    """
    state = read_short_state(symbol)
    if not state.get("armed"):
        # Prospective discipline, mirroring the long lane's "first start arms the cursor": the very
        # first sight of a coin never trades.
        write_short_state(symbol, {**state, "armed": True, "short_size": "0"})
        return {"stage": "armed"}

    row = _position_row(symbol, api_key, secret, get_transport)
    size = _decimal((row or {}).get("size", "0"))
    side = str((row or {}).get("side", ""))
    open_short_position = row is not None and size > 0 and side == "Sell"
    entry = _decimal((row or {}).get("avgPrice", "0")) if open_short_position else Decimal("0")
    result: dict[str, Any] = {"size": str(size if open_short_position else 0)}

    if open_short_position:
        # 1. NEVER UNPROTECTED — every cycle, independent of any signal. An open short whose venue
        #    stop cannot be confirmed is closed immediately.
        _, _, tick = rt.perp_instrument(get_transport, pf.DEMO_BASE, symbol)
        resting = _decimal((row or {}).get("stopLoss", "0"))
        wanted = quantize_short_stop_price(short_stop_price(entry), tick)
        if not (resting > 0 and resting <= wanted):
            protected, wanted = protect_short(
                symbol,
                entry,
                tick,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
            )
            if not protected:
                closed = force_close_short(
                    symbol,
                    size,
                    api_key,
                    secret,
                    get_transport=get_transport,
                    post_transport=post_transport,
                    sleep=sleep,
                    reason="UNPROTECTED_SHORT_IMMEDIATE_CLOSE",
                )
                _settle_short_close(symbol, state, closed)
                return {**result, "stage": "closed_unprotected", "action": closed}

        # 2. LOCAL mirrored disaster stop: mark AT/ABOVE +15% from entry closes now, exactly like
        #    the long side's local guard backing up the venue stop.
        mark = rt.perp_last_price(get_transport, pf.DEMO_BASE, symbol)
        if short_stop_triggered(entry, mark):
            closed = force_close_short(
                symbol,
                size,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                reason="DISASTER_STOP_SHORT",
            )
            _settle_short_close(symbol, state, closed)
            return {**result, "stage": "disaster_stop", "mark": str(mark), "action": closed}

        # 3. Signal cover.
        if decision == "COVER":
            closed = force_close_short(
                symbol,
                size,
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                reason="COVER_SHORT",
            )
            _settle_short_close(symbol, state, closed)
            return {**result, "stage": "cover", "action": closed}

        write_short_state(
            symbol,
            {
                **state,
                "short_size": str(size),
                "entry_price": str(entry),
                "stop_price": str(wanted),
            },
        )
        return {**result, "stage": "hold", "entry_price": str(entry), "stop_price": str(wanted)}

    # Flat on the venue: keep local state honest, then consider a NEW short.
    if Decimal(str(state.get("short_size", "0") or "0")) > 0:
        write_short_state(symbol, {**state, "short_size": "0", "entry_price": None})
    if decision != "SHORT":
        return {**result, "stage": "flat"}
    if short_entries_disabled():
        # FEE-BURN HALT. Everything above this line — the unprotected sweep, the disaster stop and
        # the cover — has already run for any open short and is deliberately NOT reachable from
        # here; only the ENTRY below is stopped. `open_short` is reached from nowhere else, so this
        # one guard covers the whole entry path.
        return {**result, "stage": "skipped_entries_disabled"}
    if long_open:
        # A coin is NEVER long and short at the same time. The long side ran first this cycle; if
        # it is still open we simply do not short.
        return {**result, "stage": "skipped_long_open"}
    if entry_notional_budget is not None and SHORT_QUOTE_USDT > entry_notional_budget:
        print(
            f"{symbol}: short skipped — shared demo capital cap reached "
            f"(need {SHORT_QUOTE_USDT} USDT, budget {entry_notional_budget} USDT)",
            file=sys.stderr,
        )
        return {**result, "stage": "skipped_cap"}
    opened = open_short(
        symbol,
        api_key,
        secret,
        get_transport=get_transport,
        post_transport=post_transport,
        sleep=sleep,
        signal_ref=signal_ref,
    )
    if opened.get("ok"):
        write_short_state(
            symbol,
            {
                **state,
                "short_size": str(opened.get("qty")),
                "entry_price": str(opened.get("entry_price")),
                "stop_price": str(opened.get("stop_price")),
            },
        )
        return {**result, "stage": "short_entry", "action": opened}
    return {**result, "stage": str(opened.get("stage")), "action": opened}


if __name__ == "__main__":  # pragma: no cover - the lane runs this, not the module
    # There is deliberately no runnable order path here: shorts run only via
    # `python scripts/demo_eth_lane.py --activity --shorts`.
    print(json.dumps({"shorts_enabled": SHORTS_ENABLED, "ledger": str(perp_ledger_path())}))
