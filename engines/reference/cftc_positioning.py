"""Independent Decimal ledger for CFTC-positioning Spot research."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

INITIAL_CASH = Decimal("1000")
ONE_HOUR = timedelta(hours=1)
ONE_WEEK = timedelta(days=7)


@dataclass(frozen=True)
class PositioningLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool


def _consecutive(left: datetime, right: datetime) -> bool:
    return timedelta(days=6) <= right - left <= timedelta(days=8)


def positioning_events(
    *,
    spot_opens: tuple[datetime, ...],
    report_dates: tuple[datetime, ...],
    available_at: tuple[datetime, ...],
    values: tuple[Decimal, ...],
    interpretation: str,
    baseline_weeks: int,
    threshold: Decimal,
    delay_bars: int = 0,
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    if not len(report_dates) == len(available_at) == len(values):
        raise ValueError("positioning inputs must have equal length")
    if interpretation not in {"ALIGNED_HIGH", "CONTRARIAN_LOW"}:
        raise ValueError("invalid interpretation")
    if baseline_weeks not in {13, 26, 52} or threshold not in {Decimal("0.5"), Decimal("1.0")}:
        raise ValueError("invalid trial parameters")
    if delay_bars not in {0, 1} or any(not value.is_finite() or abs(value) > 1 for value in values):
        raise ValueError("invalid delay or feature values")
    if any(left >= right for left, right in pairwise(report_dates)) or any(
        left > right for left, right in pairwise(available_at)
    ):
        raise ValueError("positioning dates must be ordered")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise ValueError("Spot opens must be strictly ordered")

    candidates: dict[datetime, datetime] = {}
    for index in range(baseline_weeks, len(report_dates)):
        dates = report_dates[index - baseline_weeks : index + 1]
        if any(not _consecutive(left, right) for left, right in pairwise(dates)):
            continue
        baseline = values[index - baseline_weeks : index]
        mean = sum(baseline, Decimal(0)) / Decimal(baseline_weeks)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(
            baseline_weeks
        )
        if variance == 0:
            continue
        z_score = (values[index] - mean) / variance.sqrt()
        eligible = z_score > threshold if interpretation == "ALIGNED_HIGH" else z_score < -threshold
        if not eligible or available_at[index] < spot_opens[0]:
            continue
        mapped = bisect_right(spot_opens, available_at[index]) + delay_bars
        if mapped < len(spot_opens):
            candidates[spot_opens[mapped]] = report_dates[index]

    source_gap_opens = {
        spot_opens[mapped]
        for index, (left, right) in enumerate(pairwise(report_dates), start=1)
        if not _consecutive(left, right)
        and available_at[index] >= spot_opens[0]
        and (mapped := bisect_right(spot_opens, available_at[index])) < len(spot_opens)
    }
    entries = [False] * len(spot_opens)
    exits = [False] * len(spot_opens)
    held = False
    scheduled_exit: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        gap = (index > 0 and opened - spot_opens[index - 1] != ONE_HOUR) or (
            opened in source_gap_opens
        )
        if held and (gap or (scheduled_exit is not None and opened >= scheduled_exit)):
            exits[index] = True
            held = False
            scheduled_exit = None
        if gap or held or was_held:
            continue
        if opened in candidates:
            entries[index] = True
            held = True
            scheduled_exit = opened + ONE_WEEK
    return tuple(entries), tuple(exits)


def simulate_positioning_ledger(
    *,
    spot_opens: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    report_dates: tuple[datetime, ...],
    available_at: tuple[datetime, ...],
    values: tuple[Decimal, ...],
    interpretation: str,
    baseline_weeks: int,
    threshold: Decimal,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    delay_bars: int = 0,
) -> PositioningLedgerResult:
    if not len(spot_opens) == len(opens) == len(closes) or not spot_opens:
        raise ValueError("Spot columns must be non-empty and equal length")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs must be non-negative")
    entries, exits = positioning_events(
        spot_opens=spot_opens,
        report_dates=report_dates,
        available_at=available_at,
        values=values,
        interpretation=interpretation,
        baseline_weeks=baseline_weeks,
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
    return PositioningLedgerResult(
        tuple(returns), previous_equity, buys, sells, sells, bool(quantity)
    )
