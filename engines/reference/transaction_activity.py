"""Independent Decimal ledger for transaction-activity Spot research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_DAY = timedelta(days=1)
ONE_HOUR = timedelta(hours=1)
INITIAL_CASH = Decimal("1000")


@dataclass(frozen=True)
class ActivityLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool
    event_codes: tuple[int, ...]


def activity_events(
    *,
    spot_opens: tuple[datetime, ...],
    source_days: tuple[datetime, ...],
    counts: tuple[int, ...],
    side: str,
    window: int,
    holding_days: int,
    signal_start: datetime | None = None,
    delay_bars: int = 0,
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    if len(source_days) != len(counts) or side not in {"HIGH", "LOW"}:
        raise ValueError("invalid activity inputs")
    if window <= 1 or holding_days not in {1, 3} or delay_bars not in {0, 1}:
        raise ValueError("invalid trial parameters")
    if any(count <= 0 for count in counts):
        raise ValueError("activity counts must be positive")
    if any(left >= right for left, right in pairwise(source_days)):
        raise ValueError("activity source days must be strictly ordered")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise ValueError("Spot opens must be strictly ordered")

    logs = [Decimal(count).ln() for count in counts]
    candidates: dict[datetime, datetime] = {}
    for index in range(window, len(source_days)):
        days = source_days[index - window : index + 1]
        if any(right - left != ONE_DAY for left, right in pairwise(days)):
            continue
        baseline = logs[index - window : index]
        if len(set(counts[index - window : index])) == 1:
            continue
        mean = sum(baseline, Decimal(0)) / Decimal(window)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(window)
        z_score = (logs[index] - mean) / variance.sqrt()
        eligible = z_score > 1 if side == "HIGH" else z_score < -1
        within_segment = signal_start is None or source_days[index] >= signal_start - timedelta(
            days=2
        )
        if eligible and within_segment:
            candidates[source_days[index] + timedelta(days=2, hours=1 + delay_bars)] = source_days[
                index
            ]

    source_gap_exits = {
        left + timedelta(days=3, hours=1)
        for left, right in pairwise(source_days)
        if right - left != ONE_DAY
    }
    entries = [False] * len(spot_opens)
    exits = [False] * len(spot_opens)
    held = False
    scheduled_exit: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        spot_gap = index > 0 and opened - spot_opens[index - 1] != ONE_HOUR
        source_gap = opened in source_gap_exits
        due = scheduled_exit is not None and opened >= scheduled_exit
        if held and (spot_gap or source_gap or due):
            exits[index] = True
            held = False
            scheduled_exit = None
        if spot_gap or source_gap or held or was_held:
            continue
        if opened in candidates:
            entries[index] = True
            held = True
            scheduled_exit = opened + timedelta(days=holding_days)
    return tuple(entries), tuple(exits)


def simulate_activity_ledger(
    *,
    spot_opens: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    source_days: tuple[datetime, ...],
    counts: tuple[int, ...],
    side: str,
    window: int,
    holding_days: int,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    signal_start: datetime | None = None,
    delay_bars: int = 0,
) -> ActivityLedgerResult:
    if not len(spot_opens) == len(opens) == len(closes) or not spot_opens:
        raise ValueError("Spot columns must be non-empty and equal length")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs must be non-negative")
    entries, exits = activity_events(
        spot_opens=spot_opens,
        source_days=source_days,
        counts=counts,
        side=side,
        window=window,
        holding_days=holding_days,
        signal_start=signal_start,
        delay_bars=delay_bars,
    )
    slip = slippage_bps_per_side / Decimal(10_000)
    cash, quantity, previous_equity = INITIAL_CASH, Decimal(0), INITIAL_CASH
    returns: list[Decimal] = []
    buys = sells = 0
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        if exits[index] and quantity:
            cash = quantity * open_price * (1 - slip) * (1 - fee_rate_per_side)
            quantity = Decimal(0)
            sells += 1
        elif entries[index] and not quantity:
            quantity = cash / (open_price * (1 + slip) * (1 + fee_rate_per_side))
            cash = Decimal(0)
            buys += 1
        equity = cash + quantity * close_price
        returns.append(equity / previous_equity - 1)
        previous_equity = equity
    return ActivityLedgerResult(
        tuple(returns),
        previous_equity,
        buys,
        sells,
        sells,
        bool(quantity),
        tuple(int(entry) + int(exit) * 2 for entry, exit in zip(entries, exits, strict=True)),
    )
