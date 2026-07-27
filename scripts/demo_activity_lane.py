#!/usr/bin/env python3
"""Multi-timeframe, multi-strategy CONFLUENCE activity lane (demo / fake money only).

A HIGH-ACTIVITY scored measurement engine layered ADDITIVELY on the reviewed D-104 demo lane. For
each coin in a ~40-coin universe it:

  1. fetches that coin's bars ONCE per timeframe (a small confluence SET — default 15m/1h/4h), so N
     strategies reuse one fetch per (coin, timeframe);
  2. runs the whole breadth-robust roster on EACH timeframe, each (strategy, timeframe) emitting
     BUY / SELL / None on the latest closed bar;
  3. aggregates every (strategy x timeframe) signal into ONE confidence score in [-1, +1], weighting
     higher timeframes more (a 1h/4h agreement outweighs 15m), and records which strategies/
     timeframes are bullish vs bearish so the reason is inspectable;
  4. holds ONE long per coin: enters when confidence >= ENTRY_THRESHOLD, exits when it falls to
     <= EXIT_THRESHOLD (hysteresis so it doesn't thrash) or the -15% disaster / venue-resting stop
     fires.

This is NOT validated edge. Every order/heartbeat is fake money, execution_authority NONE,
UNVALIDATED, promotion_eligible False, Bybit VENUE_DEMO only. Demo P&L is not validation evidence.

It reuses the demo lane's order/stop machinery verbatim through `demo_eth_lane.run_cycle` (one call
per coin, on the NOT_ACTIVATED path — Stage B stays ETH-only). Safety is composed exactly like the
multi-coin lane: SHARED kill switch (checked once, halts all), SHARED total-capital cap (gates only
NEW entries, never exits/stops), per-coin disaster + venue-resting stops priced off that coin's own
entry, and one coin's failure never aborts the others.

Run: python scripts/demo_eth_lane.py --activity [--interval 5m|15m|1h|4h]
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_eth_lane as lane  # noqa: E402
import scripts.demo_preflight as pf  # noqa: E402
import scripts.demo_roundtrip as rt  # noqa: E402
import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_signal_strategy_search as sig  # noqa: E402
from tios.trading_domain import MarketBar  # noqa: E402

# Tag on every confluence order/ledger/heartbeat record: separates this scored engine from the
# untagged ETH/multi records that share the append-only ledger, and names the engine honestly.
ACTIVITY_STRATEGY = "ACTIVITY-CONFLUENCE"

# Full ~40-coin normalized universe (data/normalized_multi). A coin the demo venue does not list
# just errors on its kline fetch and is skipped (per-coin try/except); it never aborts the cycle.
ACTIVITY_UNIVERSE: tuple[str, ...] = (
    "AAVEUSDT",
    "ADAUSDT",
    "ALGOUSDT",
    "APTUSDT",
    "ARBUSDT",
    "ATOMUSDT",
    "AVAXUSDT",
    "AXSUSDT",
    "BCHUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "EGLDUSDT",
    "EOSUSDT",
    "ETCUSDT",
    "ETHUSDT",
    "FILUSDT",
    "FLOWUSDT",
    "FTMUSDT",
    "GRTUSDT",
    "INJUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "MANAUSDT",
    "MATICUSDT",
    "NEARUSDT",
    "OPUSDT",
    "RUNEUSDT",
    "SANDUSDT",
    "SEIUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "THETAUSDT",
    "TIAUSDT",
    "TRXUSDT",
    "UNIUSDT",
    "XLMUSDT",
    "XRPUSDT",
    "XTZUSDT",
)

# Breadth-robust roster (report_research_findings leads), all OHLCV-only so they run on demo klines.
# Each research builder is REUSED as-is; primary (first-grid) variant params. Edit to change roster.
ROSTER: tuple[tuple[str, ext.SignalBuilder], ...] = (
    ("EXT-KELTNER-BREAKOUT", ext.keltner_breakout(20, 10, Decimal("2"))),
    ("EXT-BB-BREAKOUT", ext.bollinger_breakout(20, Decimal("2"))),
    ("EXT-DONCHIAN-40", ext.donchian_breakout(40, 20)),
    ("EXT-SMA-10-30", ext.sma_cross(10, 30)),
    ("EXT-EMA-12-26", ext.ema_cross(12, 26)),
    ("EXT-EMA-8-21", ext.ema_cross(8, 21)),
    ("SIG-VOLUME-BREAKOUT", sig.volume_breakout(20, Decimal("1.5"))),
)

# Confluence timeframe SET and per-timeframe weight. Higher timeframes count more (a 1h agreement is
# stronger than 5m). 15m and 1h are ALWAYS included; the CLI --interval swaps the fastest member
# (default 5m). The 4h anchor was dropped for the activity/visibility lane: with weight 3 and a
# frequently-bearish higher trend it pinned most coins below ENTRY and starved the lane of trades.
# This is activity tuning (more demo traffic on an UNVALIDATED, fake-money lane), NOT a claim of
# better edge — dropping the higher-timeframe trend filter admits weaker confluence, not stronger.
CONFLUENCE_HIGHER_TIMEFRAMES: tuple[str, ...] = ("15m", "1h")
CONFLUENCE_TIMEFRAMES: tuple[str, ...] = ("5m", "15m", "1h")
TIMEFRAME_WEIGHTS: dict[str, Decimal] = {
    "5m": Decimal("1"),
    "15m": Decimal("1"),
    "1h": Decimal("2"),
    "4h": Decimal("3"),
}
_TF_INTERVAL: dict[str, str] = {"5m": "5", "15m": "15", "1h": "60", "4h": "240"}
_TF_MINUTES: dict[str, int] = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}

# Hysteresis band: go long once bullish confidence clears ENTRY; stay long until it falls to EXIT.
# ENTRY > EXIT, so a score drifting in the middle neither opens nor churns an existing position.
# ENTRY lowered 0.25 -> 0.15 to sustain visible demo activity (~5 trades/30min) past the cold-start
# burst; like the 4h drop above this widens the entry gate for traffic, not for edge.
ENTRY_THRESHOLD = Decimal("0.15")
EXIT_THRESHOLD = Decimal("0.05")

# --loop cadence: one cycle per fastest-timeframe bar (interval minutes -> seconds), floored so a
# fast interval can never hot-spin the roster fetch. ponytail: fixed floor, tune if the venue rate-
# limits kline fetches at this cadence.
LOOP_MIN_SLEEP_SECONDS = 60.0

# Bars a coin must return on EVERY confluence timeframe before it may be scored: the roster's
# longest lookback (donchian_breakout(40, 20)) plus the bar it is evaluated on. Below this the
# roster's indicators have no window — and on an EMPTY series `_true_range` in
# run_external_strategy_search indexes `high[0]` and raises `list index out of range`, which is
# exactly what a delisted/renamed symbol returns from the demo venue. The test is on the DATA the
# venue actually returned, never on a symbol list, so a future delisting behaves identically.
MIN_ROSTER_BARS = 41

# Symbols already warned about this run — the no-data skip is quiet after the first cycle instead
# of re-logging every coin every cycle. Cleared at the start of `run_activity_lane`.
_NO_DATA_WARNED: set[str] = set()

# TRANSPORT failure vs DATA failure. urllib's URLError/HTTPError, socket.gaierror (the observed
# "nodename nor servname provided" DNS loss), ConnectionError and TimeoutError are all OSError
# subclasses, so one tuple covers "the request never produced an answer". Anything else —
# IndexError/ValueError/KeyError/RuntimeError from parsing or scoring — is a DATA problem about ONE
# coin and is never counted towards an outage.
_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (OSError,)

# Connectivity backoff. When EVERY evaluated coin in a cycle failed on transport, the next cycle
# waits `clamp(cadence * 2**consecutive_outages)` instead of spinning at full cadence against a dead
# network. CADENCE AND LOGGING ONLY: no order decision, sizing, threshold, stop or kill-switch check
# is affected, and the wait is sliced so the kill switch is still honoured while backing off.
OUTAGE_BACKOFF_MAX_SECONDS = 900.0
OUTAGE_BACKOFF_POLL_SECONDS = 30.0


def candles_from_bars(bars: tuple[MarketBar, ...]) -> ext.Candles:
    """MarketBar tuple -> the research builders' aligned Decimal-column `Candles` dict."""
    return {
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    }


