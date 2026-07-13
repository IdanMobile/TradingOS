"""Independent Decimal ledger for funding-pressure Spot research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_HOUR = timedelta(hours=1)
INITIAL_CASH = Decimal("1000")


@dataclass(frozen=True)
class FundingLedgerResult:
    returns: tuple[Decimal, ...]
    ending_equity: Decimal
    buy_count: int
    sell_count: int
    completed_trades: int
    ending_held: bool


def funding_events(
    *,
    spot_opens: tuple[datetime, ...],
    calc_times: tuple[datetime, ...],
    rates: tuple[Decimal, ...],
    polarity: str,
    lookback: int,
    threshold: Decimal,
    signal_start: datetime | None = None,
    delay_bars: int = 0,
) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    """Build position-aware fill flags from exact observation timestamps."""
    if len(calc_times) != len(rates):
        raise ValueError("funding timestamps and rates must have equal lengths")
    if polarity not in {"CONTINUATION", "CONTRARIAN"}:
        raise ValueError("unsupported funding polarity")
    if lookback <= 0 or threshold < 0 or delay_bars not in {0, 1}:
        raise ValueError("invalid lookback, threshold, or delay")
    if any(left >= right for left, right in pairwise(calc_times)):
        raise ValueError("funding timestamps must be strictly ordered")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise ValueError("Spot opens must be strictly ordered")

    open_index = {value: index for index, value in enumerate(spot_opens)}
    desired: dict[int, bool] = {}
    for index in range(lookback - 1, len(calc_times)):
        observed = calc_times[index]
        if signal_start is not None and observed < signal_start:
            continue
        average = sum(rates[index + 1 - lookback : index + 1], Decimal(0)) / Decimal(lookback)
        eligible = average > threshold if polarity == "CONTINUATION" else average < -threshold
        expected = observed.replace(minute=0, second=0, microsecond=0) + ONE_HOUR
        fill_index = open_index.get(expected)
        if fill_index is None or fill_index + delay_bars >= len(spot_opens):
            continue
        fill_index += delay_bars
        desired[fill_index] = eligible

    entries = [False] * len(spot_opens)
    exits = [False] * len(spot_opens)
    held = False
    for index in range(len(spot_opens)):
        is_gap = index > 0 and spot_opens[index] - spot_opens[index - 1] != ONE_HOUR
        if is_gap:
            if held:
                exits[index] = True
                held = False
            continue
        eligible = desired.get(index)
        if eligible is True and not held:
            entries[index] = True
            held = True
        elif eligible is False and held:
            exits[index] = True
            held = False
    return tuple(entries), tuple(exits)


def simulate_funding_ledger(
    *,
    spot_opens: tuple[datetime, ...],
    opens: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    calc_times: tuple[datetime, ...],
    rates: tuple[Decimal, ...],
    polarity: str,
    lookback: int,
    threshold: Decimal,
    fee_rate_per_side: Decimal,
    slippage_bps_per_side: Decimal,
    signal_start: datetime | None = None,
    delay_bars: int = 0,
) -> FundingLedgerResult:
    """All-in unlevered Spot long/cash accounting with adverse side costs."""
    if not len(spot_opens) == len(opens) == len(closes) or not spot_opens:
        raise ValueError("Spot columns must be non-empty and equal length")
    if fee_rate_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs must be non-negative")
    if any(price <= 0 for price in opens + closes):
        raise ValueError("Spot prices must be positive")
    entries, exits = funding_events(
        spot_opens=spot_opens,
        calc_times=calc_times,
        rates=rates,
        polarity=polarity,
        lookback=lookback,
        threshold=threshold,
        signal_start=signal_start,
        delay_bars=delay_bars,
    )
    slip = slippage_bps_per_side / Decimal(10_000)
    cash, quantity = INITIAL_CASH, Decimal(0)
    previous_equity = INITIAL_CASH
    returns: list[Decimal] = []
    buys = sells = 0
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        if exits[index] and quantity:
            cash = quantity * open_price * (Decimal(1) - slip) * (Decimal(1) - fee_rate_per_side)
            quantity = Decimal(0)
            sells += 1
        elif entries[index] and not quantity:
            quantity = cash / (open_price * (Decimal(1) + slip) * (Decimal(1) + fee_rate_per_side))
            cash = Decimal(0)
            buys += 1
        equity = cash + quantity * close_price
        returns.append(equity / previous_equity - Decimal(1))
        previous_equity = equity
    return FundingLedgerResult(
        returns=tuple(returns),
        ending_equity=previous_equity,
        buy_count=buys,
        sell_count=sells,
        completed_trades=sells,
        ending_held=bool(quantity),
    )
