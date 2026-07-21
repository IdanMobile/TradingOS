"""Immutable offline decision traces for evidence-driven strategy improvement.

The contracts in this module join existing market decisions without adding an
execution command, venue connection, or approval capability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from .models import (
    ContractError,
    DomainRef,
    ExecutionAuthority,
    FillEvent,
    OrderCapability,
    OrderId,
    OrderIntent,
    Provenance,
    RiskDecision,
    RiskOutcome,
    Side,
    SignalEvent,
    VenueConnection,
)

_TRACE_ID = re.compile(r"TRACE-[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class DecisionTraceStatus(StrEnum):
    NO_TRADE = "NO_TRADE"
    RISK_BLOCKED = "RISK_BLOCKED"
    SIMULATED_UNFILLED = "SIMULATED_UNFILLED"
    SIMULATED_FILLED = "SIMULATED_FILLED"


class OutcomeClassification(StrEnum):
    NO_TRADE = "NO_TRADE"
    CORRECT_RISK_BLOCK = "CORRECT_RISK_BLOCK"
    PROFITABLE = "PROFITABLE"
    BREAKEVEN = "BREAKEVEN"
    ORDINARY_STATISTICAL_LOSS = "ORDINARY_STATISTICAL_LOSS"
    DATA_DEFECT = "DATA_DEFECT"
    RESEARCH_DEFECT = "RESEARCH_DEFECT"
    STRATEGY_WEAKNESS = "STRATEGY_WEAKNESS"
    EXECUTION_DEFECT = "EXECUTION_DEFECT"
    OPERATIONAL_DEFECT = "OPERATIONAL_DEFECT"
    UNKNOWN = "UNKNOWN"


DEFECT_CLASSIFICATIONS = frozenset(
    {
        OutcomeClassification.DATA_DEFECT,
        OutcomeClassification.RESEARCH_DEFECT,
        OutcomeClassification.STRATEGY_WEAKNESS,
        OutcomeClassification.EXECUTION_DEFECT,
        OutcomeClassification.OPERATIONAL_DEFECT,
    }
)


class AttributionBasis(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    AI_HYPOTHESIS = "AI_HYPOTHESIS"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    """Complete accounting for one offline decision horizon."""

    classification: OutcomeClassification
    gross_pnl: Decimal
    fees: Decimal
    slippage_cost: Decimal
    net_pnl: Decimal
    currency: str
    horizon_seconds: int
    reconciled: bool

    def __post_init__(self) -> None:
        for name in ("gross_pnl", "fees", "slippage_cost", "net_pnl"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ContractError(f"{name} must be a finite Decimal")
        if self.fees < 0 or self.slippage_cost < 0:
            raise ContractError("fees and slippage_cost must be nonnegative")
        if self.gross_pnl - self.fees - self.slippage_cost != self.net_pnl:
            raise ContractError("net_pnl must reconcile to gross_pnl minus costs")
        if not re.fullmatch(r"[A-Z][A-Z0-9]{2,9}", self.currency):
            raise ContractError("outcome currency must be an uppercase currency code")
        if not isinstance(self.horizon_seconds, int) or isinstance(self.horizon_seconds, bool):
            raise ContractError("horizon_seconds must be an integer")
        if self.horizon_seconds < 0:
            raise ContractError("horizon_seconds must be nonnegative")
        if not isinstance(self.reconciled, bool):
            raise ContractError("reconciled must be boolean")
        expected_sign = {
            OutcomeClassification.PROFITABLE: self.net_pnl > 0,
            OutcomeClassification.BREAKEVEN: self.net_pnl == 0,
            OutcomeClassification.ORDINARY_STATISTICAL_LOSS: self.net_pnl < 0,
            OutcomeClassification.NO_TRADE: self.net_pnl == 0,
            OutcomeClassification.CORRECT_RISK_BLOCK: self.net_pnl == 0,
        }.get(self.classification, True)
        if not expected_sign:
            raise ContractError("outcome classification must agree with net_pnl")


@dataclass(frozen=True, slots=True)
class FailureAttribution:
    """Evidence-backed diagnosis; AI output remains explicitly hypothetical."""

    classification: OutcomeClassification
    basis: AttributionBasis
    confidence: Decimal
    facts: tuple[str, ...]
    competing_hypotheses: tuple[str, ...]
    evidence_refs: tuple[DomainRef, ...]

    def __post_init__(self) -> None:
        if self.classification in {
            OutcomeClassification.NO_TRADE,
            OutcomeClassification.PROFITABLE,
            OutcomeClassification.BREAKEVEN,
        }:
            raise ContractError("failure attribution requires a loss, block, defect, or unknown")
        if (
            not isinstance(self.confidence, Decimal)
            or not self.confidence.is_finite()
            or not Decimal("0") <= self.confidence <= Decimal("1")
        ):
            raise ContractError("attribution confidence must be a Decimal from 0 to 1")
        for name in ("facts", "competing_hypotheses", "evidence_refs"):
            if not isinstance(getattr(self, name), tuple):
                raise ContractError(f"{name} must be an immutable tuple")
        if not self.facts or any(
            not isinstance(fact, str) or not fact.strip() for fact in self.facts
        ):
            raise ContractError("failure attribution requires non-empty facts")
        if any(
            not isinstance(hypothesis, str) or not hypothesis.strip()
            for hypothesis in self.competing_hypotheses
        ):
            raise ContractError("competing hypotheses must be non-empty strings")
        if any(not isinstance(ref, DomainRef) for ref in self.evidence_refs):
            raise ContractError("failure evidence references must be domain references")
        if not self.evidence_refs or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ContractError("failure attribution requires unique evidence references")
        if self.basis is AttributionBasis.AI_HYPOTHESIS and not self.competing_hypotheses:
            raise ContractError("AI attribution must preserve at least one competing hypothesis")

    @property
    def confirmed(self) -> bool:
        return self.basis in {AttributionBasis.DETERMINISTIC, AttributionBasis.HUMAN_REVIEWED}


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """One reproducible, capability-free decision from signal through outcome."""

    trace_id: str
    input_sha256: str
    feature_sha256: str
    strategy_spec_sha256: str
    signal: SignalEvent
    risk: RiskDecision
    status: DecisionTraceStatus
    intent: OrderIntent | None
    order_ref: OrderId | None
    fills: tuple[FillEvent, ...]
    outcome: DecisionOutcome
    attribution: FailureAttribution | None
    evidence_refs: tuple[DomainRef, ...]
    provenance: Provenance
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        if not _TRACE_ID.fullmatch(self.trace_id):
            raise ContractError("trace_id must start with TRACE- and have an opaque suffix")
        for name in ("input_sha256", "feature_sha256", "strategy_spec_sha256"):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise ContractError(f"{name} must be a lowercase SHA-256 digest")
        if not isinstance(self.fills, tuple) or not isinstance(self.evidence_refs, tuple):
            raise ContractError("fills and evidence_refs must be immutable tuples")
        if any(not isinstance(ref, DomainRef) for ref in self.evidence_refs):
            raise ContractError("trace evidence references must be domain references")
        if not self.evidence_refs or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ContractError("decision traces require unique evidence references")
        if not isinstance(self.provenance, Provenance):
            raise ContractError("trace provenance must be a Provenance value")
        if self.execution_authority is not ExecutionAuthority.NONE:
            raise ContractError("decision traces cannot grant execution authority")
        if self.venue_connection is not VenueConnection.NONE:
            raise ContractError("decision traces cannot connect to a venue")
        if self.paper_orders is not OrderCapability.DISABLED:
            raise ContractError("decision traces cannot enable paper orders")
        if self.live_orders is not OrderCapability.DISABLED:
            raise ContractError("decision traces cannot enable live orders")
        if self.risk.as_of < self.signal.observed_at:
            raise ContractError("risk decision cannot precede its signal")
        if self.intent is not None:
            if self.intent.run_ref != self.signal.run_ref:
                raise ContractError("intent and signal must share a run")
            if self.intent.instrument != self.signal.instrument:
                raise ContractError("intent and signal must share an instrument")
            if self.intent.source_signal_ref not in (None, self.signal.signal_id):
                raise ContractError("intent must reference the traced signal")
        fill_ids = [fill.fill_id for fill in self.fills]
        if len(set(fill_ids)) != len(fill_ids):
            raise ContractError("fill events must be unique")
        for fill in self.fills:
            if fill.run_ref != self.signal.run_ref or fill.instrument != self.signal.instrument:
                raise ContractError("fills must share the traced run and instrument")
            if self.order_ref is None or fill.order_ref != self.order_ref:
                raise ContractError("fills must reference the traced order")
        self._validate_state()

    def _validate_state(self) -> None:
        if self.status is DecisionTraceStatus.NO_TRADE:
            if self.signal.side is not Side.FLAT or self.intent or self.order_ref or self.fills:
                raise ContractError("NO_TRADE requires a flat signal and no order artifacts")
            if self.outcome.classification is not OutcomeClassification.NO_TRADE:
                raise ContractError("NO_TRADE requires a NO_TRADE outcome")
        elif self.status is DecisionTraceStatus.RISK_BLOCKED:
            if self.risk.decision is not RiskOutcome.BLOCK:
                raise ContractError("RISK_BLOCKED requires a blocking risk decision")
            if self.intent or self.order_ref or self.fills:
                raise ContractError("a blocked decision cannot have order artifacts")
            if self.outcome.classification not in {
                OutcomeClassification.CORRECT_RISK_BLOCK,
                OutcomeClassification.UNKNOWN,
            }:
                raise ContractError("blocked outcomes must be a correct block or unknown")
        elif self.status is DecisionTraceStatus.SIMULATED_UNFILLED:
            if self.risk.decision is not RiskOutcome.PASS or self.intent is None:
                raise ContractError("SIMULATED_UNFILLED requires approved intent")
            if self.fills:
                raise ContractError("SIMULATED_UNFILLED cannot contain fills")
            if self.outcome.net_pnl != 0 or self.outcome.classification not in {
                OutcomeClassification.EXECUTION_DEFECT,
                OutcomeClassification.OPERATIONAL_DEFECT,
                OutcomeClassification.UNKNOWN,
            }:
                raise ContractError("unfilled outcomes require zero P&L and failure attribution")
        elif self.status is DecisionTraceStatus.SIMULATED_FILLED:
            if self.risk.decision is not RiskOutcome.PASS:
                raise ContractError("SIMULATED_FILLED requires passing risk")
            if self.intent is None or self.order_ref is None or not self.fills:
                raise ContractError("SIMULATED_FILLED requires intent, order, and fills")
            if not self.outcome.reconciled:
                raise ContractError("a filled decision is incomplete until reconciled")
            if self.outcome.classification in {
                OutcomeClassification.NO_TRADE,
                OutcomeClassification.CORRECT_RISK_BLOCK,
            }:
                raise ContractError("a filled decision requires a realized outcome classification")
            if any(fill.fee.currency != self.outcome.currency for fill in self.fills):
                raise ContractError("fill and outcome currencies must agree")
            retained_fees = sum((fill.fee.amount for fill in self.fills), start=Decimal("0"))
            if retained_fees != self.outcome.fees:
                raise ContractError("outcome fees must reconcile to retained fills")

        requires_attribution = self.outcome.classification not in {
            OutcomeClassification.NO_TRADE,
            OutcomeClassification.PROFITABLE,
            OutcomeClassification.BREAKEVEN,
        }
        if requires_attribution != (self.attribution is not None):
            raise ContractError("loss, block, defect, and unknown outcomes require attribution")
        if self.attribution and self.attribution.classification is not self.outcome.classification:
            raise ContractError("outcome and attribution classifications must agree")


@dataclass(frozen=True, slots=True)
class HistoricalTradeTrace:
    """One reconstructed historical round trip with explicit evidence limitations.

    This is deliberately not a :class:`DecisionTrace`: retained legacy fills do not
    prove which signal or risk decision existed when the trade was produced.
    """

    trace_id: str
    source_sha256: str
    strategy_spec_sha256: str
    strategy_version_ref: DomainRef
    split_label: str
    source_trade_id: int
    pair: str
    opened_at: datetime
    closed_at: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    outcome: DecisionOutcome
    cost_flipped: bool
    evidence_refs: tuple[DomainRef, ...]
    provenance: Provenance
    reconstruction_limitations: tuple[str, ...]
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        if not _TRACE_ID.fullmatch(self.trace_id):
            raise ContractError("trace_id must start with TRACE- and have an opaque suffix")
        for name in ("source_sha256", "strategy_spec_sha256"):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise ContractError(f"{name} must be a lowercase SHA-256 digest")
        if self.strategy_version_ref.prefix != "SV-":
            raise ContractError("historical trade strategy must use an SV- reference")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.split_label):
            raise ContractError("split_label must be an uppercase identifier")
        if (
            not isinstance(self.source_trade_id, int)
            or isinstance(self.source_trade_id, bool)
            or self.source_trade_id < 0
        ):
            raise ContractError("source_trade_id must be a nonnegative integer")
        if not isinstance(self.pair, str) or not re.fullmatch(r"[A-Z0-9]+/[A-Z0-9]+", self.pair):
            raise ContractError("pair must be an uppercase base/quote symbol")
        for name in ("opened_at", "closed_at"):
            value = getattr(self, name)
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() != timedelta(0)
            ):
                raise ContractError(f"{name} must be timezone-aware UTC")
        if self.opened_at >= self.closed_at:
            raise ContractError("historical trade must close after it opens")
        for name in ("quantity", "entry_price", "exit_price"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ContractError(f"{name} must be a positive finite Decimal")
        expected_gross = (self.exit_price - self.entry_price) * self.quantity
        if self.outcome.gross_pnl != expected_gross:
            raise ContractError("historical trade gross P&L must reconcile to prices and quantity")
        expected_horizon = int((self.closed_at - self.opened_at).total_seconds())
        if self.outcome.horizon_seconds != expected_horizon or not self.outcome.reconciled:
            raise ContractError("historical trade outcome must be reconciled to its horizon")
        expected_classification = (
            OutcomeClassification.PROFITABLE
            if self.outcome.net_pnl > 0
            else OutcomeClassification.ORDINARY_STATISTICAL_LOSS
            if self.outcome.net_pnl < 0
            else OutcomeClassification.BREAKEVEN
        )
        if self.outcome.classification is not expected_classification:
            raise ContractError("historical trade classification must follow realized net P&L")
        if self.cost_flipped != (self.outcome.gross_pnl > 0 > self.outcome.net_pnl):
            raise ContractError("cost_flipped must reflect gross-positive, net-negative P&L")
        for name in ("evidence_refs", "reconstruction_limitations"):
            if not isinstance(getattr(self, name), tuple):
                raise ContractError(f"{name} must be an immutable tuple")
        if (
            not self.evidence_refs
            or any(not isinstance(ref, DomainRef) for ref in self.evidence_refs)
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
        ):
            raise ContractError("historical trade evidence must contain unique references")
        if not isinstance(self.provenance, Provenance):
            raise ContractError("historical trade provenance must be a Provenance value")
        if not self.reconstruction_limitations or any(
            not isinstance(item, str) or not item.strip()
            for item in self.reconstruction_limitations
        ):
            raise ContractError("historical trade must state reconstruction limitations")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("historical trade traces cannot grant trading capability")
