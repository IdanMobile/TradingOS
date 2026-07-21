#!/usr/bin/env python3
"""First campaign executed entirely through the D-107/D-108 substrate.

Family: `FAM-VOL-CONTRACTION-BREAKOUT-V1` — enter long when a *preceding low-volatility
regime* resolves upward through its own range, exit on a trailing low. This is distinct
from the retained Donchian baselines (B2) in the way that matters: a plain N-bar-high
breakout fires in any regime, whereas this one is only armed after realized range has
contracted, so it tests a different claim (that contraction precedes directional
resolution) rather than a reparameterisation of one already rejected under D-054.

Selecting this family is itself a search, and D-108 makes that cost something: the
campaign deflates against the hierarchy-wide trial ledger, so admitting this family raises
the bar for it and every family after it.

Everything the substrate enforces is exercised here for real:

  pre-registration -> train-only search -> per-trial ledger -> freeze -> one validation
  read -> hierarchy-wide deflation -> holdout untouched

The expected outcome is a FAIL. That is not a caveat — a family that clears a correctly
deflated bar on the first attempt would be more suspicious than one that does not.

    python scripts/run_first_budgeted_campaign.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.validation.campaign import TrialScore, run_campaign  # noqa: E402
from tios.validation.splits import split_temporal  # noqa: E402

DATASET = ROOT / "data" / "normalized_multi" / "BTCUSDT_1h.parquet"
HOLDOUT_SEALED_UNTIL = datetime(2027, 1, 14, tzinfo=UTC)

# F1/S1 — the project's selection-and-primary cost scenario (D-107 evidence conventions).
FEE_RATE_PER_SIDE = 0.001
SLIPPAGE_RATE_PER_SIDE = 0.0001

Bar = tuple[float, float, float, float]  # open, high, low, close


def load_bars(path: Path = DATASET) -> tuple[Bar, ...]:
    table = pq.read_table(path, columns=["open", "high", "low", "close"])
    columns = [table.column(name).to_pylist() for name in ("open", "high", "low", "close")]
    return tuple(zip(*(map(float, column) for column in columns), strict=True))


def evaluate(window: Sequence[Bar], parameters: dict[str, Any]) -> TrialScore:
    """Per-bar Sharpe of the rule over `window`, after F1/S1 costs, filling at next open.

    Pure: the same window and parameters always produce the same score. Called only with
    training data during the search — the split makes anything else unreachable.

    The descriptive ``score`` is unchanged; ``trade_returns`` are the completed trades the DSR is
    built on, and ``bar_returns`` is that PnL aligned to absolute bar index (0.0 while flat, in
    warm-up, or marking) so trials with different warm-ups still line up for the correlation
    haircut.
    """
    contraction = int(parameters["contraction_window"])
    breakout = int(parameters["breakout_window"])
    exit_window = int(parameters["exit_window"])
    quantile = float(parameters["contraction_quantile"])

    warmup = max(contraction, breakout, exit_window) + 1
    bar_returns = [0.0] * max(len(window) - 1, 0)
    if len(window) < warmup + 10:
        return TrialScore(0.0, (), tuple(bar_returns))

    ranges = [(bar[1] - bar[2]) / bar[3] if bar[3] else 0.0 for bar in window]
    returns: list[float] = []
    trade_returns: list[float] = []
    held = False

    for index in range(warmup, len(window) - 1):
        recent = ranges[index - contraction : index]
        contracted = recent and ranges[index] <= sorted(recent)[int(len(recent) * quantile)]

        highs = [bar[1] for bar in window[index - breakout : index]]
        lows = [bar[2] for bar in window[index - exit_window : index]]
        close = window[index][3]

        entry = (not held) and contracted and close > max(highs)
        exit_ = held and close < min(lows)

        # Signals are evaluated on a closed bar and filled at the NEXT open, with adverse
        # slippage on both sides. Filling at the signal bar's own close would leak.
        fill = window[index + 1][0]
        if entry:
            held = True
            entry_price = fill * (1 + SLIPPAGE_RATE_PER_SIDE) * (1 + FEE_RATE_PER_SIDE)
            continue
        if exit_ and held:
            held = False
            exit_price = fill * (1 - SLIPPAGE_RATE_PER_SIDE) * (1 - FEE_RATE_PER_SIDE)
            trade_returns.append(exit_price / entry_price - 1)
            returns.append(trade_returns[-1])
            bar_returns[index] = trade_returns[-1]
            continue
        if held:
            returns.append(0.0)  # mark-to-market bars carry no realised return

    if len(returns) < 2:
        return TrialScore(0.0, tuple(trade_returns), tuple(bar_returns))
    deviation = pstdev(returns)
    score = mean(returns) / deviation if deviation > 0 else 0.0
    return TrialScore(score, tuple(trade_returns), tuple(bar_returns))


def parameter_grid() -> list[dict[str, Any]]:
    """The pre-registered search space, enumerated once and never widened mid-run."""
    return [
        {
            "contraction_window": contraction,
            "breakout_window": breakout,
            "exit_window": exit_window,
            "contraction_quantile": quantile,
        }
        for contraction in (24, 48, 96)
        for breakout in (12, 24, 48)
        for exit_window in (12, 24)
        for quantile in (0.2, 0.3)
    ]


def main() -> int:
    if not DATASET.is_file():
        print(f"dataset absent: {DATASET}", file=sys.stderr)
        return 1

    bars = load_bars()
    grid = parameter_grid()
    print(f"dataset: {DATASET.name}  bars={len(bars)}  grid={len(grid)} parameter sets")

    split = split_temporal(
        bars,
        train_fraction=0.6,
        validation_fraction=0.2,
        gap_bars=96,  # >= the longest lookback, so no window straddles a boundary
        sealed_until=HOLDOUT_SEALED_UNTIL,
    )
    print(f"split: {split.sizes()}  holdout sealed until {HOLDOUT_SEALED_UNTIL.date()}")

    result = run_campaign(
        ROOT,
        family="FAM-VOL-CONTRACTION-BREAKOUT-V1",
        search_space={
            "contraction_window": [24, 48, 96],
            "breakout_window": [12, 24, 48],
            "exit_window": [12, 24],
            "contraction_quantile": [0.2, 0.3],
        },
        primary_endpoint="per_bar_sharpe_after_f1s1_costs",
        cost_model={
            "scenario": "F1/S1",
            "fee_rate_per_side": FEE_RATE_PER_SIDE,
            "slippage_rate_per_side": SLIPPAGE_RATE_PER_SIDE,
            "order_assumption": "MARKET_TAKER_AT_NEXT_OPEN_WITH_ADVERSE_SLIPPAGE",
        },
        chronology=f"BTCUSDT 1h, {len(bars)} bars, chronological 60/20/20 with 96-bar gaps",
        thresholds={"dsr_min": 0.95, "min_validation_trades": 10},
        stop_rules="no_rescue_on_fail; no parameter widening after registration",
        split=split,
        parameter_grid=grid,
        evaluate=evaluate,
        fold_count=5,
    )

    print()
    print(f"registration:       {result.registration_ref}")
    print(f"trials (family):    {result.ledger_trials}")
    print(
        f"trials (hierarchy): {result.hierarchy_trials} across {result.admitted_families} families"
    )
    print(f"selected:           {result.selected.parameters if result.selected else None}")
    print(f"train score:        {result.selected.train_score:.6f}" if result.selected else "")
    print(f"validation score:   {result.validation_score:.6f}")
    print(f"validation trades:  {result.validation_trades} (min {result.min_validation_trades})")
    if result.dsr:
        print(f"noise threshold:    {result.dsr['expected_maximum_noise_sharpe']:.6f}")
        print(f"DSR:                {result.dsr['dsr']:.6f}")
        print(f"effective trials:   {result.effective_trials}")
    print(f"blockers:           {list(result.blockers) or 'none'}")
    print(f"holdout sealed:     {result.holdout_sealed}")
    print(f"promotable:         {result.promotable}")

    if result.insufficient_activity:
        verdict = "INSUFFICIENT_ACTIVITY — too few completed trades to claim a DSR"
    elif result.dsr and result.dsr["dsr"] >= 0.95 and result.validation_score > 0:
        verdict = "PASS-ELIGIBLE (still requires G1-G11, specialist review, prospective evidence)"
    else:
        verdict = "FAIL — does not clear the deflated bar"
    print()
    print(f"VERDICT: {verdict}")
    print(
        json.dumps({"artifact": f"artifacts/validation/campaigns/{result.registration_ref}.json"})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
