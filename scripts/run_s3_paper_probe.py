#!/usr/bin/env python3
"""Run the S3 paper lane END-TO-END over frozen data, in synthetic probe mode.

Operator request (2026-07-12): with no strategy passing validation, exercise the
S3 paper-lane machinery itself so it is proven to work — WITHOUT faking a verdict
or touching a venue. This drives a candidate's signals through the real inert
trading-domain contracts: synthetic fill -> ledger -> spot position -> portfolio
-> backtest/paper divergence report.

Hard boundaries (unchanged, D-036/D-037/AD SS AA):
  * candidate stays NOT_ELIGIBLE / execution_authority=NONE
  * mode = SYNTHETIC_LOCAL_SIMULATOR; venue_connection=NONE; no order route
  * paper/live orders DISABLED; this is a local historical replay, not trading
The candidate used (QC2 Donchian, ETHUSDT 1h, window=40) is the strongest proxy
row found so far, but it FAILED validation (G10 DSR 0.7564 < 0.95). It is used
ONLY as plumbing input; nothing here approves or promotes it.

ponytail: reuses the trading_domain synthetic reducers + seed proxy + donchian
builder; adds only the bar-walk that wires signals into fills.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_external_strategy_search as ext  # noqa: E402
import scripts.run_seed_research_cycle_v0 as seed  # noqa: E402
from tios.trading_domain import (  # noqa: E402
    AccountId,
    ApprovalId,
    CreatorType,
    DatasetId,
    DivergenceMetric,
    DomainRef,
    FillEvent,
    FillId,
    InstrumentId,
    LedgerDirection,
    LedgerId,
    LiquidityRole,
    Market,
    MarketBar,
    MarketName,
    Money,
    OrderId,
    OrderIntent,
    OrderType,
    PaperFeeModel,
    PaperFillPriceSource,
    PaperLaneMode,
    PaperLaneProposal,
    PortfolioId,
    PositionId,
    PositionStatus,
    Provenance,
    RunId,
    Side,
    Stage,
    StageGateId,
    SyntheticExecutedFill,
    SyntheticFillStatus,
    SyntheticLedgerEntryKind,
    SyntheticPaperFillPolicy,
    VenueFamily,
    apply_synthetic_ledger_change,
    build_synthetic_divergence_report,
    calculate_synthetic_fill,
    initialize_synthetic_ledger,
    project_synthetic_portfolio,
    project_synthetic_spot_position,
)

OUT = ROOT / "artifacts" / "trading_domain" / "s3_paper_probe"
CREATED_AT = datetime(2026, 7, 12, tzinfo=UTC)
BASE_TIME = datetime(2021, 1, 1, tzinfo=UTC)  # synthetic monotonic bar clock
EVIDENCE = (DomainRef("EV-S3-PAPER-PROBE-2026-07-12"),)
PROVENANCE = Provenance(EVIDENCE)
INITIAL_CAPITAL = Decimal("10000")
SIZE_BUFFER = Decimal("0.001")  # ponytail: 0.1% cash headroom so fee rounding never overdraws
TAKER_FEE_BPS = Decimal("10")  # 0.1% — aligned with the backtest proxy fee for a clean comparison
SLIPPAGE_BPS = Decimal("2")


@dataclass(frozen=True)
class Candidate:
    strategy_id: str
    dataset: str
    donchian_window: int
    instrument: str
    timeframe_minutes: int


# Strongest proxy row to date — still validation-FAILED, used as plumbing input only.
CANDIDATE = Candidate("STRAT-QC2-donchian-breakout", "ETHUSDT_1h", 40, "ETH-USDT.BINANCE_SPOT", 60)


def _market(candidate: Candidate) -> Market:
    from tios.trading_domain import Timeframe

    tf = {5: Timeframe.M5, 15: Timeframe.M15, 60: Timeframe.H1}[candidate.timeframe_minutes]
    return Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BINANCE_SPOT"),
        InstrumentId(candidate.instrument),
        tf,
        DatasetId(f"DS-{candidate.dataset}"),
    )


def _bar(market: Market, candles: dict, index: int, minutes: int) -> MarketBar:
    open_time = BASE_TIME + timedelta(minutes=minutes * index)
    return MarketBar(
        market=market,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=minutes),
        open=candles["open"][index],
        high=candles["high"][index],
        low=candles["low"][index],
        close=candles["close"][index],
        volume=Decimal("0"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


@dataclass
class PaperRun:
    executed: list[SyntheticExecutedFill]
    ledger: object
    fee_total: Decimal
    trade_count: int
    final_position: object
    final_equity: Decimal


def run_paper_lane(candidate: Candidate, candles: dict | None = None) -> PaperRun:
    """Walk frozen bars, routing entry/exit signals through the synthetic contracts.

    `candles` may be injected for a fast deterministic test; otherwise the frozen
    dataset is loaded.
    """
    if candles is None:
        candles = seed.load_candles(seed.DATASETS[candidate.dataset])
    entries, exits = ext.donchian_breakout(candidate.donchian_window, candidate.donchian_window)(
        candles
    )
    market = _market(candidate)
    instrument = market.instrument
    run_ref = RunId(f"RUN-S3-PAPER-PROBE-{candidate.dataset}")
    minutes = candidate.timeframe_minutes

    ledger = initialize_synthetic_ledger(
        ledger_id=LedgerId(f"LEDGER-S3-PAPER-PROBE-{candidate.dataset}"),
        entry_id=ApprovalId("APR-S3-PAPER-PROBE-LEDGER-INITIAL"),
        initial_capital=Money(INITIAL_CAPITAL, "USDT"),
        occurred_at=BASE_TIME,
        source_ref=DomainRef("APR-S3-PAPER-PROBE-LANE"),
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    policy = SyntheticPaperFillPolicy(
        policy_id=ApprovalId("APR-S3-PAPER-PROBE-FILL-POLICY"),
        stage=Stage.S3_PAPER_DEMO,
        price_source=PaperFillPriceSource.BAR_CLOSE,
        fee_model=PaperFeeModel.FIXED_BPS,
        maker_fee_bps=TAKER_FEE_BPS,
        taker_fee_bps=TAKER_FEE_BPS,
        slippage_bps=SLIPPAGE_BPS,
        max_fill_latency_seconds=minutes * 60,
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )

    executed: list[SyntheticExecutedFill] = []
    cash = INITIAL_CAPITAL
    quantity = Decimal("0")
    fee_total = Decimal("0")
    n = len(candles["open"])
    fee_multiplier = Decimal("1") + TAKER_FEE_BPS / Decimal("10000")
    slip_multiplier = Decimal("1") + SLIPPAGE_BPS / Decimal("10000")

    for i in range(n - 1):
        exec_index = i + 1
        want_buy = quantity == 0 and entries[i]
        want_sell = quantity > 0 and exits[i]
        if not (want_buy or want_sell):
            continue
        side = Side.BUY if want_buy else Side.SELL
        exec_bar = _bar(market, candles, exec_index, minutes)
        reference = exec_bar.close  # BAR_CLOSE price source
        if side is Side.BUY:
            # Size all-in: cash = fill_price*qty + fee = ref*slip*qty*(1+fee). Buffer vs rounding.
            fill_price = reference * slip_multiplier
            qty = (cash * (Decimal("1") - SIZE_BUFFER)) / (fill_price * fee_multiplier)
        else:
            qty = quantity
        intent = OrderIntent(
            source_signal_ref=None,
            run_ref=run_ref,
            instrument=instrument,
            side=side,
            order_type=OrderType.MARKET,
            quantity=qty,
            limit_price=None,
            stop_price=None,
            bracket_levels=None,
            created_at=CREATED_AT,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        calc = calculate_synthetic_fill(intent=intent, policy=policy, bar=exec_bar)
        assert calc.status is SyntheticFillStatus.FILLED and calc.price is not None
        assert calc.notional is not None and calc.fee is not None
        fill_time = exec_bar.close_time
        event = FillEvent(
            fill_id=FillId(f"FILL-{candidate.dataset}-{exec_index}"),
            order_ref=OrderId(f"ORD-{candidate.dataset}-{exec_index}"),
            run_ref=run_ref,
            instrument=instrument,
            filled_at=fill_time,
            price=calc.price,
            quantity=calc.quantity,
            fee=calc.fee,
            liquidity_role=LiquidityRole.TAKER,
            created_at=CREATED_AT,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        executed.append(SyntheticExecutedFill(intent, event))
        fee_total += calc.fee.amount
        # Evolve the synthetic ledger: settlement + fee, mirroring the contract's kinds.
        settle_dir = LedgerDirection.DEBIT if side is Side.BUY else LedgerDirection.CREDIT
        ledger = apply_synthetic_ledger_change(
            ledger,
            entry_id=ApprovalId(f"APR-S3-PAPER-PROBE-SETTLE-{exec_index}"),
            occurred_at=fill_time,
            kind=SyntheticLedgerEntryKind.FILL_SETTLEMENT,
            direction=settle_dir,
            amount=calc.notional,
            source_ref=DomainRef(f"FILL-{candidate.dataset}-{exec_index}"),
            evidence_refs=EVIDENCE,
            created_at=CREATED_AT,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        ledger = apply_synthetic_ledger_change(
            ledger,
            entry_id=ApprovalId(f"APR-S3-PAPER-PROBE-FEE-{exec_index}"),
            occurred_at=fill_time,
            kind=SyntheticLedgerEntryKind.FEE,
            direction=LedgerDirection.DEBIT,
            amount=calc.fee,
            source_ref=DomainRef(f"FILL-{candidate.dataset}-{exec_index}"),
            evidence_refs=EVIDENCE,
            created_at=CREATED_AT,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        if side is Side.BUY:
            cash -= calc.notional.amount + calc.fee.amount
            quantity += calc.quantity
        else:
            cash += calc.notional.amount - calc.fee.amount
            quantity -= calc.quantity

    last_close = candles["close"][-1]
    # close_time of the final bar; every fill_at is a bar close_time <= this.
    last_time = BASE_TIME + timedelta(minutes=minutes * n)
    position = project_synthetic_spot_position(
        position_id=PositionId(f"POS-S3-PAPER-PROBE-{candidate.dataset}"),
        run_ref=run_ref,
        instrument=instrument,
        executions=tuple(executed),
        mark_price=last_close,
        as_of=last_time,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    marks = {instrument: last_close} if position.status is PositionStatus.OPEN else {}
    projection = project_synthetic_portfolio(
        account_id=AccountId(f"ACCT-S3-PAPER-PROBE-{candidate.dataset}"),
        portfolio_id=PortfolioId(f"PF-S3-PAPER-PROBE-{candidate.dataset}"),
        ledger=ledger,
        positions=(position,),
        marks=marks,
        reporting_currency="USDT",
        as_of=last_time,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
        evidence_refs=EVIDENCE,
    )
    final_equity = projection.portfolio.equity[0].amount
    return PaperRun(executed, ledger, fee_total, len(executed), position, final_equity)


def _backtest_with_fees(
    opens: list[Decimal], entries: list[bool], exits: list[bool]
) -> tuple[Decimal, int, Decimal]:
    """Next-open proxy that also tallies total fees, for divergence comparison."""
    cash, quantity, trades, fees = seed.INITIAL_CASH, Decimal("0"), 0, Decimal("0")
    for i in range(len(opens) - 1):
        price = opens[i + 1]
        if quantity == 0 and entries[i]:
            fee = cash * seed.FEES
            quantity = (cash - fee) / price
            cash, trades, fees = Decimal("0"), trades + 1, fees + fee
        elif quantity > 0 and exits[i]:
            gross = quantity * price
            fee = gross * seed.FEES
            cash, quantity, trades, fees = gross - fee, Decimal("0"), trades + 1, fees + fee
    equity = cash if quantity == 0 else quantity * opens[-1] * (Decimal("1") - seed.FEES)
    return equity, trades, fees


def build_report(candidate: Candidate) -> dict:
    paper = run_paper_lane(candidate)
    paper_return = paper.final_equity / INITIAL_CAPITAL - Decimal("1")

    # Backtest baseline: the deterministic next-open proxy over the same signals.
    candles = seed.load_candles(seed.DATASETS[candidate.dataset])
    entries, exits = ext.donchian_breakout(candidate.donchian_window, candidate.donchian_window)(
        candles
    )
    bt_equity, bt_trades, bt_fees = _backtest_with_fees(candles["open"], entries, exits)
    bt_return = bt_equity / seed.INITIAL_CASH - Decimal("1")

    # Divergence observations must be nonnegative (contract), so compare execution
    # fidelity — trade frequency and fees — not signed returns. Returns are reported
    # as plain fields below. TRADE_COUNT tolerance is loose because paper fills at bar
    # close while the backtest fills at next-open, which legitimately shifts a few fills.
    divergence = build_synthetic_divergence_report(
        report_id=ApprovalId("APR-S3-PAPER-PROBE-DIVERGENCE"),
        strategy_context_ref=DomainRef(
            f"SV-{candidate.strategy_id}-{candidate.dataset}-w{candidate.donchian_window}"
        ),
        backtest_run_ref=RunId(f"RUN-BACKTEST-PROXY-{candidate.dataset}"),
        paper_context_ref=DomainRef("APR-S3-PAPER-PROBE-LANE"),
        backtest_metrics={
            DivergenceMetric.TRADE_COUNT: Decimal(bt_trades),
            DivergenceMetric.FEE_TOTAL: bt_fees,
        },
        synthetic_metrics={
            DivergenceMetric.TRADE_COUNT: Decimal(paper.trade_count),
            DivergenceMetric.FEE_TOTAL: paper.fee_total,
        },
        tolerances={
            DivergenceMetric.TRADE_COUNT: Decimal("4"),
            DivergenceMetric.FEE_TOTAL: Decimal("50"),
        },
        evidence_refs=EVIDENCE,
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    proposal = PaperLaneProposal(
        proposal_id=ApprovalId("APR-S3-PAPER-PROBE-LANE"),
        strategy_context_ref=DomainRef(f"SV-{candidate.strategy_id}-{candidate.dataset}"),
        mode=PaperLaneMode.SYNTHETIC_LOCAL_SIMULATOR,
        gate_ref=StageGateId("GATE-S3-PAPER-DEMO-READINESS-2026-07-11"),
        requested_synthetic_capital=Money(INITIAL_CAPITAL, "USDT"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    return {
        "schema": "tios-s3-paper-probe-v1",
        "mode": "SYNTHETIC_LOCAL_SIMULATOR",
        "status": "PAPER_LANE_RAN_SYNTHETICALLY_NOT_VALIDATED",
        "approval_status": "NOT_ELIGIBLE",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "candidate": {
            "strategy_id": candidate.strategy_id,
            "dataset": candidate.dataset,
            "donchian_window": candidate.donchian_window,
            "validation_note": "FAILED validation (G10 DSR 0.7564 < 0.95); plumbing input only",
        },
        "paper_lane_proposal": {
            "proposal_id": str(proposal.proposal_id),
            "mode": proposal.mode.value,
            "requested_synthetic_capital": str(proposal.requested_synthetic_capital.amount),
        },
        "paper_result": {
            "initial_capital": str(INITIAL_CAPITAL),
            "final_equity": str(paper.final_equity),
            "total_return": str(paper_return),
            "trade_count": paper.trade_count,
            "fee_total": str(paper.fee_total),
            "final_position_status": paper.final_position.status.value,
            "ledger_entries": len(paper.ledger.entries),
        },
        "backtest_baseline": {
            "total_return": str(bt_return),
            "trade_count": bt_trades,
            "fee_total": str(bt_fees),
        },
        "paper_vs_backtest_return_gap": str(paper_return - bt_return),
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
    report = build_report(CANDIDATE)
    artifact = OUT / "S3_PAPER_PROBE_2026_07_12.json"
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(artifact.relative_to(ROOT)),
                "paper_return": report["paper_result"]["total_return"],
                "backtest_return": report["backtest_baseline"]["total_return"],
                "divergence_status": report["divergence_report"]["status"],
                "trades": report["paper_result"]["trade_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
