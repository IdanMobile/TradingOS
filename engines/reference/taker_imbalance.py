"""Independent Decimal ledger for BTC Spot taker-imbalance research."""

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
class TakerLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool


def taker_events(
    *,
    spot_opens: tuple[datetime, ...],
    source_opens: tuple[datetime, ...],
    source_closes: tuple[datetime, ...],
    quote_volume: tuple[Decimal, ...],
    taker_buy_quote: tuple[Decimal, ...],
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
    delay_bars: int = 0,
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    if not len(source_opens) == len(source_closes) == len(quote_volume) == len(taker_buy_quote):
        raise ValueError("source inputs must have equal length")
    if interpretation not in {"CONTINUATION_HIGH", "REVERSAL_LOW"}:
        raise ValueError("invalid interpretation")
    if baseline_hours not in {24, 168, 720} or threshold not in {Decimal("1.0"), Decimal("2.0")}:
        raise ValueError("invalid trial parameters")
    if delay_bars not in {0, 1} or any(left >= right for left, right in pairwise(spot_opens)):
        raise ValueError("invalid delay or Spot ordering")
    valid = [
        total > 0 and Decimal(0) <= bought <= total and closed >= opened
        for opened, closed, total, bought in zip(
            source_opens, source_closes, quote_volume, taker_buy_quote, strict=True
        )
    ]
    values = [
        Decimal(2) * bought / total - Decimal(1) if okay else Decimal(0)
        for total, bought, okay in zip(quote_volume, taker_buy_quote, valid, strict=True)
    ]
    candidates: set[datetime] = set()
    for index in range(baseline_hours, len(source_opens)):
        start = index - baseline_hours
        if not all(valid[start : index + 1]) or any(
            right - left != BAR for left, right in pairwise(source_opens[start : index + 1])
        ):
            continue
        baseline = values[start:index]
        mean = sum(baseline, Decimal(0)) / Decimal(baseline_hours)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(
            baseline_hours
        )
        if variance == 0:
            continue
        z_score = (values[index] - mean) / variance.sqrt()
        eligible = (
            z_score > threshold if interpretation == "CONTINUATION_HIGH" else z_score < -threshold
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
        boundary = max(opened, source_closes[index])
        mapped = bisect_right(spot_opens, boundary)
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


def simulate_taker_ledger(
    *,
    spot_opens: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    source_opens: tuple[datetime, ...],
    source_closes: tuple[datetime, ...],
    quote_volume: tuple[Decimal, ...],
    taker_buy_quote: tuple[Decimal, ...],
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    delay_bars: int = 0,
) -> TakerLedgerResult:
    if not len(spot_opens) == len(opens) == len(closes) or not spot_opens:
        raise ValueError("Spot columns must be non-empty and equal length")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs must be non-negative")
    entries, exits = taker_events(
        spot_opens=spot_opens,
        source_opens=source_opens,
        source_closes=source_closes,
        quote_volume=quote_volume,
        taker_buy_quote=taker_buy_quote,
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
    return TakerLedgerResult(tuple(returns), previous_equity, buys, sells, sells, bool(quantity))
