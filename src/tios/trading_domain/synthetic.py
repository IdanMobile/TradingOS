"""Pure synthetic fill, ledger, and position reducers with no execution path."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from .models import (
    AccountId,
    ApprovalId,
    ContractError,
    CreatorType,
    DivergenceMetric,
    DivergenceObservation,
    DivergenceStatus,
    DomainRef,
    FillEvent,
    InstrumentId,
    LedgerDirection,
    LedgerId,
    LiquidityRole,
    MarketBar,
    MarketQuote,
    Money,
    OrderIntent,
    OrderType,
    PaperDivergenceReport,
    PaperFillPriceSource,
    PaperOperationsEventKind,
    PaperOperationsEventRecord,
    PaperOperationsEventSeverity,
    PaperOperationsRunbook,
    PaperStabilityReport,
    PaperStabilityStatus,
    PortfolioId,
    PositionId,
    PositionSnapshot,
    PositionStatus,
    Provenance,
    RiskId,
    RunId,
    Side,
    SignedMoney,
    Stage,
    SyntheticAccountSnapshot,
    SyntheticLedgerEntry,
    SyntheticLedgerEntryKind,
    SyntheticLedgerSnapshot,
    SyntheticPaperFillPolicy,
    SyntheticPortfolioSnapshot,
)

_BPS = Decimal("10000")


class SyntheticFillStatus(StrEnum):
    FILLED = "FILLED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    LIMIT_NOT_REACHED = "LIMIT_NOT_REACHED"


@dataclass(frozen=True, slots=True)
class SyntheticFillCalculation:
    status: SyntheticFillStatus
    quantity: Decimal
    price: Decimal | None
    notional: Money | None
    fee: Money | None
    liquidity_role: LiquidityRole | None
    reason: str


@dataclass(frozen=True, slots=True)
class SyntheticExecutedFill:
    intent: OrderIntent
    fill: FillEvent

    def __post_init__(self) -> None:
        if (
            self.intent.run_ref != self.fill.run_ref
            or self.intent.instrument != self.fill.instrument
        ):
            raise ContractError("synthetic executed fill context must match its intent")


@dataclass(frozen=True, slots=True)
class SyntheticPortfolioProjection:
    account: SyntheticAccountSnapshot
    portfolio: SyntheticPortfolioSnapshot


def build_synthetic_divergence_report(
    *,
    report_id: ApprovalId,
    strategy_context_ref: DomainRef,
    backtest_run_ref: RunId,
    paper_context_ref: DomainRef,
    backtest_metrics: dict[DivergenceMetric, Decimal],
    synthetic_metrics: dict[DivergenceMetric, Decimal],
    tolerances: dict[DivergenceMetric, Decimal],
    evidence_refs: tuple[DomainRef, ...],
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> PaperDivergenceReport:
    """Compare like-for-like retained metrics without activating a paper lane."""
    metrics = set(backtest_metrics)
    if not metrics or set(synthetic_metrics) != metrics or set(tolerances) != metrics:
        raise ContractError("divergence metric and tolerance sets must match and be nonempty")
    observations = tuple(
        DivergenceObservation(
            metric=metric,
            backtest_value=backtest_metrics[metric],
            paper_value=synthetic_metrics[metric],
            tolerance=tolerances[metric],
        )
        for metric in sorted(metrics, key=lambda item: item.value)
    )
    return PaperDivergenceReport(
        report_id=report_id,
        strategy_context_ref=strategy_context_ref,
        backtest_run_ref=backtest_run_ref,
        paper_context_ref=paper_context_ref,
        observations=observations,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )


def evaluate_paper_stability(
    *,
    report_id: ApprovalId,
    paper_lane_ref: ApprovalId,
    divergence_report: PaperDivergenceReport,
    runbook: PaperOperationsRunbook,
    runtime_risk_policy_ref: RiskId,
    window_started_at: datetime,
    window_ended_at: datetime,
    required_observation_hours: Decimal,
    events: tuple[PaperOperationsEventRecord, ...],
    evidence_refs: tuple[DomainRef, ...],
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> PaperStabilityReport:
    """Compute paper stability from retained heartbeats, incidents, and divergence."""
    if window_started_at >= window_ended_at:
        raise ContractError("paper stability window start must precede end")
    if any(
        event.runbook_ref != runbook.runbook_id
        or not window_started_at <= event.occurred_at <= window_ended_at
        for event in events
    ):
        raise ContractError("paper stability events must match the runbook and window")
    expected_heartbeats = max(
        1,
        int(
            (window_ended_at - window_started_at).total_seconds()
            // runbook.heartbeat_interval_seconds
        ),
    )
    observed_heartbeats = sum(event.kind is PaperOperationsEventKind.HEARTBEAT for event in events)
    uptime = min(Decimal(observed_heartbeats) / Decimal(expected_heartbeats), Decimal(1))
    missed = sum(event.kind is PaperOperationsEventKind.HEARTBEAT_MISSED for event in events)
    incidents = sum(
        event.severity in (PaperOperationsEventSeverity.WARN, PaperOperationsEventSeverity.CRITICAL)
        and event.kind is not PaperOperationsEventKind.HEARTBEAT_MISSED
        for event in events
    )
    duration_hours = Decimal(str((window_ended_at - window_started_at).total_seconds() / 3600))
    passed = (
        duration_hours >= required_observation_hours
        and uptime == 1
        and incidents == 0
        and missed == 0
        and divergence_report.status is DivergenceStatus.WITHIN_TOLERANCE
    )
    return PaperStabilityReport(
        report_id=report_id,
        stage=Stage.S3_PAPER_DEMO,
        paper_lane_ref=paper_lane_ref,
        divergence_report_ref=divergence_report.report_id,
        runbook_ref=runbook.runbook_id,
        runtime_risk_policy_ref=runtime_risk_policy_ref,
        window_started_at=window_started_at,
        window_ended_at=window_ended_at,
        required_observation_hours=required_observation_hours,
        observed_uptime_fraction=uptime,
        incident_count=incidents,
        missed_heartbeat_count=missed,
        status=PaperStabilityStatus.PASS if passed else PaperStabilityStatus.FAIL,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )


def calculate_synthetic_fill(
    *,
    intent: OrderIntent,
    policy: SyntheticPaperFillPolicy,
    bar: MarketBar | None = None,
    quote: MarketQuote | None = None,
) -> SyntheticFillCalculation:
    """Calculate one deterministic local fill; never creates an order or account change."""
    if policy.price_source is PaperFillPriceSource.QUOTE_MIDPOINT:
        if quote is None or quote.market.instrument != intent.instrument:
            raise ContractError("quote midpoint fill calculation requires a matching quote")
        reference = (quote.bid_price + quote.ask_price) / 2
        low, high = quote.bid_price, quote.ask_price
    else:
        if bar is None or bar.market.instrument != intent.instrument:
            raise ContractError("bar fill calculation requires a matching market bar")
        reference = (
            bar.close
            if policy.price_source is PaperFillPriceSource.BAR_CLOSE
            else (bar.high + bar.low) / 2
        )
        low, high = bar.low, bar.high

    if intent.stop_price is not None:
        triggered = (
            high >= intent.stop_price if intent.side is Side.BUY else low <= intent.stop_price
        )
        if not triggered:
            return _unfilled(
                intent.quantity, SyntheticFillStatus.NOT_TRIGGERED, "stop not triggered"
            )
    if intent.limit_price is not None:
        reached = (
            low <= intent.limit_price if intent.side is Side.BUY else high >= intent.limit_price
        )
        if not reached:
            return _unfilled(
                intent.quantity,
                SyntheticFillStatus.LIMIT_NOT_REACHED,
                "limit price not reached",
            )

    multiplier = Decimal(1) + (
        policy.slippage_bps / _BPS if intent.side is Side.BUY else -policy.slippage_bps / _BPS
    )
    price = reference * multiplier
    if intent.limit_price is not None:
        price = (
            min(price, intent.limit_price)
            if intent.side is Side.BUY
            else max(price, intent.limit_price)
        )
    liquidity = (
        LiquidityRole.MAKER
        if intent.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT)
        else LiquidityRole.TAKER
    )
    fee_bps = policy.maker_fee_bps if liquidity is LiquidityRole.MAKER else policy.taker_fee_bps
    notional_amount = price * intent.quantity
    currency = intent.instrument.quote_currency
    return SyntheticFillCalculation(
        status=SyntheticFillStatus.FILLED,
        quantity=intent.quantity,
        price=price,
        notional=Money(notional_amount, currency),
        fee=Money(notional_amount * fee_bps / _BPS, currency),
        liquidity_role=liquidity,
        reason="deterministic local policy fill",
    )


def _unfilled(
    quantity: Decimal, status: SyntheticFillStatus, reason: str
) -> SyntheticFillCalculation:
    return SyntheticFillCalculation(status, quantity, None, None, None, None, reason)


def initialize_synthetic_ledger(
    *,
    ledger_id: LedgerId,
    entry_id: ApprovalId,
    initial_capital: Money,
    occurred_at: datetime,
    source_ref: DomainRef,
    evidence_refs: tuple[DomainRef, ...],
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> SyntheticLedgerSnapshot:
    entry = SyntheticLedgerEntry(
        entry_id=entry_id,
        occurred_at=occurred_at,
        kind=SyntheticLedgerEntryKind.INITIAL_CAPITAL,
        direction=LedgerDirection.CREDIT,
        amount=initial_capital,
        balance_after=initial_capital,
        source_ref=source_ref,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )
    return SyntheticLedgerSnapshot(
        ledger_id=ledger_id,
        stage=Stage.S3_PAPER_DEMO,
        as_of=occurred_at,
        entries=(entry,),
        balances=(initial_capital,),
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )


def apply_synthetic_ledger_change(
    snapshot: SyntheticLedgerSnapshot,
    *,
    entry_id: ApprovalId,
    occurred_at: datetime,
    kind: SyntheticLedgerEntryKind,
    direction: LedgerDirection,
    amount: Money,
    source_ref: DomainRef,
    evidence_refs: tuple[DomainRef, ...],
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> SyntheticLedgerSnapshot:
    """Return the next ledger snapshot; exact duplicate entry IDs reuse prior state."""
    existing = next((entry for entry in snapshot.entries if entry.entry_id == entry_id), None)
    if existing is not None:
        if (
            existing.occurred_at,
            existing.kind,
            existing.direction,
            existing.amount,
            existing.source_ref,
            existing.evidence_refs,
        ) == (occurred_at, kind, direction, amount, source_ref, evidence_refs):
            return snapshot
        raise ContractError("synthetic ledger idempotency key conflicts with retained entry")
    if occurred_at < snapshot.as_of:
        raise ContractError("synthetic ledger changes must be time ordered")
    balances = {money.currency: money.amount for money in snapshot.balances}
    if amount.currency not in balances:
        raise ContractError("synthetic ledger currency must be initialized first")
    next_amount = balances[amount.currency] + (
        amount.amount if direction is LedgerDirection.CREDIT else -amount.amount
    )
    if next_amount < 0:
        raise ContractError("synthetic ledger change would overdraw the balance")
    entry = SyntheticLedgerEntry(
        entry_id=entry_id,
        occurred_at=occurred_at,
        kind=kind,
        direction=direction,
        amount=amount,
        balance_after=Money(next_amount, amount.currency),
        source_ref=source_ref,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )
    balances[amount.currency] = next_amount
    return replace(
        snapshot,
        as_of=occurred_at,
        entries=snapshot.entries + (entry,),
        balances=tuple(Money(value, currency) for currency, value in sorted(balances.items())),
        evidence_refs=tuple(dict.fromkeys(snapshot.evidence_refs + evidence_refs)),
        created_at=created_at,
    )


def project_synthetic_spot_position(
    *,
    position_id: PositionId,
    run_ref: RunId,
    instrument: InstrumentId,
    executions: tuple[SyntheticExecutedFill, ...],
    mark_price: Decimal,
    as_of: datetime,
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> PositionSnapshot:
    """Project fee-aware long-only spot P&L from ordered retained synthetic fills."""
    if mark_price <= 0 or not mark_price.is_finite():
        raise ContractError("synthetic position mark price must be finite and positive")
    quantity = Decimal(0)
    cost = Decimal(0)
    realized = Decimal(0)
    for index, execution in enumerate(executions, start=1):
        intent, fill = execution.intent, execution.fill
        if intent.run_ref != run_ref or intent.instrument != instrument or fill.filled_at > as_of:
            raise ContractError("synthetic position fill does not match projection context")
        if intent.side is Side.BUY:
            quantity += fill.quantity
            cost += fill.price * fill.quantity + fill.fee.amount
        else:
            if fill.quantity > quantity:
                raise ContractError("synthetic spot position cannot sell more than it holds")
            average = cost / quantity
            realized += (fill.price - average) * fill.quantity - fill.fee.amount
            quantity -= fill.quantity
            cost = average * quantity
        if index > 1 and executions[index - 2].fill.filled_at > fill.filled_at:
            raise ContractError("synthetic position fills must be time ordered")
    average_price = cost / quantity if quantity else None
    unrealized = (
        (mark_price - average_price) * quantity if average_price is not None else Decimal(0)
    )
    status = (
        PositionStatus.OPEN
        if quantity
        else PositionStatus.CLOSED
        if executions
        else PositionStatus.FLAT
    )
    return PositionSnapshot(
        position_id=position_id,
        run_ref=run_ref,
        instrument=instrument,
        as_of=as_of,
        quantity=quantity,
        average_price=average_price,
        realized_pnl=SignedMoney(realized, instrument.quote_currency),
        unrealized_pnl=SignedMoney(unrealized, instrument.quote_currency),
        status=status,
        event_cursor=len(executions),
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )


def project_synthetic_portfolio(
    *,
    account_id: AccountId,
    portfolio_id: PortfolioId,
    ledger: SyntheticLedgerSnapshot,
    positions: tuple[PositionSnapshot, ...],
    marks: dict[InstrumentId, Decimal],
    reporting_currency: str,
    as_of: datetime,
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
    evidence_refs: tuple[DomainRef, ...],
) -> SyntheticPortfolioProjection:
    """Derive a synthetic account and marked portfolio from retained local state."""
    if ledger.as_of > as_of:
        raise ContractError("synthetic portfolio cannot precede its ledger")
    if len({position.instrument for position in positions}) != len(positions):
        raise ContractError("synthetic portfolio positions must have unique instruments")
    cash = next((money for money in ledger.balances if money.currency == reporting_currency), None)
    if cash is None:
        raise ContractError("synthetic portfolio reporting currency is absent from ledger")
    marked_value = Decimal(0)
    for position in positions:
        if position.instrument.quote_currency != reporting_currency or position.as_of > as_of:
            raise ContractError("synthetic position does not match portfolio context")
        mark = marks.get(position.instrument)
        if position.status is PositionStatus.OPEN:
            if mark is None or mark <= 0 or not mark.is_finite():
                raise ContractError("open synthetic positions require a finite positive mark")
            assert position.average_price is not None
            expected_unrealized = (mark - position.average_price) * position.quantity
            if position.unrealized_pnl.amount != expected_unrealized:
                raise ContractError("synthetic position unrealized P&L does not match its mark")
            marked_value += mark * position.quantity
        elif mark is not None:
            raise ContractError("closed or flat synthetic positions must not carry a mark")
    account = SyntheticAccountSnapshot(
        account_id=account_id,
        ledger_ref=ledger.ledger_id,
        stage=Stage.S3_PAPER_DEMO,
        as_of=as_of,
        balances=ledger.balances,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )
    portfolio = SyntheticPortfolioSnapshot(
        portfolio_id=portfolio_id,
        account_ref=account_id,
        ledger_ref=ledger.ledger_id,
        stage=Stage.S3_PAPER_DEMO,
        as_of=as_of,
        reporting_currency=reporting_currency,
        cash=(cash,),
        positions=positions,
        equity=(Money(cash.amount + marked_value, reporting_currency),),
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )
    return SyntheticPortfolioProjection(account, portfolio)