def signal_on_latest(builder: ext.SignalBuilder, candles: ext.Candles) -> str | None:
    """Bridge a research signal builder to a single BUY / SELL / None on the LATEST closed bar."""
    entries, exits = builder(candles)
    if entries and entries[-1]:
        return "BUY"
    if exits and exits[-1]:
        return "SELL"
    return None


def roster_signals(candles: ext.Candles) -> list[tuple[str, str | None]]:
    """Every roster strategy's latest-bar decision on one timeframe's candles."""
    return [(strategy_id, signal_on_latest(builder, candles)) for strategy_id, builder in ROSTER]


def _q(score: Decimal) -> str:
    return str(score.quantize(Decimal("0.0001")))


def confluence_score(
    signals_by_tf: dict[str, list[tuple[str, str | None]]],
    weights: dict[str, Decimal] = TIMEFRAME_WEIGHTS,
) -> tuple[Decimal, dict[str, Any]]:
    """Aggregate (strategy x timeframe) signals into one confidence in [-1, +1].

    Each BUY contributes +weight, each SELL -weight, None 0; the sum is normalized by the total
    possible weight (every strategy on every timeframe), so a unanimous-bullish book scores +1 and a
    unanimous-bearish one -1. Higher-timeframe agreement dominates via the weights. The returned
    context lists which (strategy, timeframe) pairs are bullish vs bearish for inspectability.
    """
    numerator = Decimal("0")
    denom = Decimal("0")
    bullish: list[dict[str, str]] = []
    bearish: list[dict[str, str]] = []
    for timeframe, sigs in signals_by_tf.items():
        weight = weights[timeframe]
        for strategy_id, decision in sigs:
            denom += weight
            if decision == "BUY":
                numerator += weight
                bullish.append(
                    {"strategy": strategy_id, "timeframe": timeframe, "weight": str(weight)}
                )
            elif decision == "SELL":
                numerator -= weight
                bearish.append(
                    {"strategy": strategy_id, "timeframe": timeframe, "weight": str(weight)}
                )
    score = (numerator / denom) if denom > 0 else Decimal("0")
    context = {
        "confidence": _q(score),
        "bullish": bullish,
        "bearish": bearish,
        "entry_threshold": str(ENTRY_THRESHOLD),
        "exit_threshold": str(EXIT_THRESHOLD),
    }
    return score, context


