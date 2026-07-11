#!/usr/bin/env python3
"""Retain validation-probe evidence for the top D-040 seed contexts.

This is intentionally below a promotion-grade validation package: it gives the lab
temporal split, cost-stress, buy-and-hold, and parameter-neighborhood evidence for
the positive proxy rows from SEEDCYCLE-9b1652, while keeping every candidate
UNVALIDATED/NOT_ELIGIBLE.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_seed_research_cycle_v0 as seed  # noqa: E402

OUT = ROOT / "artifacts" / "validation" / "seed_candidates"
ARTIFACT = OUT / "SEED_VALIDATION_PROBE_2026_07_11.json"
INITIAL_CASH = Decimal("1000")


@dataclass(frozen=True)
class Context:
    candidate_id: str
    dataset: str
    trial_key: str
    runner_name: str


CONTEXTS = (
    Context("STRAT-QC2-donchian-breakout", "ETHUSDT_1h", "window=40", "qc2"),
    Context("STRAT-QC2-donchian-breakout", "BTCUSDT_1h", "window=80", "qc2"),
    Context(
        "STRAT-FT1-sample-strategy",
        "ETHUSDT_15m",
        "rsi_window=21,rsi_threshold=20",
        "ft1",
    ),
)

RUNNERS: dict[str, Callable[[dict[str, list[Decimal]]], list[seed.Trial]]] = {
    "qc1": seed.qc1_trials,
    "qc2": seed.qc2_trials,
    "pine1": seed.pine1_trials,
    "ft1": seed.ft1_trials,
    "ft2": seed.ft2_trials,
}


def _return_from_equity(equity: Decimal) -> Decimal:
    return equity / INITIAL_CASH - Decimal("1")


def _trial(candles: dict[str, list[Decimal]], context: Context) -> seed.Trial:
    for row in RUNNERS[context.runner_name](candles):
        if row.trial_key == context.trial_key:
            return row
    raise RuntimeError(f"trial not found: {context}")


def _slice_candles(
    candles: dict[str, list[Decimal]], start: int, stop: int
) -> dict[str, list[Decimal]]:
    return {name: values[start:stop] for name, values in candles.items()}


def _buy_hold_return(candles: dict[str, list[Decimal]], fee: Decimal = seed.FEES) -> Decimal:
    opens = candles["open"]
    if len(opens) < 2:
        return Decimal("-1")
    quantity = (INITIAL_CASH * (Decimal("1") - fee)) / opens[0]
    final_equity = quantity * opens[-1] * (Decimal("1") - fee)
    return _return_from_equity(final_equity)


def _cost_stress(
    candles: dict[str, list[Decimal]], context: Context
) -> dict[str, dict[str, str | int]]:
    original_fee = seed.FEES
    rows: dict[str, dict[str, str | int]] = {}
    try:
        for fee in (Decimal("0"), Decimal("0.001"), Decimal("0.002"), Decimal("0.003")):
            seed.FEES = fee
            trial = _trial(candles, context)
            rows[str(fee)] = {
                "total_return": trial.total_return,
                "final_equity": trial.final_equity,
                "trades": trial.trades,
            }
    finally:
        seed.FEES = original_fee
    return rows


def _temporal_splits(
    candles: dict[str, list[Decimal]], context: Context
) -> dict[str, dict[str, str | int]]:
    n = len(candles["open"])
    spans = {
        "train_first_third": (0, n // 3),
        "validation_middle_third": (n // 3, (2 * n) // 3),
        "holdout_final_third": ((2 * n) // 3, n),
    }
    rows: dict[str, dict[str, str | int]] = {}
    for name, (start, stop) in spans.items():
        trial = _trial(_slice_candles(candles, start, stop), context)
        rows[name] = {
            "total_return": trial.total_return,
            "final_equity": trial.final_equity,
            "trades": trial.trades,
            "bars": stop - start,
        }
    return rows


def _neighborhood(
    candles: dict[str, list[Decimal]], context: Context
) -> list[dict[str, str | int]]:
    rows = sorted(
        RUNNERS[context.runner_name](candles),
        key=lambda row: Decimal(row.total_return),
        reverse=True,
    )
    return [
        {
            "trial_key": row.trial_key,
            "total_return": row.total_return,
            "final_equity": row.final_equity,
            "trades": row.trades,
        }
        for row in rows[:8]
    ]


def evaluate_context(context: Context) -> dict[str, object]:
    candles = seed.load_candles(seed.DATASETS[context.dataset])
    full = _trial(candles, context)
    temporal = _temporal_splits(candles, context)
    cost = _cost_stress(candles, context)
    holdout_return = Decimal(str(temporal["holdout_final_third"]["total_return"]))
    benchmark_return = _buy_hold_return(candles)
    blocker_reasons = [
        "probe artifact only; not a promotion-grade validation package",
        "no cross-engine reproduction for this seed context",
        "no production G10/PBO/DSR over this seed context's searched population",
        "no paper/demo divergence evidence",
    ]
    if holdout_return <= Decimal("0"):
        blocker_reasons.append("final-third holdout return is not positive")
    if _return_from_equity(Decimal(full.final_equity)) <= benchmark_return:
        blocker_reasons.append("full-period proxy does not beat buy-and-hold")
    return {
        "context": asdict(context),
        "status": "UNVALIDATED",
        "approval_status": "NOT_ELIGIBLE",
        "execution_authority": "NONE",
        "full_period": {
            "total_return": full.total_return,
            "final_equity": full.final_equity,
            "trades": full.trades,
        },
        "buy_hold_benchmark": {"total_return": str(benchmark_return)},
        "temporal_splits": temporal,
        "cost_stress": cost,
        "parameter_neighborhood_top": _neighborhood(candles, context),
        "blockers": blocker_reasons,
    }


def build_report() -> dict[str, object]:
    return {
        "schema": "tios-seed-validation-probe-v1",
        "source_cycle": (
            "artifacts/research_lab/seed_cycle_v0/"
            "SEEDCYCLE-9b1652a62996fda4b753c6695f43569ab860acd8decb48c9c5994566f4a6488f"
        ),
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "contexts": [evaluate_context(context) for context in CONTEXTS],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_report()
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(ARTIFACT.relative_to(ROOT)), "contexts": len(CONTEXTS)}))


if __name__ == "__main__":
    main()
