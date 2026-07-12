#!/usr/bin/env python3
"""Human-readable backtest outcomes: $ in -> $ out, trades, wins, losses.

Operator request (2026-07-12): show a strategy the way a person thinks about it —
"I put in $1000, over the last year on the 1h chart it became $X across N trades,
W winners and L losers" — across every available timeframe and several lookback
windows (5y/4y/3y/2y/1y/6m/1m).

Data reality: the frozen DS-CRYPTO-SPOT-BAKEOFF-V1 dataset holds BTCUSDT/ETHUSDT at
5m/15m/1h only, 2021-01-01..2026-06-30. There is NO 1-minute data here; adding it
would mean downloading and re-freezing new data (a separate, gated decision). This
tool reports what actually exists and says so.

Still research only: nothing is validated, no venue, no orders. A good number here
is necessary but NOT sufficient — see the validation gates for why (overfitting).

ponytail: reuses the public-strategy builders from run_external_strategy_search and
the seed dataset map; the default Donchian uses an O(n) monotonic-deque rolling
extreme so the 5m x 5y windows stay fast. Add strategies by extending STRATEGIES.
"""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_external_strategy_search as ext  # noqa: E402

OUT = ROOT / "artifacts" / "research_lab" / "human_backtest_view"
DATA = ROOT / "data" / "normalized"
INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("5m", "15m", "1h")  # everything the frozen dataset actually has
MISSING_TIMEFRAMES = ("1m", "4h", "1d")  # not in the frozen dataset; needs new data
WINDOWS = (
    ("5y", 1825),
    ("4y", 1460),
    ("3y", 1095),
    ("2y", 730),
    ("1y", 365),
    ("6m", 182),
    ("1m", 30),
)
START_CAPITAL = Decimal("1000")
FEE = Decimal("0.001")  # 0.1% per side, matching the bake-off assumption

Candles = dict[str, list[Decimal]]


def _prior_extreme(values: list[Decimal], window: int, want_max: bool) -> list[Decimal | None]:
    """Rolling max/min over the `window` bars BEFORE each index i (excludes i). O(n)."""
    out: list[Decimal | None] = [None] * len(values)
    dq: deque[int] = deque()
    for i in range(len(values)):
        while dq and dq[0] < i - window:
            dq.popleft()
        if i >= window:
            out[i] = values[dq[0]]
        v = values[i]
        if want_max:
            while dq and values[dq[-1]] <= v:
                dq.pop()
        else:
            while dq and values[dq[-1]] >= v:
                dq.pop()
        dq.append(i)
    return out