def confluence_decision(score: Decimal) -> str | None:
    """Hysteresis decision: BUY above ENTRY, SELL at/below EXIT, else None (hold current state)."""
    if score >= ENTRY_THRESHOLD:
        return "BUY"
    if score <= EXIT_THRESHOLD:
        return "SELL"
    return None


def _decision_signals_fn(
    decision: str | None, score: Decimal, ref_bars: tuple[MarketBar, ...]
) -> Any:
    """A `run_cycle` signals_fn that injects the confluence decision as one latest-bar signal.

    The signal's `observed_at` is the reference bar's close time, so run_cycle's cursor advances one
    bar at a time exactly like the ETH lane (no re-fire on the same bar, first cycle arms the
    cursor). The signal_ref carries the confidence score, so the order record is attributable.
    """

    def signals_fn(_bars: tuple[MarketBar, ...]) -> list[Any]:
        if decision is None or not ref_bars:
            return []
        close_time = ref_bars[-1].close_time
        signal_id = f"ACT-CONF:{_q(score)}:{close_time.isoformat()}"
        side = SimpleNamespace(value=decision)
        return [SimpleNamespace(side=side, signal_id=signal_id, observed_at=close_time)]

    return signals_fn


def activity_open_exposure(symbols: list[str]) -> Decimal:
    """Sum of per-coin buy notional currently open across the confluence lane (own state files)."""
    total = Decimal("0")
    for symbol in symbols:
        if Decimal(str(lane.read_state(f"{symbol}_activity").get("lane_base", "0"))) > 0:
            total += lane.BUY_QUOTE_USDT
    return total


def _timeframes_for(interval_label: str) -> tuple[str, ...]:
    """Confluence set for a chosen fastest timeframe: {interval} + always 15m/1h, de-duplicated."""
    return tuple(dict.fromkeys([interval_label, *CONFLUENCE_HIGHER_TIMEFRAMES]))


