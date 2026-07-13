"""Independent Decimal ledger for the preregistered UTC-weekday strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_HOUR = timedelta(hours=1)
INITIAL_CASH = Decimal("1000")


@dataclass(frozen=True)
class CalendarLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool


def calendar_events(
    timestamps: tuple[datetime, ...], selected_weekday: int, hour_offset: int = 0
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    """Return fill-bar entry/exit flags using only the immediately prior close."""
    if isinstance(selected_weekday, bool) or not isinstance(selected_weekday, int):
        raise ValueError("selected_weekday must be an integer")
    if not 0 <= selected_weekday <= 6:
        raise ValueError("selected_weekday must be from 0 to 6")
    if hour_offset not in (-1, 0, 1):
        raise ValueError("hour_offset must be -1, 0, or 1")
    if any(timestamp.utcoffset() != timedelta(0) for timestamp in timestamps):
        raise ValueError("timestamps must be UTC")
    if any(left >= right for left, right in pairwise(timestamps)):
        raise ValueError("timestamps must be strictly ordered")

    entries = [False] * len(timestamps)
    exits = [False] * len(timestamps)
    held = False
    for index in range(1, len(timestamps)):
        previous, current = timestamps[index - 1], timestamps[index]
        if current - previous != ONE_HOUR:
            if held:
                exits[index] = True
                held = False
            continue
        anchor = current - timedelta(hours=hour_offset)
        if anchor.hour != 0:
            continue
        if held and anchor.weekday() == (selected_weekday + 1) % 7:
            exits[index] = True
            held = False
        elif not held and anchor.weekday() == selected_weekday:
            entries[index] = True
            held = True
    return tuple(entries), tuple(exits)


def simulate_calendar_ledger(
    *,
    timestamps: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    selected_weekday: int,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    hour_offset: int = 0,
) -> CalendarLedgerResult:
    """All-in long/cash accounting with adverse next-open prices and side fees."""
    if not len(timestamps) == len(opens) == len(closes):
        raise ValueError("timestamps, opens, and closes must have equal lengths")
    if not timestamps:
        raise ValueError("at least one bar is required")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("cost inputs must be non-negative")
    if any(price <= 0 for price in opens + closes):
        raise ValueError("prices must be positive")

    entries, exits = calendar_events(timestamps, selected_weekday, hour_offset)
    slip = slippage_bps_per_side / Decimal(10_000)
    cash, quantity = INITIAL_CASH, Decimal(0)
    previous_equity = INITIAL_CASH
    returns: list[Decimal] = []
    buys = sells = 0
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        if exits[index] and quantity:
            fill = open_price * (Decimal(1) - slip)
            cash = quantity * fill * (Decimal(1) - fee_rate_per_side)
            quantity = Decimal(0)
            sells += 1
        elif entries[index] and not quantity:
            fill = open_price * (Decimal(1) + slip)
            quantity = cash / (fill * (Decimal(1) + fee_rate_per_side))
            cash = Decimal(0)
            buys += 1
        equity = cash + quantity * close_price
        returns.append(equity / previous_equity - Decimal(1))
        previous_equity = equity
    return CalendarLedgerResult(
        returns=tuple(returns),
        ending_equity=previous_equity,
        buy_count=buys,
        sell_count=sells,
        completed_trades=sells,
        ending_held=bool(quantity),
    )
