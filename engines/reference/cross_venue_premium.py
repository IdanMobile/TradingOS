"""Independent Decimal ledger for D-075 cross-venue premium research."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

INITIAL_CASH = Decimal("1000")
BAR = timedelta(hours=1)
PULSE = timedelta(hours=6)


@dataclass(frozen=True)
class PremiumLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool


def premium_events(
    *,
    spot_opens: tuple[datetime, ...],
    source_opens: tuple[datetime, ...],
    source_closes: tuple[datetime, ...],
    premiums: tuple[Decimal, ...],
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
    delay_bars: int = 0,
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    if not len(source_opens) == len(source_closes) == len(premiums):
        raise ValueError("source inputs must have equal length")
    if interpretation not in {"CONTINUATION_POSITIVE", "REVERSAL_NEGATIVE"}:
        raise ValueError("invalid interpretation")
    if baseline_hours not in {168, 720, 2160} or threshold not in {
        Decimal("1.0"),
        Decimal("2.0"),
    }:
        raise ValueError("invalid trial parameters")
    if delay_bars not in {0, 1} or any(left >= right for left, right in pairwise(spot_opens)):
        raise ValueError("invalid delay or Spot ordering")
    valid = [
        value.is_finite() and closed >= opened
        for opened, closed, value in zip(source_opens, source_closes, premiums, strict=True)
    ]
    prefix = [Decimal(0)]
    prefix_squared = [Decimal(0)]
    run_length: list[int] = []
    for index, value in enumerate(premiums):
        safe = value if valid[index] else Decimal(0)
        prefix.append(prefix[-1] + safe)
        prefix_squared.append(prefix_squared[-1] + safe * safe)
        consecutive = index > 0 and source_opens[index] - source_opens[index - 1] == BAR
        run_length.append(
            (run_length[-1] + 1 if valid[index - 1] and consecutive else 1) if valid[index] else 0
        )

    candidates: set[datetime] = set()
    for index in range(baseline_hours, len(source_opens)):
        start = index - baseline_hours
        if run_length[index] < baseline_hours + 1:
            continue
        count = Decimal(baseline_hours)
        total = prefix[index] - prefix[start]
        squared_total = prefix_squared[index] - prefix_squared[start]
        mean = total / count
        variance = squared_total / count - mean * mean
        if variance <= 0:
            continue
        z_score = (premiums[index] - mean) / variance.sqrt()
        eligible = (
            z_score > threshold
            if interpretation == "CONTINUATION_POSITIVE"
            else z_score < -threshold
        )
        if not eligible or source_closes[index] < spot_opens[0]:
            continue
        mapped = bisect_right(spot_opens, source_closes[index]) + delay_bars
        if mapped < len(spot_opens):
            candidates.add(spot_opens[mapped])

    interruptions: set[datetime] = set()
    for index, opened in enumerate(source_opens):
        discontinuity = index > 0 and opened - source_opens[index - 1] != BAR
        if valid[index] and not discontinuity:
            continue
        mapped = bisect_right(spot_opens, max(opened, source_closes[index]))
        if mapped < len(spot_opens):
            interruptions.add(spot_opens[mapped])
    entries = [False] * len(spot_opens)
    exits = [False] * len(spot_opens)
    held = False
    scheduled: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        gap = (index > 0 and opened - spot_opens[index - 1] != BAR) or opened in interruptions
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = True
            held = False
            scheduled = None
        if gap or held or was_held:
            continue
        if opened in candidates:
            entries[index] = True
            held = True
            scheduled = opened + PULSE
    return tuple(entries), tuple(exits)


def simulate_premium_ledger(
    *,
    spot_opens: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    source_opens: tuple[datetime, ...],
    source_closes: tuple[datetime, ...],
    premiums: tuple[Decimal, ...],
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    delay_bars: int = 0,
    precomputed_events: tuple[tuple[bool, ...], tuple[bool, ...]] | None = None,
) -> PremiumLedgerResult:
    if not len(spot_opens) == len(opens) == len(closes) or not spot_opens:
        raise ValueError("Spot columns must be non-empty and equal length")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs must be non-negative")
    entries, exits = precomputed_events or premium_events(
        spot_opens=spot_opens,
        source_opens=source_opens,
        source_closes=source_closes,
        premiums=premiums,
        interpretation=interpretation,
        baseline_hours=baseline_hours,
        threshold=threshold,
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
    return PremiumLedgerResult(tuple(returns), previous_equity, buys, sells, sells, bool(quantity))
