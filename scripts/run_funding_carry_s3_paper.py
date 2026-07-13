#!/usr/bin/env python3
"""S3 paper-lane EXECUTION probe for the basis-aware funding carry.

`run_funding_carry_basis.py` proved the carry survives basis risk, but it charged
only a coarse 4bps toggle fee. The handoff's honest remaining step is EXECUTION-level
validation: does REALISTIC execution erode the carry? Being delta-neutral, every
rebalance trades BOTH legs (buy/sell spot AND short/cover perp); each leg pays a taker
fee plus slippage. This drives the SAME best config through explicit per-leg costs,
routes the resulting cash flows through the real synthetic ledger contract, and reports
the paper-vs-backtest divergence.

Finding shape: signals (held-set path) are identical, so TRADE_COUNT matches; the
execution COST diverges — that gap is exactly the number S3 exists to measure.

Hard boundaries (unchanged, D-036/D-037/AD SS AA):
  * candidate stays NOT_ELIGIBLE / execution_authority=NONE
  * mode = SYNTHETIC_LOCAL_SIMULATOR; venue_connection=NONE; no order route
  * perps/margin are S4-gated; this is offline historical replay, not trading

ponytail: reuses fcb.build_matrix + the identical held-set walk; the only new physics is
per-leg (spot+perp) taker+slippage vs the coarse toggle fee. The ledger is an aggregate
cash reconstruction (one settlement credit + one fee debit) — per-rebalance detail lives
in the returns array; the contract's job here is to prove the S3 cash-flow path accepts
the carry without overdrawing, not to re-derive compounding.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_funding_carry_basis as fcb  # noqa: E402
from tios.trading_domain import (  # noqa: E402
    ApprovalId,
    CreatorType,
    DivergenceMetric,
    DomainRef,
    LedgerDirection,
    LedgerId,
    Money,
    PaperLaneMode,
    Provenance,
    RunId,
    Stage,
    SyntheticLedgerEntryKind,
    apply_synthetic_ledger_change,
    build_synthetic_divergence_report,
    initialize_synthetic_ledger,
)

OUT = ROOT / "artifacts" / "trading_domain" / "s3_carry_paper"
CREATED_AT = datetime(2026, 7, 12, tzinfo=UTC)
BASE_TIME = datetime(2021, 1, 1, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-S3-CARRY-PAPER-2026-07-12"),)
PROVENANCE = Provenance(EVIDENCE)
INITIAL_CAPITAL = Decimal("10000")

# Realistic per-leg execution: a delta-neutral pair trades spot + perp (2 legs); each leg
# pays a taker fee + slippage. The backtest's coarse fee (fcb.FEE = 4bps per toggle) is the
# baseline; this is what it omits.
TAKER_FEE_BPS = 10.0
SLIPPAGE_BPS = 2.0
LEGS_PER_TOGGLE = 2  # spot leg + perp leg
PAPER_TOGGLE_COST = LEGS_PER_TOGGLE * (TAKER_FEE_BPS + SLIPPAGE_BPS) / 10_000.0  # 0.0024
BACKTEST_TOGGLE_COST = fcb.FEE  # 0.0004 — the coarse proxy the backtest actually charged


def carry_walk(
    data: dict[str, dict[str, list[float | None]]],
    threshold: float,
    lookback: int,
    rebalance: int,
    toggle_cost: float,
) -> tuple[list[float], float, int]:
    """Basis-aware carry held-set walk, parametrised by per-toggle execution cost.

    Structurally identical to fcb.backtest: with toggle_cost == fcb.FEE it reproduces the
    backtest exactly (asserted in tests). Also returns the summed fee fraction and the
    number of legs toggled, so paper and baseline can be compared like-for-like.
    """
    pairs = list(data)
    n = len(next(iter(data.values()))["fund"])
    held: set[str] = set()
    strat = [0.0] * n
    fee_frac = 0.0
    toggles = 0
    for t in range(1, n):
        if held:
            got = [r for p in held if (r := fcb._carry_return(data[p], t)) is not None]
            strat[t] = sum(got) / len(got) if got else 0.0
        if t >= lookback and t % rebalance == 0:
            new = set()
            for p in pairs:
                w = [
                    data[p]["fund"][t - k]
                    for k in range(lookback)
                    if data[p]["fund"][t - k] is not None
                ]
                if w and mean(w) > threshold:
                    new.add(p)
            if new != held:
                turn = len(new ^ held)
                cost = toggle_cost * turn / max(len(new | held), 1)
                strat[t] -= cost
                fee_frac += cost
                toggles += turn
            held = new
    return strat, fee_frac, toggles


def select_best(data: dict[str, dict]) -> tuple[float, int, int]:
    """Pick the config the backtest would pick: max per-bar Sharpe under the baseline fee."""
    from itertools import product

    best_cfg, best_sharpe = (fcb.THRESHOLDS[0], fcb.LOOKBACKS[0], fcb.REBALANCES[0]), -1e9
    for threshold, lookback, rebalance in product(fcb.THRESHOLDS, fcb.LOOKBACKS, fcb.REBALANCES):
        strat, _, _ = carry_walk(data, threshold, lookback, rebalance, BACKTEST_TOGGLE_COST)
        sharpe = fcb._metrics(strat)["sharpe_bar"]
        if sharpe > best_sharpe:
            best_cfg, best_sharpe = (threshold, lookback, rebalance), sharpe
    return best_cfg


def _cents(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_ledger(net_equity: Decimal, total_fees: Decimal):
    """Aggregate S3 cash-flow through the real ledger contract: capital, then the net
    carry settlement credit, then the total execution-fee debit. Final balance == net
    equity, proving the path never overdraws. ponytail: aggregate, not per-rebalance."""
    ledger = initialize_synthetic_ledger(
        ledger_id=LedgerId("LEDGER-S3-CARRY-PAPER"),
        entry_id=ApprovalId("APR-S3-CARRY-PAPER-LEDGER-INITIAL"),
        initial_capital=Money(INITIAL_CAPITAL, "USDT"),
        occurred_at=BASE_TIME,
        source_ref=DomainRef("APR-S3-CARRY-PAPER-LANE"),
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    # gross carry P&L = net equity change + the fees that were paid out of it.
    gross_pnl = _cents(net_equity - INITIAL_CAPITAL + total_fees)
    ledger = apply_synthetic_ledger_change(
        ledger,
        entry_id=ApprovalId("APR-S3-CARRY-PAPER-SETTLEMENT"),
        occurred_at=CREATED_AT,
        kind=SyntheticLedgerEntryKind.FILL_SETTLEMENT,
        direction=LedgerDirection.CREDIT,
        amount=Money(gross_pnl, "USDT"),
        source_ref=DomainRef("FILL-S3-CARRY-PAPER-NET-PNL"),
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ledger = apply_synthetic_ledger_change(
        ledger,
        entry_id=ApprovalId("APR-S3-CARRY-PAPER-FEES"),
        occurred_at=CREATED_AT,
        kind=SyntheticLedgerEntryKind.FEE,
        direction=LedgerDirection.DEBIT,
        amount=Money(_cents(total_fees), "USDT"),
        source_ref=DomainRef("APR-S3-CARRY-PAPER-EXECUTION-FEES"),
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    return ledger


def build_report() -> dict:
    periods, data = fcb.build_matrix()
    threshold, lookback, rebalance = select_best(data)

    bt_strat, bt_fee_frac, bt_toggles = carry_walk(
        data, threshold, lookback, rebalance, BACKTEST_TOGGLE_COST
    )
    pp_strat, pp_fee_frac, pp_toggles = carry_walk(
        data, threshold, lookback, rebalance, PAPER_TOGGLE_COST
    )
    bt_m, pp_m = fcb._metrics(bt_strat), fcb._metrics(pp_strat)

    cap = float(INITIAL_CAPITAL)
    bt_fees = _cents(Decimal(str(bt_fee_frac * cap)))
    pp_fees = _cents(Decimal(str(pp_fee_frac * cap)))
    pp_net_equity = _cents(INITIAL_CAPITAL * Decimal(str(1 + pp_m["total_return_pct"] / 100)))

    ledger = build_ledger(pp_net_equity, pp_fees)
    ledger_balance = ledger.balances[0].amount

    divergence = build_synthetic_divergence_report(
        report_id=ApprovalId("APR-S3-CARRY-PAPER-DIVERGENCE"),
        strategy_context_ref=DomainRef("SV-FUNDING-CARRY-BASIS-DELTA-NEUTRAL"),
        backtest_run_ref=RunId("RUN-BACKTEST-FUNDING-CARRY-BASIS"),
        paper_context_ref=DomainRef("APR-S3-CARRY-PAPER-LANE"),
        backtest_metrics={
            DivergenceMetric.TRADE_COUNT: Decimal(bt_toggles),
            DivergenceMetric.FEE_TOTAL: bt_fees,
        },
        synthetic_metrics={
            DivergenceMetric.TRADE_COUNT: Decimal(pp_toggles),
            DivergenceMetric.FEE_TOTAL: pp_fees,
        },
        # TRADE_COUNT must match (same signals); FEE_TOTAL is expected to diverge — that
        # divergence IS the execution finding, not a bug.
        tolerances={
            DivergenceMetric.TRADE_COUNT: Decimal("0"),
            DivergenceMetric.FEE_TOTAL: Decimal("50"),
        },
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )

    carry_survives = pp_m["ann_return_pct"] > 0
    finding = (
        f"Realistic per-leg execution (spot+perp, taker {TAKER_FEE_BPS}bps + slippage "
        f"{SLIPPAGE_BPS}bps = {PAPER_TOGGLE_COST * 10000:.0f}bps/toggle vs the backtest's "
        f"{BACKTEST_TOGGLE_COST * 10000:.0f}bps) cuts annual carry from {bt_m['ann_return_pct']}% "
        f"to {pp_m['ann_return_pct']}% ({pp_toggles} leg-toggles, ${pp_fees} execution cost). "
        + (
            "Carry stays net-positive after realistic execution — the edge is execution-robust "
            "at this turnover; remaining risk is COUNTERPARTY (operator/venue), not backtest math."
            if carry_survives
            else "Carry goes net-negative once realistic execution is charged — the coarse "
            "backtest fee was masking a turnover cost the edge cannot pay. NOT tradeable as-is."
        )
    )

    return {
        "schema": "tios-s3-carry-paper-v1",
        "mode": PaperLaneMode.SYNTHETIC_LOCAL_SIMULATOR.value,
        "stage": Stage.S3_PAPER_DEMO.value,
        "status": "PAPER_LANE_RAN_SYNTHETICALLY_NOT_VALIDATED",
        "approval_status": "NOT_ELIGIBLE",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "candidate": {
            "strategy_id": "STRAT-FUNDING-CARRY-BASIS-DELTA-NEUTRAL",
            "universe_pairs": len(data),
            "periods_8h": len(periods),
            "best_config": {
                "threshold": threshold,
                "lookback": lookback,
                "rebalance": rebalance,
            },
            "validation_note": "basis-aware carry DSR 1.0 but verdict_is_genuine=false; this "
            "probe measures the EXECUTION piece that DSR omitted. Still NOT_ELIGIBLE.",
        },
        "backtest_baseline": {
            "toggle_fee_bps": BACKTEST_TOGGLE_COST * 10000,
            "ann_return_pct": bt_m["ann_return_pct"],
            "total_return_pct": bt_m["total_return_pct"],
            "max_drawdown_pct": bt_m["max_drawdown_pct"],
            "leg_toggles": bt_toggles,
            "execution_cost_usdt": str(bt_fees),
        },
        "paper_realistic_execution": {
            "toggle_fee_bps": PAPER_TOGGLE_COST * 10000,
            "ann_return_pct": pp_m["ann_return_pct"],
            "total_return_pct": pp_m["total_return_pct"],
            "max_drawdown_pct": pp_m["max_drawdown_pct"],
            "leg_toggles": pp_toggles,
            "execution_cost_usdt": str(pp_fees),
            "final_equity_usdt": str(pp_net_equity),
        },
        "ann_return_erosion_pct": round(bt_m["ann_return_pct"] - pp_m["ann_return_pct"], 2),
        "ledger": {
            "entries": len(ledger.entries),
            "final_balance_usdt": str(ledger_balance),
            "reconstructs_paper_equity": ledger_balance == pp_net_equity,
        },
        "divergence_report": {
            "status": divergence.status.value,
            "observations": [
                {
                    "metric": obs.metric.value,
                    "backtest_value": str(obs.backtest_value),
                    "paper_value": str(obs.paper_value),
                    "tolerance": str(obs.tolerance),
                    "within_tolerance": abs(obs.backtest_value - obs.paper_value) <= obs.tolerance,
                }
                for obs in divergence.observations
            ],
        },
        "finding": finding,
        "prohibited": [
            "credential_request",
            "venue_account_connection",
            "order_submit_cancel_replace",
            "paper_demo_live_activation",
            "real_money",
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    artifact = OUT / "S3_CARRY_PAPER_2026_07_12.json"
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bt, pp = report["backtest_baseline"], report["paper_realistic_execution"]
    print(f"config: {report['candidate']['best_config']}  ({report['candidate']['periods_8h']} 8h)")
    print(f"backtest (coarse {bt['toggle_fee_bps']:.0f}bps): ann {bt['ann_return_pct']}%")
    print(f"paper (realistic {pp['toggle_fee_bps']:.0f}bps): ann {pp['ann_return_pct']}%")
    print(
        f"erosion: {report['ann_return_erosion_pct']} pct-pts   divergence: "
        f"{report['divergence_report']['status']}"
    )
    print(report["finding"])


if __name__ == "__main__":
    main()
