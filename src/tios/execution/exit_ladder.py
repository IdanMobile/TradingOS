"""Laddered TP/SL exit planning — venue-agnostic, shared by every bot (demo and real).

Pure calculation: given an entry, a direction, and volatility (ATR), produce a stop-loss and a
ladder of take-profits (TP1..TPn) sized in units of risk (R), plus per-tick evaluation that says
what fraction to close and where to move the stop (breakeven / trail). It executes nothing — the
venue adapter turns a decision into orders — so it is identical for demo and live; only the
execution layer is gate-controlled.

Level model:
  * 1R = sl_atr_mult * ATR  (the risk distance from entry to the stop).
  * SL  = entry -/+ 1R      (below a long, above a short).
  * TPk = entry +/- Rk * 1R (Rk from tp_r_multiples, e.g. 1R,2R,3R,4R).
  * scale_out[k] = fraction of the position closed at TPk.
  * After breakeven_after_tp is taken, the stop moves to entry (the trade becomes risk-free).

Position size follows the stop, not the target: risk a fixed fraction of equity, and
size = (equity * risk_fraction) / |entry - stop|. Decimal throughout for money math.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True, slots=True)
class LadderConfig:
    sl_atr_mult: Decimal
    tp_r_multiples: tuple[Decimal, ...]
    scale_out: tuple[Decimal, ...]
    breakeven_after_tp: int = 1  # 1-based TP index after which the stop moves to entry; 0 = never

    def __post_init__(self) -> None:
        if self.sl_atr_mult <= 0:
            raise ValueError("sl_atr_mult must be positive")
        if not self.tp_r_multiples or len(self.tp_r_multiples) != len(self.scale_out):
            raise ValueError("tp_r_multiples and scale_out must be non-empty and the same length")
        if any(r <= 0 for r in self.tp_r_multiples):
            raise ValueError("every take-profit R multiple must be positive")
        if list(self.tp_r_multiples) != sorted(self.tp_r_multiples):
            raise ValueError("tp_r_multiples must be ascending (TP1 < TP2 < ...)")
        if any(f <= 0 for f in self.scale_out) or sum(self.scale_out) > Decimal(1):
            raise ValueError("scale_out fractions must be positive and sum to <= 1")
        if not 0 <= self.breakeven_after_tp <= len(self.tp_r_multiples):
            raise ValueError("breakeven_after_tp must be within the take-profit count (0 = never)")


# Default: 2xATR stop, targets 1R/2R/3R/4R, quarter out at each, breakeven at TP1.
DEFAULT_LADDER = LadderConfig(
    sl_atr_mult=Decimal("2"),
    tp_r_multiples=(Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")),
    scale_out=(Decimal("0.25"), Decimal("0.25"), Decimal("0.25"), Decimal("0.25")),
    breakeven_after_tp=1,
)


@dataclass(frozen=True, slots=True)
class TakeProfit:
    level: int  # 1-based
    price: Decimal
    r_multiple: Decimal
    close_fraction: Decimal


@dataclass(frozen=True, slots=True)
class ExitLadder:
    direction: Direction
    entry: Decimal
    stop_loss: Decimal
    risk_per_unit: Decimal  # 1R price distance
    take_profits: tuple[TakeProfit, ...]
    breakeven_after_tp: int


def build_ladder(
    *, direction: Direction, entry: Decimal, atr: Decimal, config: LadderConfig = DEFAULT_LADDER
) -> ExitLadder:
    """Compute the stop-loss and take-profit ladder from entry + volatility."""
    if entry <= 0 or atr <= 0:
        raise ValueError("entry and atr must be positive")
    risk = config.sl_atr_mult * atr  # 1R
    sign = Decimal(1) if direction is Direction.LONG else Decimal(-1)
    take_profits = tuple(
        TakeProfit(index + 1, entry + sign * r * risk, r, fraction)
        for index, (r, fraction) in enumerate(
            zip(config.tp_r_multiples, config.scale_out, strict=True)
        )
    )
    return ExitLadder(
        direction, entry, entry - sign * risk, risk, take_profits, config.breakeven_after_tp
    )


def position_size(
    *, equity: Decimal, risk_fraction: Decimal, entry: Decimal, stop_loss: Decimal
) -> Decimal:
    """Units to trade so that a stop-out loses exactly `risk_fraction` of equity."""
    stop_distance = abs(entry - stop_loss)
    if stop_distance <= 0 or risk_fraction <= 0:
        return Decimal(0)
    return equity * risk_fraction / stop_distance


@dataclass(frozen=True, slots=True)
class ExitDecision:
    stop_hit: bool
    triggered_tps: tuple[int, ...]  # newly-hit TP levels (not previously taken)
    close_fraction: Decimal  # total fraction of the ORIGINAL position to close now
    new_stop_loss: Decimal | None  # move the stop (e.g. to breakeven) or None to leave it


def evaluate(
    *, ladder: ExitLadder, price: Decimal, taken_levels: frozenset[int], current_stop: Decimal
) -> ExitDecision:
    """Per-tick exit logic: which stop/TPs the current price triggers, and any stop move."""
    long = ladder.direction is Direction.LONG
    if (long and price <= current_stop) or (not long and price >= current_stop):
        remaining = Decimal(1) - sum(
            (tp.close_fraction for tp in ladder.take_profits if tp.level in taken_levels),
            Decimal(0),
        )
        return ExitDecision(True, (), max(remaining, Decimal(0)), None)

    triggered = tuple(
        tp.level
        for tp in ladder.take_profits
        if tp.level not in taken_levels
        and ((long and price >= tp.price) or (not long and price <= tp.price))
    )
    close_fraction = sum(
        (tp.close_fraction for tp in ladder.take_profits if tp.level in triggered), Decimal(0)
    )
    highest_taken = max([*taken_levels, *triggered], default=0)
    new_stop: Decimal | None = None
    if (
        ladder.breakeven_after_tp
        and highest_taken >= ladder.breakeven_after_tp
        and current_stop != ladder.entry
    ):
        new_stop = ladder.entry  # trade becomes risk-free once the breakeven TP is taken
    return ExitDecision(False, triggered, close_fraction, new_stop)