def fast_donchian(window: int) -> ext.SignalBuilder:
    """Donchian breakout with an O(n) rolling channel (the QC2 candidate)."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        upper = _prior_extreme(c["high"], window, want_max=True)
        lower = _prior_extreme(c["low"], window, want_max=False)
        entries = [u is not None and p > u for p, u in zip(close, upper, strict=True)]
        exits = [lo is not None and p < lo for p, lo in zip(close, lower, strict=True)]
        return entries, exits

    return build


def _canonical(strategy: ext.Strategy) -> ext.SignalBuilder:
    """First variant of a public strategy = its textbook default configuration."""
    return next(iter(strategy.variants.values()))


# QC2 Donchian-40 is the candidate we've been discussing; plus every public strategy.
STRATEGIES: dict[str, ext.SignalBuilder] = {"QC2-DONCHIAN-40": fast_donchian(40)}
STRATEGIES.update({s.strategy_id: _canonical(s) for s in ext.STRATEGIES})
DEFAULT_STRATEGY = "QC2-DONCHIAN-40"


@dataclass(frozen=True)
class Loaded:
    candles: Candles
    open_times: list[datetime]


def load(instrument: str, timeframe: str) -> Loaded:
    table = pq.read_table(
        DATA / f"{instrument}_{timeframe}.parquet",
        columns=["timestamp_open_utc", "open", "high", "low", "close"],
    )
    candles = {
        name: [Decimal(str(v.as_py())) for v in table.column(name)]
        for name in ("open", "high", "low", "close")
    }
    times = [t.as_py() for t in table.column("timestamp_open_utc")]
    return Loaded(candles, times)


def slice_window(data: Loaded, days: int) -> Candles:
    """Last `days` of bars, by timestamp (accurate regardless of timeframe)."""
    if not data.open_times:
        return {k: [] for k in ("open", "high", "low", "close")}
    cutoff = data.open_times[-1] - timedelta(days=days)
    start = bisect_left(data.open_times, cutoff)
    return {name: values[start:] for name, values in data.candles.items()}


@dataclass(frozen=True)
class Outcome:
    window: str
    bars: int
    start_usd: str
    end_usd: str
    return_pct: str
    trades: int
    wins: int
    losses: int
    win_rate_pct: str
    buy_hold_pct: str
    beat_buy_hold: bool
    open_at_end: bool


def _buy_hold_pct(candles: Candles) -> Decimal:
    opens, closes = candles["open"], candles["close"]
    if len(opens) < 2:
        return Decimal("0")
    qty = START_CAPITAL * (Decimal("1") - FEE) / opens[0]
    end = qty * closes[-1] * (Decimal("1") - FEE)
    return (end / START_CAPITAL - Decimal("1")) * 100


def per_trade_backtest(candles: Candles, entries: list[bool], exits: list[bool]) -> Outcome:
    """All-in long-only, next-bar-open execution, per round-trip win/loss."""
    opens, closes = candles["open"], candles["close"]
    cash, qty, entry_cost = START_CAPITAL, Decimal("0"), Decimal("0")
    wins = losses = 0
    open_at_end = False
    for i in range(len(opens) - 1):
        price = opens[i + 1]
        if qty == 0 and entries[i]:
            entry_cost, qty, cash = cash, cash * (Decimal("1") - FEE) / price, Decimal("0")
        elif qty > 0 and exits[i]:
            cash, qty = qty * price * (Decimal("1") - FEE), Decimal("0")
            wins, losses = (wins + 1, losses) if cash > entry_cost else (wins, losses + 1)
    if qty > 0:  # still holding at the end: mark to the last close, count as a trade
        cash = qty * closes[-1] * (Decimal("1") - FEE)
        wins, losses = (wins + 1, losses) if cash > entry_cost else (wins, losses + 1)
        open_at_end = True
    trades = wins + losses
    ret = (cash / START_CAPITAL - Decimal("1")) * 100
    bh = _buy_hold_pct(candles)
    return Outcome(
        window="",
        bars=len(opens),
        start_usd=f"{START_CAPITAL:.0f}",
        end_usd=f"{cash:.2f}",
        return_pct=f"{ret:.1f}",
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate_pct=f"{(Decimal(wins) / Decimal(trades) * 100) if trades else Decimal(0):.0f}",
        buy_hold_pct=f"{bh:.1f}",
        beat_buy_hold=ret > bh,
        open_at_end=open_at_end,
    )


def run_strategy(strategy_id: str) -> dict:
    builder = STRATEGIES[strategy_id]
    matrix: list[dict] = []
    for instrument in INSTRUMENTS:
        for timeframe in TIMEFRAMES:
            data = load(instrument, timeframe)
            for label, days in WINDOWS:
                candles = slice_window(data, days)
                if len(candles["open"]) < 2:
                    continue
                entries, exits = builder(candles)
                outcome = per_trade_backtest(candles, entries, exits)
                row = {
                    **asdict(outcome),
                    "window": label,
                    "instrument": instrument,
                    "timeframe": timeframe,
                }
                matrix.append(row)
    return {
        "schema": "tios-human-backtest-view-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "strategy_id": strategy_id,
        "start_capital_usd": str(START_CAPITAL),
        "fee_per_side": str(FEE),
        "available_timeframes": list(TIMEFRAMES),
        "timeframes_not_in_frozen_dataset": list(MISSING_TIMEFRAMES),
        "data_span": "2021-01-01..2026-06-30",
        "caveat": "A good backtest number is necessary but NOT sufficient; see validation "
        "gates (overfitting). Nothing here is validated or tradeable.",
        "results": matrix,
    }


def _print_human(report: dict) -> None:
    print(
        f"\nStrategy: {report['strategy_id']}   (${report['start_capital_usd']} start, "
        f"{report['fee_per_side']} fee/side, long-only, next-open fills)"
    )
    print(
        f"Timeframes available: {', '.join(report['available_timeframes'])}   "
        f"(NOT in frozen data: {', '.join(report['timeframes_not_in_frozen_dataset'])})"
    )
    key = None
    for row in report["results"]:
        combo = f"{row['instrument']} {row['timeframe']}"
        if combo != key:
            key = combo
            print(f"\n{combo}")
            header = f"  {'window':<7}{'end $':>11}{'return':>9}{'trades':>8}"
            print(header + f"{'W/L':>10}{'win%':>6}{'vs B&H':>9}")
        star = "*" if row["beat_buy_hold"] else " "
        wl = f"{row['wins']}/{row['losses']}"
        print(
            f"  {row['window']:<7}{'$' + row['end_usd']:>11}{row['return_pct'] + '%':>9}"
            f"{row['trades']:>8}{wl:>10}{row['win_rate_pct'] + '%':>6}"
            f"{row['buy_hold_pct'] + '%':>8}{star}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Human-readable backtest outcomes.")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=sorted(STRATEGIES))
    parser.add_argument("--all", action="store_true", help="run every named strategy")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ids = sorted(STRATEGIES) if args.all else [args.strategy]
    for strategy_id in ids:
        report = run_strategy(strategy_id)
        artifact = OUT / f"HUMAN_VIEW_{strategy_id}.json"
        artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _print_human(report)
        print(f"\n  artifact: {artifact.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
