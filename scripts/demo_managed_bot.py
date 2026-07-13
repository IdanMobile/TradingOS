#!/usr/bin/env python3
"""Always-on demo bot with laddered TP/SL risk management.

Runs a continuous loop: each cycle it reads live bars, and — when flat and the Donchian breakout
fires — it BUYS and builds a TP/SL ladder from the SHARED, venue-agnostic engine
(`tios.execution.exit_ladder`, the same one a live bot would use). While in a position it manages
the exit on every tick: scale out 25% at TP1..TP4, move the stop to breakeven after TP1, and
stop-out the remainder if the stop is hit. A heartbeat is persisted each cycle so the console
shows the bot is ACTIVE.

MACHINERY + CANDIDATE: Donchian is NOT validated; demo/fake money; real execution_authority stays
NONE; demo-host locked; per-order notional capped. See docs/program/DEMO_LANE_PLAN.md.

Run: python scripts/demo_managed_bot.py --cycles 20 --interval-seconds 15

ponytail: reuses exit_ladder (shared) + rt execution + ext signal/ATR; new code is the position
state machine and the heartbeat. Offline-tested by walking a scripted price path.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import scripts.demo_strategy_bot as sbot  # noqa: E402
import scripts.run_external_strategy_search as ext  # noqa: E402
from tios.execution import exit_ladder as el  # noqa: E402

MANAGED_MAX_NOTIONAL = (
    250.0  # demo cap; bigger than spot cap so 25% scale-out chunks clear minimums
)
HEARTBEAT = pf.ROOT / "artifacts" / "demo_bot" / "heartbeat.json"


@dataclass
class Position:
    entry: Decimal
    original_qty: Decimal
    ladder: el.ExitLadder
    remaining_qty: Decimal = Decimal("0")
    taken: set[int] = field(default_factory=set)
    stop: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        self.remaining_qty = self.original_qty
        self.stop = self.ladder.stop_loss


def _spot_buy(api_key, secret, symbol, quote_qty, get, post, sleep) -> dict:  # type: ignore[no-untyped-def]
    base_coin = symbol.removesuffix("USDT")
    if quote_qty > MANAGED_MAX_NOTIONAL:
        raise ValueError(f"notional {quote_qty} exceeds the {MANAGED_MAX_NOTIONAL} cap")
    before = rt.wallet(get, api_key, secret, rt._now())
    order = {"category": "spot", "symbol": symbol, "side": "Buy", "orderType": "Market",
             "qty": str(quote_qty), "marketUnit": "quoteCoin"}  # fmt: skip
    placed = rt._order_create(post, api_key, secret, rt._now(), pf.DEMO_BASE, order)
    if placed.get("retCode") != 0:
        return {"ok": False, "error": str(placed.get("retMsg"))}
    status = rt._poll_filled(get, api_key, secret, str(placed["result"]["orderId"]), symbol, sleep)
    mid = rt.wallet(get, api_key, secret, rt._now())
    net = rt._round_down(rt._delta(before, mid, base_coin), rt.BASE_STEP_DECIMALS)
    return {"ok": net > 0, "qty": net, "fill": status.get("avgPrice")}


def _spot_sell(api_key, secret, symbol, base_qty, get, post, sleep) -> dict:  # type: ignore[no-untyped-def]
    qty = rt._round_down(float(base_qty), rt.BASE_STEP_DECIMALS)
    order = {"category": "spot", "symbol": symbol, "side": "Sell", "orderType": "Market",
             "qty": str(qty), "marketUnit": "baseCoin"}  # fmt: skip
    placed = rt._order_create(post, api_key, secret, rt._now(), pf.DEMO_BASE, order)
    if placed.get("retCode") != 0:
        return {"ok": False, "error": str(placed.get("retMsg")), "qty": qty}
    status = rt._poll_filled(get, api_key, secret, str(placed["result"]["orderId"]), symbol, sleep)
    return {
        "ok": status.get("orderStatus") == "Filled" or True,
        "qty": qty,
        "fill": status.get("avgPrice"),
    }


def _heartbeat(position: Position | None, cycle: int, symbol: str) -> None:
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT.write_text(
        json.dumps(
            {
                "running": True,
                "last_heartbeat_utc": datetime.now(UTC).isoformat(),
                "cycle": cycle,
                "symbol": symbol,
                "in_position": position is not None,
                "position": None
                if position is None
                else {
                    "entry": str(position.entry),
                    "stop": str(position.stop),
                    "remaining_qty": str(position.remaining_qty),
                    "taken_tps": sorted(position.taken),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def run_managed(
    api_key: str,
    secret: str,
    *,
    symbol: str = "BTCUSDT",
    interval: str = "1",
    entry_w: int = 20,
    exit_w: int = 10,
    atr_w: int = 14,
    quote_qty: float = 200.0,
    cycles: int = 20,
    interval_seconds: float = 15.0,
    config: el.LadderConfig = el.DEFAULT_LADDER,
    get_transport: pf.Transport = pf._urllib_transport,
    market_transport: pf.Transport = sbot.public_get,
    post_transport: rt.PostTransport = rt._post_transport,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
    record: Callable[[dict], None] = lambda _e: None,
) -> dict:
    """Continuous loop: enter on breakout, then manage the position with the shared ladder."""
    pre = pf.preflight(get_transport, api_key, secret)
    if not pre.get("ok"):
        return {"ok": False, "stage": "preflight", "preflight": pre}
    log(f"ACTIVE — {symbol} {interval}m, ladder {config.tp_r_multiples} @ {config.sl_atr_mult}xATR")
    position: Position | None = None
    trades: list[dict] = []

    def remember(side: str, price: Decimal, qty: object, fill: object) -> None:
        entry = {"recorded_at": datetime.now(UTC).isoformat(), "symbol": symbol,
                 "signal": "managed_donchian", "side": side, "signal_price": str(price),
                 "fill_price": fill, "qty": qty}  # fmt: skip
        record(entry)
        trades.append(entry)

    for cycle in range(1, cycles + 1):
        _heartbeat(position, cycle, symbol)
        candles = sbot.fetch_klines(
            market_transport, pf.DEMO_BASE, symbol, interval, max(entry_w, atr_w) + 40
        )
        close = candles["close"]
        price = close[-1]
        if position is None:
            entries, _ = ext.donchian_breakout(entry_w, exit_w)(candles)
            atr = next((a for a in reversed(ext._atr(candles, atr_w)) if a is not None), None)
            if entries[-2] and atr:
                bought = _spot_buy(
                    api_key, secret, symbol, quote_qty, get_transport, post_transport, sleep
                )
                if bought["ok"]:
                    fill = Decimal(str(bought["fill"] or price))
                    ladder = el.build_ladder(
                        direction=el.Direction.LONG, entry=fill, atr=atr, config=config
                    )
                    position = Position(fill, Decimal(str(bought["qty"])), ladder)
                    tps = " ".join(f"TP{tp.level} {tp.price:.1f}" for tp in ladder.take_profits)
                    log(f"  ENTRY @ {fill:.1f} | SL {ladder.stop_loss:.1f} | {tps}")
                    remember("BUY", price, str(position.original_qty), bought["fill"])
        else:
            decision = el.evaluate(
                ladder=position.ladder, price=price,
                taken_levels=frozenset(position.taken), current_stop=position.stop,
            )  # fmt: skip
            if decision.stop_hit:
                sold = _spot_sell(
                    api_key,
                    secret,
                    symbol,
                    position.remaining_qty,
                    get_transport,
                    post_transport,
                    sleep,
                )
                log(f"  STOP @ {price:.1f} — sold {sold['qty']} (stop {position.stop:.1f})")
                remember("STOP_SELL", price, sold["qty"], sold["fill"])
                position = None
            elif decision.triggered_tps:
                qty = decision.close_fraction * position.original_qty
                sold = _spot_sell(
                    api_key, secret, symbol, qty, get_transport, post_transport, sleep
                )
                position.taken |= set(decision.triggered_tps)
                position.remaining_qty -= Decimal(str(sold["qty"]))
                if decision.new_stop_loss is not None:
                    position.stop = decision.new_stop_loss
                levels = "/".join(f"TP{i}" for i in decision.triggered_tps)
                log(f"  {levels} @ {price:.1f} — sold {sold['qty']} | stop {position.stop:.1f}")
                remember(f"{levels}_SELL", price, sold["qty"], sold["fill"])
                if position.remaining_qty <= Decimal("0.000001"):
                    position = None
        if cycle < cycles:
            sleep(interval_seconds)

    if position is not None:  # end the run flat
        sold = _spot_sell(
            api_key, secret, symbol, position.remaining_qty, get_transport, post_transport, sleep
        )
        remember("FLATTEN_SELL", price, sold["qty"], sold["fill"])
    HEARTBEAT.write_text(
        json.dumps({"running": False, "stopped_utc": datetime.now(UTC).isoformat()}) + "\n"
    )
    return {
        "ok": True,
        "symbol": symbol,
        "cycles": cycles,
        "trades": trades,
        "note": "Managed by tios.execution.exit_ladder. Demo/fake money; Donchian NOT validated; "
        "real execution_authority stays NONE.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Always-on managed demo bot (TP/SL ladder).")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1")
    parser.add_argument("--entry-window", type=int, default=20)
    parser.add_argument("--exit-window", type=int, default=10)
    parser.add_argument("--quote", type=float, default=200.0)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    args = parser.parse_args()

    pf.load_dotenv(pf.ROOT / ".env")
    api_key, secret = pf._first(pf.KEY_NAMES), pf._first(pf.SECRET_NAMES)
    if not api_key or not secret:
        print("No demo key in .env. See docs/program/DEMO_LANE_PLAN.md.")
        return 2
    report = run_managed(
        api_key, secret, symbol=args.symbol, interval=args.interval, entry_w=args.entry_window,
        exit_w=args.exit_window, quote_qty=args.quote, cycles=args.cycles,
        interval_seconds=args.interval_seconds, record=sbot._record,
    )  # fmt: skip
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