def run_activity_cycle(
    api_key: str,
    secret: str,
    *,
    symbols: tuple[str, ...] | list[str] = ACTIVITY_UNIVERSE,
    timeframes: tuple[str, ...] = CONFLUENCE_TIMEFRAMES,
    total_cap: Decimal = lane.TOTAL_DEMO_CAPITAL_USDT,
    get_transport: pf.Transport = pf._urllib_transport,
    post_transport: rt.PostTransport = lane._live_post_transport,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """One confluence cycle across the universe: ONE scored long per coin.

    Safety composition (identical to run_multi_cycle):
      * SHARED kill switch — checked ONCE; if set, ALL coins halt and nothing runs.
      * SHARED total-capital cap — a new entry that would breach `total_cap` is skipped (logged, not
        an error) inside run_cycle; already-open coins still run their risk-reducing exits/stops.
      * one coin's failure never aborts the others (caught, logged, cycle continues).

    Two resilience behaviors, both cadence/logging only:
      * a coin whose venue klines are empty or shorter than MIN_ROSTER_BARS on any timeframe is a
        quiet SKIP (warned once per run), excluded from this cycle's scored universe — it is not an
        error and it never touches another coin;
      * a cycle in which EVERY evaluated coin failed on TRANSPORT is reported as one connectivity
        outage (`connectivity_outage`) and logs one line instead of one per coin. The caller backs
        off on that flag; nothing about scoring, sizing, entries, exits or stops changes.
    """
    coin_list = list(symbols)
    if lane.kill_switch_active():
        return {
            "kill_switch": True,
            "coins": {symbol: {"stage": "kill_switch"} for symbol in coin_list},
            **lane.LANE_LABEL,
        }
    reference_tf = min(timeframes, key=lambda tf: _TF_MINUTES[tf])
    # Seed the shared budget from exposure already open, then decrement as coins enter this cycle.
    remaining = total_cap - activity_open_exposure(coin_list)
    coins: dict[str, Any] = {}
    evaluated = 0  # coins actually attempted this cycle (no-data skips are not evaluated)
    transport_failures: list[str] = []  # deferred per-coin lines; flushed only if NOT an outage
    last_transport_error = ""
    for symbol in coin_list:
        state_key = f"{symbol}_activity"
        was_open = Decimal(str(lane.read_state(state_key).get("lane_base", "0"))) > 0
        try:
            # Per-coin fetch cache: exactly one kline request per (coin, timeframe); the whole
            # roster reuses each timeframe's bars.
            bars_by_tf = {
                tf: lane.fetch_closed_bars(get_transport, symbol=symbol, interval=_TF_INTERVAL[tf])
                for tf in timeframes
            }
            thin = {
                tf: len(bars_by_tf[tf])
                for tf in timeframes
                if len(bars_by_tf[tf]) < MIN_ROSTER_BARS
            }
            if thin:
                # No usable data for this coin (delisted/renamed/too new). Quiet SKIP: excluded
                # from this cycle's scored universe, warned once per run, never an error, and no
                # other coin is affected. Not counted as `evaluated`, so a delisted coin can never
                # look like a connectivity outage.
                if symbol not in _NO_DATA_WARNED:
                    _NO_DATA_WARNED.add(symbol)
                    print(
                        f"{symbol}: no usable bars {thin} (need {MIN_ROSTER_BARS} per timeframe) "
                        "— skipping this coin for the rest of the run",
                        file=sys.stderr,
                    )
                coins[symbol] = {"skipped": "insufficient_bars", "bars": thin}
                continue
            evaluated += 1
            signals_by_tf = {
                tf: roster_signals(candles_from_bars(bars_by_tf[tf])) for tf in timeframes
            }
            score, context = confluence_score(signals_by_tf)
            decision = confluence_decision(score)
            ref_bars = bars_by_tf[reference_tf]
            heartbeat_extra = {
                "confluence": {
                    **context,
                    "timeframes": list(timeframes),
                    "reference_timeframe": reference_tf,
                    "decision": decision or "HOLD",
                }
            }
            heartbeat = lane.run_cycle(
                api_key,
                secret,
                get_transport=get_transport,
                post_transport=post_transport,
                sleep=sleep,
                symbol=symbol,
                interval=_TF_INTERVAL[reference_tf],
                prefetched_bars=ref_bars,
                signals_fn=_decision_signals_fn(decision, score, ref_bars),
                state_key=state_key,
                strategy=ACTIVITY_STRATEGY,
                entry_notional_budget=remaining,
                heartbeat_extra=heartbeat_extra,
            )
            coins[symbol] = {
                "lane_base": heartbeat["lane_base"],
                "confidence": context["confidence"],
                "decision": decision or "HOLD",
                "action": heartbeat.get("action"),
                "entry_price": heartbeat.get("entry_price"),
                "resting_stop": heartbeat.get("resting_stop"),
            }
            now_open = Decimal(str(heartbeat["lane_base"])) > 0
            if now_open and not was_open:
                # A fresh entry consumed one BUY_QUOTE_USDT of the shared cap this cycle.
                remaining -= lane.BUY_QUOTE_USDT
        except Exception as error:  # noqa: BLE001 - one coin must never abort the whole cycle
            evaluated += 1
            message = f"{symbol}: activity cycle failed, continuing other coins: {error}"
            if isinstance(error, _TRANSPORT_ERRORS):
                # Deferred: if the whole cycle turns out to be a connectivity outage these N
                # identical lines collapse into one. Otherwise they are printed verbatim below.
                transport_failures.append(message)
                last_transport_error = str(error)
            else:
                print(message, file=sys.stderr)
            coins[symbol] = {"error": str(error)}
    # Outage = every coin we actually evaluated failed, and every one of those failures was a
    # transport failure. A mixed cycle (any success, or any DATA failure) is NOT an outage.
    outage = evaluated > 0 and len(transport_failures) == evaluated
    if outage:
        print(
            f"connectivity outage: all {evaluated} evaluated coins failed on transport "
            f"({last_transport_error}) — per-coin errors suppressed for this cycle",
            file=sys.stderr,
        )
    else:
        for message in transport_failures:
            print(message, file=sys.stderr)
    return {
        "kill_switch": False,
        "total_cap": str(total_cap),
        "remaining_budget": str(remaining),
        "reference_timeframe": reference_tf,
        "connectivity_outage": outage,
        "coins": coins,
        **lane.LANE_LABEL,
    }


def outage_backoff_seconds(consecutive_outages: int, cadence_seconds: float) -> float:
    """Wait before the next cycle after `consecutive_outages` all-transport-failure cycles.

    Normal cadence while healthy; then a capped doubling (cadence*2, *4, ... up to
    OUTAGE_BACKOFF_MAX_SECONDS) so the lane stops hammering a dead network. Never shorter than the
    normal cadence, so backing off can only ever slow the loop down, never speed it up.
    """
    if consecutive_outages <= 0:
        return cadence_seconds
    return max(
        cadence_seconds, min(cadence_seconds * 2**consecutive_outages, OUTAGE_BACKOFF_MAX_SECONDS)
    )


def _wait_honouring_kill_switch(seconds: float, sleep: Any) -> bool:
    """Sleep `seconds` in slices, returning False the moment the kill switch appears.

    Cadence only: a long backoff must never make the lane deaf to the kill switch.
    """
    remaining = seconds
    while remaining > 0:
        step = min(OUTAGE_BACKOFF_POLL_SECONDS, remaining)
        sleep(step)
        remaining -= step
        if lane.kill_switch_active():
            return False
    return True


def run_activity_lane(
    api_key: str,
    secret: str,
    *,
    interval: str = "15m",
    loop: bool = False,
    sleep: Any = time.sleep,
) -> int:
    """Preflight once, then run confluence cycles across the universe.

    `loop=False` (default) runs exactly one cycle then exits — byte-identical to the original
    one-shot `--activity` behavior. `loop=True` re-runs `run_activity_cycle` every fastest-timeframe
    bar (sleep floored by LOOP_MIN_SLEEP_SECONDS) until the kill switch is set or the process is
    interrupted; the per-cycle logic and the held single-lane lock are unchanged.

    On a cycle reported as a connectivity outage the loop waits `outage_backoff_seconds` instead of
    the normal cadence (kill switch still polled throughout), and logs recovery on the first cycle
    that is not an outage. This changes ONLY when the next cycle starts and what is logged.
    """
    _NO_DATA_WARNED.clear()  # "warn once" is scoped to this run
    pre = pf.preflight(pf._urllib_transport, api_key, secret)
    if not pre.get("ok"):
        print(json.dumps({"ok": False, "stage": "preflight", "preflight": pre}, indent=2))
        return 1
    timeframes = _timeframes_for(interval)
    sleep_seconds = max(LOOP_MIN_SLEEP_SECONDS, _TF_MINUTES[interval] * 60)
    print(
        f"preflight GREEN on {pre['host']} — confluence activity lane "
        f"({len(ACTIVITY_UNIVERSE)} coins, timeframes {list(timeframes)}, "
        f"shared cap {lane.TOTAL_DEMO_CAPITAL_USDT} USDT, "
        f"{'loop ~' + str(int(sleep_seconds)) + 's' if loop else 'once'})"
    )
    consecutive_outages = 0
    try:
        while True:
            report = run_activity_cycle(api_key, secret, timeframes=timeframes)
            print(json.dumps(report, indent=2, sort_keys=True))
            if report.get("connectivity_outage"):
                consecutive_outages += 1
            elif consecutive_outages:
                print("connectivity restored — resuming normal cadence.")
                consecutive_outages = 0
            if not loop:
                return 0
            if lane.kill_switch_active():
                print("KILL_SWITCH present — confluence activity lane stopped.")
                return 0
            wait = outage_backoff_seconds(consecutive_outages, sleep_seconds)
            if consecutive_outages:
                print(
                    f"connectivity outage — backing off {int(wait)}s before the next cycle "
                    f"(normal cadence {int(sleep_seconds)}s).",
                    file=sys.stderr,
                )
            if not _wait_honouring_kill_switch(wait, sleep):
                print("KILL_SWITCH present — confluence activity lane stopped.")
                return 0
    except KeyboardInterrupt:
        print("interrupted — confluence activity lane stopped.")
        return 0
