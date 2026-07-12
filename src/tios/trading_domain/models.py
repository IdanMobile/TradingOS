"""Framework-free, inert S2 trading-domain contracts.

These types describe retained historical evidence and read projections.  They
contain no venue connectivity or trading commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar


class ContractError(ValueError):
    """Raised when a trading-domain contract invariant is violated."""


_ID_PREFIXES = (
    "DS-",
    "STRAT-",
    "SV-",
    "HYP-",
    "EXP-",
    "RUN-",
    "LAB-",
    "SCORE-",
    "VAL-",
    "EV-",
    "APR-",
    "SRC-",
    "RA-",
    "CON-",
    "MDL-",
    "AGT-",
    "PRM-",
    "BMK-",
    "LRN-",
    "JOB-",
    "SIG-",
    "ORD-",
    "FILL-",
    "POS-",
    "ACCT-",
    "PF-",
    "RISK-",
    "ANN-",
    "GATE-",
    "LEDGER-",
)
_ID_SUFFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_CURRENCY = re.compile(r"[A-Z][A-Z0-9]{2,9}\Z")
_CONTEXT_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _require_decimal(value: Decimal, field_name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractError(f"{field_name} must be a finite Decimal")
    if value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ContractError(f"{field_name} must be {qualifier}")


def _require_utc(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContractError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ContractError(f"{field_name} must be UTC")


def _require_tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise ContractError(f"{field_name} must be an immutable tuple")


@dataclass(frozen=True, slots=True)
class PrefixedId:
    value: str
    prefix: ClassVar[str]

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.startswith(self.prefix):
            raise ContractError(f"id must start with {self.prefix}")
        if not _ID_SUFFIX.fullmatch(self.value[len(self.prefix) :]):
            raise ContractError("id must have a non-empty opaque suffix")

    def __str__(self) -> str:
        return self.value


class DatasetId(PrefixedId):
    prefix = "DS-"


class StrategyVersionId(PrefixedId):
    prefix = "SV-"


class RunId(PrefixedId):
    prefix = "RUN-"


class SignalId(PrefixedId):
    prefix = "SIG-"


class OrderId(PrefixedId):
    prefix = "ORD-"


class FillId(PrefixedId):
    prefix = "FILL-"


class PositionId(PrefixedId):
    prefix = "POS-"


class AccountId(PrefixedId):
    prefix = "ACCT-"


class PortfolioId(PrefixedId):
    prefix = "PF-"


class RiskId(PrefixedId):
    prefix = "RISK-"


class ApprovalId(PrefixedId):
    prefix = "APR-"


class AnnotationId(PrefixedId):
    prefix = "ANN-"


class StageGateId(PrefixedId):
    prefix = "GATE-"


class LedgerId(PrefixedId):
    prefix = "LEDGER-"


@dataclass(frozen=True, slots=True)
class DomainRef:
    value: str

    def __post_init__(self) -> None:
        prefix = next((item for item in _ID_PREFIXES if self.value.startswith(item)), None)
        if prefix is None or not _ID_SUFFIX.fullmatch(self.value[len(prefix) :]):
            raise ContractError("reference must be an opaque catalog-prefixed id")

    @property
    def prefix(self) -> str:
        return next(item for item in _ID_PREFIXES if self.value.startswith(item))

    def __str__(self) -> str:
        return self.value


class Environment(StrEnum):
    HISTORICAL_RESEARCH = "HISTORICAL_RESEARCH"


class ExecutionAuthority(StrEnum):
    NONE = "NONE"


class VenueConnection(StrEnum):
    NONE = "NONE"


class OrderCapability(StrEnum):
    DISABLED = "DISABLED"


class Stage(StrEnum):
    S3_PAPER_DEMO = "S3_PAPER_DEMO"
    S4_LIVE = "S4_LIVE"


class StageGateStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_OPERATOR_DECISION = "READY_FOR_OPERATOR_DECISION"
    APPROVED = "APPROVED"


class StageGateRequirementKind(StrEnum):
    EVIDENCE = "EVIDENCE"
    HUMAN_DECISION = "HUMAN_DECISION"
    CREDENTIAL_GRANT = "CREDENTIAL_GRANT"


class PaperLaneMode(StrEnum):
    SYNTHETIC_LOCAL_SIMULATOR = "SYNTHETIC_LOCAL_SIMULATOR"
    VENUE_DEMO_OR_TESTNET = "VENUE_DEMO_OR_TESTNET"


class DivergenceMetric(StrEnum):
    TOTAL_RETURN = "TOTAL_RETURN"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    TRADE_COUNT = "TRADE_COUNT"
    FILL_COUNT = "FILL_COUNT"
    FEE_TOTAL = "FEE_TOTAL"


class DivergenceStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    OUTSIDE_TOLERANCE = "OUTSIDE_TOLERANCE"


class PaperStabilityStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class LimitedLiveRiskPackageStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_OPERATOR_DECISION = "READY_FOR_OPERATOR_DECISION"
    REJECTED = "REJECTED"


class OperationalDrillKind(StrEnum):
    FEED_LOSS = "FEED_LOSS"
    STALE_DATA = "STALE_DATA"
    ENGINE_CRASH = "ENGINE_CRASH"
    MANUAL_KILL_SWITCH = "MANUAL_KILL_SWITCH"
    CREDENTIAL_REVOCATION = "CREDENTIAL_REVOCATION"


class OperationalDrillStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class SyntheticLedgerEntryKind(StrEnum):
    INITIAL_CAPITAL = "INITIAL_CAPITAL"
    ORDER_RESERVE = "ORDER_RESERVE"
    FILL_SETTLEMENT = "FILL_SETTLEMENT"
    FEE = "FEE"
    ADJUSTMENT = "ADJUSTMENT"


class LedgerDirection(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class PaperFillPriceSource(StrEnum):
    BAR_CLOSE = "BAR_CLOSE"
    BAR_MIDPOINT = "BAR_MIDPOINT"
    QUOTE_MIDPOINT = "QUOTE_MIDPOINT"


class PaperFeeModel(StrEnum):
    FIXED_BPS = "FIXED_BPS"


class KillSwitchMode(StrEnum):
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    AUTOMATIC_LOCAL_SIMULATION = "AUTOMATIC_LOCAL_SIMULATION"


class PaperRunbookInterventionMode(StrEnum):
    MANUAL_ONLY = "MANUAL_ONLY"
    LOCAL_SIMULATION_ONLY = "LOCAL_SIMULATION_ONLY"


class LiveRunbookEscalationMode(StrEnum):
    OPERATOR_MANUAL_ONLY = "OPERATOR_MANUAL_ONLY"
    DISABLE_AND_REVIEW = "DISABLE_AND_REVIEW"


class LiveOperationsEventKind(StrEnum):
    PROCESS_STARTED = "PROCESS_STARTED"
    PROCESS_STOPPED = "PROCESS_STOPPED"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_MISSED = "HEARTBEAT_MISSED"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    KILL_SWITCH_OBSERVED = "KILL_SWITCH_OBSERVED"
    ESCALATION_RECORDED = "ESCALATION_RECORDED"
    LOG_RETENTION_CHECK = "LOG_RETENTION_CHECK"


class LiveOperationsEventSeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class OperationalIncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class OperationalIncidentSeverity(StrEnum):
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class PaperOperationsEventKind(StrEnum):
    PROCESS_STARTED = "PROCESS_STARTED"
    PROCESS_STOPPED = "PROCESS_STOPPED"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_MISSED = "HEARTBEAT_MISSED"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    KILL_SWITCH_OBSERVED = "KILL_SWITCH_OBSERVED"
    LOG_RETENTION_CHECK = "LOG_RETENTION_CHECK"


class PaperOperationsEventSeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class CredentialPermission(StrEnum):
    READ_MARKET_DATA = "READ_MARKET_DATA"
    READ_ACCOUNT = "READ_ACCOUNT"
    PLACE_SPOT_ORDERS = "PLACE_SPOT_ORDERS"
    CANCEL_SPOT_ORDERS = "CANCEL_SPOT_ORDERS"
    FUNDS_OUT = "FUNDS_OUT"
    TRANSFER_FUNDS = "TRANSFER_FUNDS"


class CreatorType(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return {
            Timeframe.M1: 60,
            Timeframe.M5: 300,
            Timeframe.M15: 900,
            Timeframe.H1: 3600,
            Timeframe.H4: 14400,
            Timeframe.D1: 86400,
        }[self]


@dataclass(frozen=True, slots=True)
class MarketName:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CONTEXT_NAME.fullmatch(self.value):
            raise ContractError("market must be an uppercase canonical name")


@dataclass(frozen=True, slots=True)
class VenueFamily:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CONTEXT_NAME.fullmatch(self.value):
            raise ContractError("venue family must be an uppercase canonical name")


@dataclass(frozen=True, slots=True)
class InstrumentId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ContractError("instrument must be a string")
        pair, separator, venue = self.value.partition(".")
        base, dash, quote = pair.partition("-")
        if (
            separator != "."
            or dash != "-"
            or not base
            or not quote
            or not _CONTEXT_NAME.fullmatch(base)
            or not _CONTEXT_NAME.fullmatch(quote)
            or not _CONTEXT_NAME.fullmatch(venue)
        ):
            raise ContractError("instrument must match BASE-QUOTE.VENUE_FAMILY")

    @property
    def base_currency(self) -> str:
        return self.value.partition("-")[0]

    @property
    def quote_currency(self) -> str:
        return self.value.partition("-")[2].partition(".")[0]

    @property
    def venue_family(self) -> VenueFamily:
        return VenueFamily(self.value.partition(".")[2])


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        _require_decimal(self.amount, "money amount")
        if not isinstance(self.currency, str) or not _CURRENCY.fullmatch(self.currency):
            raise ContractError("currency must be an uppercase currency code")


@dataclass(frozen=True, slots=True)
class SignedMoney:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ContractError("signed money amount must be a finite Decimal")
        if not isinstance(self.currency, str) or not _CURRENCY.fullmatch(self.currency):
            raise ContractError("currency must be an uppercase currency code")


@dataclass(frozen=True, slots=True)
class Provenance:
    refs: tuple[DomainRef, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.refs, "provenance refs")
        if not self.refs or len(set(self.refs)) != len(self.refs):
            raise ContractError("provenance refs must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class Market:
    market: MarketName
    venue_family: VenueFamily
    instrument: InstrumentId
    timeframe: Timeframe
    dataset_ref: DatasetId

    def __post_init__(self) -> None:
        if self.instrument.venue_family != self.venue_family:
            raise ContractError("instrument and market venue families must match")


def _validate_record(
    schema_version: int,
    created_at: datetime,
    provenance: Provenance,
    environment: Environment,
) -> None:
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        raise ContractError("schema_version must be a positive integer")
    _require_utc(created_at, "created_at")
    if not isinstance(provenance, Provenance):
        raise ContractError("provenance must be a Provenance value")
    if environment is not Environment.HISTORICAL_RESEARCH:
        raise ContractError("only historical research records exist in S2")


def _validate_control_plane_record(
    schema_version: int,
    created_at: datetime,
    provenance: Provenance,
) -> None:
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        raise ContractError("schema_version must be a positive integer")
    _require_utc(created_at, "created_at")
    if not isinstance(provenance, Provenance):
        raise ContractError("provenance must be a Provenance value")


@dataclass(frozen=True, slots=True)
class StageGateRequirement:
    code: str
    kind: StageGateRequirementKind
    satisfied: bool
    evidence_refs: tuple[DomainRef, ...] = ()
    blocker: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not _CONTEXT_NAME.fullmatch(self.code):
            raise ContractError("stage-gate requirement code must be uppercase")
        _require_tuple(self.evidence_refs, "stage-gate evidence_refs")
        if self.satisfied:
            if not self.evidence_refs:
                raise ContractError("satisfied stage-gate requirements require evidence")
            if self.blocker is not None:
                raise ContractError("satisfied stage-gate requirements cannot have blockers")
            if self.kind is StageGateRequirementKind.HUMAN_DECISION and not any(
                ref.prefix == "APR-" for ref in self.evidence_refs
            ):
                raise ContractError("satisfied human requirements require APR evidence")
        elif not self.blocker or not self.blocker.strip():
            raise ContractError("blocked stage-gate requirements require a blocker")


@dataclass(frozen=True, slots=True)
class StageGateReadinessRecord:
    gate_id: StageGateId
    stage: Stage
    subject_ref: DomainRef
    requirements: tuple[StageGateRequirement, ...]
    status: StageGateStatus
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.requirements, "stage-gate requirements")
        if not self.requirements:
            raise ContractError("stage-gate readiness requires at least one requirement")
        if len({requirement.code for requirement in self.requirements}) != len(self.requirements):
            raise ContractError("stage-gate requirement codes must be unique")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("stage-gate records cannot grant execution capability")
        human_requirements = [
            requirement
            for requirement in self.requirements
            if requirement.kind is StageGateRequirementKind.HUMAN_DECISION
        ]
        if not human_requirements:
            raise ContractError("stage-gate readiness must include a human decision")
        all_satisfied = all(requirement.satisfied for requirement in self.requirements)
        non_human_satisfied = all(
            requirement.satisfied
            for requirement in self.requirements
            if requirement.kind is not StageGateRequirementKind.HUMAN_DECISION
        )
        human_satisfied = all(requirement.satisfied for requirement in human_requirements)
        if self.status is StageGateStatus.BLOCKED and all_satisfied:
            raise ContractError("a fully satisfied gate cannot be BLOCKED")
        if self.status is StageGateStatus.READY_FOR_OPERATOR_DECISION and (
            not non_human_satisfied or human_satisfied
        ):
            raise ContractError(
                "READY_FOR_OPERATOR_DECISION requires non-human evidence and pending human gates"
            )
        if self.status is StageGateStatus.APPROVED and not all_satisfied:
            raise ContractError("APPROVED stage gates require every requirement to be satisfied")
        required_codes = (
            {
                "S2_EXIT_PASS",
                "HG_3_APPROVED",
                "COMPLETE_APPROVABLE_STRATEGY_CONTEXT",
                "PAPER_LANE_ARCHITECTURE_DECISION",
                "SECURITY_REVIEW_PASS",
                "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL",
            }
            if self.stage is Stage.S3_PAPER_DEMO
            else {
                "S3_EXIT_PASS",
                "PAPER_STABILITY_PASS",
                "PAPER_DIVERGENCE_ACCEPTABLE",
                "LIVE_RISK_SECURITY_PACKAGE_PASS",
                "LIMITED_CAPITAL_VENUE_PROPOSAL",
                "HG_4_VENUE_OPERATOR_ELIGIBILITY",
                "HG_5_OPERATOR_APPROVAL",
                "RESTRICTED_CREDENTIAL_GRANT",
            }
        )
        missing = required_codes.difference(requirement.code for requirement in self.requirements)
        if missing:
            raise ContractError(
                f"{self.stage.value} readiness is missing required prerequisites: "
                + ", ".join(sorted(missing))
            )


@dataclass(frozen=True, slots=True)
class PaperLaneProposal:
    proposal_id: ApprovalId
    strategy_context_ref: DomainRef
    mode: PaperLaneMode
    gate_ref: StageGateId
    requested_synthetic_capital: Money
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        if self.mode is PaperLaneMode.VENUE_DEMO_OR_TESTNET:
            raise ContractError("venue demo/testnet proposals require a later credential gate")
        _require_decimal(
            self.requested_synthetic_capital.amount, "synthetic capital", positive=True
        )
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("paper-lane proposals cannot activate orders")


@dataclass(frozen=True, slots=True)
class LiveReadinessProposal:
    proposal_id: ApprovalId
    paper_context_ref: DomainRef
    gate_ref: StageGateId
    maximum_capital_at_risk: Money
    maximum_drawdown_fraction: Decimal
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_decimal(self.maximum_capital_at_risk.amount, "maximum capital", positive=True)
        _require_decimal(self.maximum_drawdown_fraction, "maximum drawdown", positive=True)
        if self.maximum_drawdown_fraction >= 1:
            raise ContractError("maximum drawdown must be a fraction below 1")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("live-readiness proposals cannot activate orders")


@dataclass(frozen=True, slots=True)
class DivergenceObservation:
    metric: DivergenceMetric
    backtest_value: Decimal
    paper_value: Decimal
    tolerance: Decimal

    def __post_init__(self) -> None:
        for name in ("backtest_value", "paper_value", "tolerance"):
            _require_decimal(getattr(self, name), name)
        if self.tolerance < 0:
            raise ContractError("divergence tolerance must be nonnegative")

    @property
    def absolute_difference(self) -> Decimal:
        return abs(self.paper_value - self.backtest_value)

    @property
    def status(self) -> DivergenceStatus:
        if self.tolerance == 0 and self.absolute_difference == 0:
            return DivergenceStatus.WITHIN_TOLERANCE
        if self.absolute_difference <= self.tolerance:
            return DivergenceStatus.WITHIN_TOLERANCE
        return DivergenceStatus.OUTSIDE_TOLERANCE


@dataclass(frozen=True, slots=True)
class PaperDivergenceReport:
    report_id: ApprovalId
    strategy_context_ref: DomainRef
    backtest_run_ref: RunId
    paper_context_ref: DomainRef
    observations: tuple[DivergenceObservation, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.observations, "divergence observations")
        _require_tuple(self.evidence_refs, "divergence evidence_refs")
        if not self.observations:
            raise ContractError("paper divergence reports require observations")
        if not self.evidence_refs:
            raise ContractError("paper divergence reports require evidence")
        if len({observation.metric for observation in self.observations}) != len(self.observations):
            raise ContractError("paper divergence metrics must be unique")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("paper divergence reports cannot activate orders")

    @property
    def status(self) -> DivergenceStatus:
        if any(
            observation.status is DivergenceStatus.OUTSIDE_TOLERANCE
            for observation in self.observations
        ):
            return DivergenceStatus.OUTSIDE_TOLERANCE
        return DivergenceStatus.WITHIN_TOLERANCE


@dataclass(frozen=True, slots=True)
class OperationalDrillRecord:
    drill_id: ApprovalId
    stage: Stage
    kind: OperationalDrillKind
    status: OperationalDrillStatus
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    blocker: str | None = None
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "drill evidence_refs")
        if self.status in (OperationalDrillStatus.PASS, OperationalDrillStatus.FAIL):
            if not self.evidence_refs:
                raise ContractError("completed operational drills require evidence")
            if self.blocker is not None:
                raise ContractError("completed operational drills cannot have blockers")
        if self.status is OperationalDrillStatus.BLOCKED and (
            not self.blocker or not self.blocker.strip()
        ):
            raise ContractError("blocked operational drills require a blocker")
        if self.status is OperationalDrillStatus.NOT_RUN and (
            self.evidence_refs or self.blocker is not None
        ):
            raise ContractError("NOT_RUN operational drills cannot carry evidence or blocker")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("operational drills cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticLedgerEntry:
    entry_id: ApprovalId
    occurred_at: datetime
    kind: SyntheticLedgerEntryKind
    direction: LedgerDirection
    amount: Money
    balance_after: Money
    source_ref: DomainRef
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.occurred_at, "occurred_at")
        _require_tuple(self.evidence_refs, "ledger entry evidence_refs")
        if not self.evidence_refs:
            raise ContractError("synthetic ledger entries require evidence")
        _require_decimal(self.amount.amount, "ledger amount", positive=True)
        if self.amount.currency != self.balance_after.currency:
            raise ContractError("ledger entry amount and balance currencies must match")
        _require_decimal(self.balance_after.amount, "ledger balance")


@dataclass(frozen=True, slots=True)
class SyntheticLedgerSnapshot:
    ledger_id: LedgerId
    stage: Stage
    as_of: datetime
    entries: tuple[SyntheticLedgerEntry, ...]
    balances: tuple[Money, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.as_of, "as_of")
        for name in ("entries", "balances", "evidence_refs"):
            _require_tuple(getattr(self, name), name)
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic ledgers are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError("synthetic ledgers must be explicitly non-real-money")
        if not self.entries or not self.evidence_refs:
            raise ContractError("synthetic ledger snapshots require entries and evidence")
        if len({entry.entry_id for entry in self.entries}) != len(self.entries):
            raise ContractError("synthetic ledger entry ids must be unique")
        if len({money.currency for money in self.balances}) != len(self.balances):
            raise ContractError("synthetic ledger balances must have unique currencies")
        if any(entry.occurred_at > self.as_of for entry in self.entries):
            raise ContractError("synthetic ledger entries cannot occur after snapshot time")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic ledgers cannot activate orders")
        latest: dict[str, Money] = {}
        running: dict[str, Decimal] = {}
        for entry in sorted(self.entries, key=lambda item: item.occurred_at):
            currency = entry.amount.currency
            previous = running.get(currency)
            if previous is None:
                if (
                    entry.kind is not SyntheticLedgerEntryKind.INITIAL_CAPITAL
                    or entry.direction is not LedgerDirection.CREDIT
                ):
                    raise ContractError(
                        "synthetic ledger currencies must begin with credited initial capital"
                    )
                previous = Decimal(0)
            elif entry.kind is SyntheticLedgerEntryKind.INITIAL_CAPITAL:
                raise ContractError("synthetic ledger currencies can have only one initial capital")
            expected = (
                previous + entry.amount.amount
                if entry.direction is LedgerDirection.CREDIT
                else previous - entry.amount.amount
            )
            if expected < 0:
                raise ContractError("synthetic ledger entries cannot overdraw a balance")
            if entry.balance_after.amount != expected:
                raise ContractError("synthetic ledger balance transition is inconsistent")
            running[currency] = expected
            latest[entry.balance_after.currency] = entry.balance_after
        if latest != {money.currency: money for money in self.balances}:
            raise ContractError("synthetic ledger balances must match latest entry balances")


@dataclass(frozen=True, slots=True)
class SyntheticPaperFillPolicy:
    policy_id: ApprovalId
    stage: Stage
    price_source: PaperFillPriceSource
    fee_model: PaperFeeModel
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    slippage_bps: Decimal
    max_fill_latency_seconds: int
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "paper fill policy evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic paper fill policies are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError("synthetic paper fill policies must be explicitly non-real-money")
        if not self.evidence_refs:
            raise ContractError("synthetic paper fill policies require evidence")
        for name in ("maker_fee_bps", "taker_fee_bps", "slippage_bps"):
            _require_decimal(getattr(self, name), name)
        if self.maker_fee_bps > 10000 or self.taker_fee_bps > 10000:
            raise ContractError("paper fee bps cannot exceed 10000")
        if self.slippage_bps > 10000:
            raise ContractError("paper slippage bps cannot exceed 10000")
        if (
            not isinstance(self.max_fill_latency_seconds, int)
            or isinstance(self.max_fill_latency_seconds, bool)
            or self.max_fill_latency_seconds < 0
        ):
            raise ContractError("max_fill_latency_seconds must be a nonnegative integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic paper fill policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticAccountSnapshot:
    account_id: AccountId
    ledger_ref: LedgerId
    stage: Stage
    as_of: datetime
    balances: tuple[Money, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.as_of, "as_of")
        for name in ("balances", "evidence_refs"):
            _require_tuple(getattr(self, name), name)
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic accounts are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError("synthetic accounts must be explicitly non-real-money")
        if not self.balances or not self.evidence_refs:
            raise ContractError("synthetic accounts require balances and evidence")
        if len({money.currency for money in self.balances}) != len(self.balances):
            raise ContractError("synthetic account balances must have unique currencies")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic accounts cannot activate orders")


@dataclass(frozen=True, slots=True)
class MarketBar:
    market: Market
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.open_time, "open_time")
        _require_utc(self.close_time, "close_time")
        if self.open_time >= self.close_time:
            raise ContractError("bar open_time must precede close_time")
        for name in ("open", "high", "low", "close"):
            _require_decimal(getattr(self, name), name, positive=True)
        _require_decimal(self.volume, "volume")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ContractError("bar OHLC values must lie between low and high")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    market: Market
    observed_at: datetime
    bid_price: Decimal
    bid_quantity: Decimal
    ask_price: Decimal
    ask_quantity: Decimal
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        for name in ("bid_price", "bid_quantity", "ask_price", "ask_quantity"):
            _require_decimal(getattr(self, name), name, positive=True)
        if self.bid_price > self.ask_price:
            raise ContractError("bid price cannot exceed ask price")


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class SignalEvent:
    signal_id: SignalId
    strategy_version_ref: StrategyVersionId
    run_ref: RunId
    instrument: InstrumentId
    timeframe: Timeframe
    observed_at: datetime
    side: Side
    rationale_code: str
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        if not self.rationale_code or not self.rationale_code.strip():
            raise ContractError("rationale_code must be non-empty")


@dataclass(frozen=True, slots=True)
class BracketLevels:
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    trailing_distance: Decimal | None = None

    def __post_init__(self) -> None:
        if self.take_profit is self.stop_loss is self.trailing_distance is None:
            raise ContractError("at least one bracket level is required")
        for name in ("take_profit", "stop_loss", "trailing_distance"):
            value = getattr(self, name)
            if value is not None:
                _require_decimal(value, name, positive=True)
        if self.trailing_distance is not None and self.trailing_distance >= 1:
            raise ContractError("trailing_distance is a percentage fraction below 1")
        if self.take_profit is not None and self.take_profit == self.stop_loss:
            raise ContractError("take-profit and stop-loss levels must differ")


def validate_bracket_levels(levels: BracketLevels, side: Side, reference_price: Decimal) -> None:
    """Validate directional bracket prices against an inert reference price."""
    _require_decimal(reference_price, "reference_price", positive=True)
    if side is Side.FLAT:
        raise ContractError("FLAT has no order bracket")
    if levels.take_profit is not None:
        valid_take_profit = (
            levels.take_profit > reference_price
            if side is Side.BUY
            else levels.take_profit < reference_price
        )
        if not valid_take_profit:
            raise ContractError("take-profit level is on the wrong side of the reference price")
    if levels.stop_loss is not None:
        valid_stop_loss = (
            levels.stop_loss < reference_price
            if side is Side.BUY
            else levels.stop_loss > reference_price
        )
        if not valid_stop_loss:
            raise ContractError("stop-loss level is on the wrong side of the reference price")


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    source_signal_ref: SignalId | None
    run_ref: RunId
    instrument: InstrumentId
    side: Side
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    bracket_levels: BracketLevels | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        if self.side is Side.FLAT:
            raise ContractError("an order intent side must be BUY or SELL")
        _require_decimal(self.quantity, "quantity", positive=True)
        if self.limit_price is not None:
            _require_decimal(self.limit_price, "limit_price", positive=True)
        if self.stop_price is not None:
            _require_decimal(self.stop_price, "stop_price", positive=True)
        required = {
            OrderType.MARKET: (False, False),
            OrderType.LIMIT: (True, False),
            OrderType.STOP: (False, True),
            OrderType.STOP_LIMIT: (True, True),
        }[self.order_type]
        if (self.limit_price is not None, self.stop_price is not None) != required:
            raise ContractError(f"invalid price fields for {self.order_type}")
        reference_price = self.limit_price or self.stop_price
        if self.bracket_levels is not None and reference_price is not None:
            validate_bracket_levels(self.bracket_levels, self.side, reference_price)


class LiquidityRole(StrEnum):
    MAKER = "MAKER"
    TAKER = "TAKER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FillEvent:
    fill_id: FillId
    order_ref: OrderId
    run_ref: RunId
    instrument: InstrumentId
    filled_at: datetime
    price: Decimal
    quantity: Decimal
    fee: Money
    liquidity_role: LiquidityRole | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.filled_at, "filled_at")
        _require_decimal(self.price, "price", positive=True)
        _require_decimal(self.quantity, "quantity", positive=True)
        if self.fee.currency != self.instrument.quote_currency:
            raise ContractError("fill fee currency must match the instrument quote currency")


class OrderStatus(StrEnum):
    INERT = "INERT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.INERT: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED}
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
}
TERMINAL_ORDER_STATES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}
)


def validate_order_transition(current: OrderStatus, target: OrderStatus) -> None:
    """Raise unless a retained order snapshot may follow another snapshot."""
    if target not in _ORDER_TRANSITIONS[current]:
        raise ContractError(f"invalid order transition: {current} -> {target}")


@dataclass(frozen=True, slots=True)
class OrderState:
    order_id: OrderId
    intent: OrderIntent
    observed_at: datetime
    state: OrderStatus
    fills: tuple[FillEvent, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.observed_at, "observed_at")
        _require_tuple(self.fills, "fills")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("S2 order capabilities must remain disabled")
        if len({fill.fill_id for fill in self.fills}) != len(self.fills):
            raise ContractError("fill ids must be unique within an order history")
        for fill in self.fills:
            if (
                fill.order_ref != self.order_id
                or fill.run_ref != self.intent.run_ref
                or fill.instrument != self.intent.instrument
                or fill.filled_at > self.observed_at
            ):
                raise ContractError("fill context or timestamp does not match the order snapshot")
        quantity = self.filled_quantity
        if quantity > self.intent.quantity:
            raise ContractError("aggregate fill quantity exceeds order quantity")
        if self.state is OrderStatus.INERT and quantity != 0:
            raise ContractError("an INERT order cannot contain fills")
        if self.state is OrderStatus.PARTIALLY_FILLED and not (0 < quantity < self.intent.quantity):
            raise ContractError("PARTIALLY_FILLED requires a partial aggregate quantity")
        if self.state is OrderStatus.FILLED and quantity != self.intent.quantity:
            raise ContractError("FILLED requires the exact order quantity")
        if self.state is OrderStatus.REJECTED and quantity != 0:
            raise ContractError("a rejected order cannot contain fills")

    @property
    def filled_quantity(self) -> Decimal:
        return sum((fill.quantity for fill in self.fills), Decimal(0))

    @property
    def average_fill_price(self) -> Decimal | None:
        if not self.fills:
            return None
        notional = sum((fill.price * fill.quantity for fill in self.fills), Decimal(0))
        return notional / self.filled_quantity

    @property
    def total_fee(self) -> Money:
        amount = sum((fill.fee.amount for fill in self.fills), Decimal(0))
        return Money(amount, self.intent.instrument.quote_currency)


def aggregate_fills(
    snapshot: OrderState,
    fills: tuple[FillEvent, ...],
    *,
    observed_at: datetime,
    event_cursor: int,
) -> OrderState:
    """Return the next inert snapshot from newly retained historical fills."""
    _require_tuple(fills, "fills")
    if not fills:
        raise ContractError("at least one new fill is required")
    if snapshot.state in TERMINAL_ORDER_STATES:
        raise ContractError("terminal order states reject additional fills")
    _require_utc(observed_at, "observed_at")
    if observed_at < snapshot.observed_at or event_cursor <= snapshot.event_cursor:
        raise ContractError("order projection time and cursor must advance")
    combined = snapshot.fills + fills
    quantity = sum((fill.quantity for fill in combined), Decimal(0))
    next_state = (
        OrderStatus.FILLED if quantity == snapshot.intent.quantity else OrderStatus.PARTIALLY_FILLED
    )
    return replace(
        snapshot,
        observed_at=observed_at,
        state=next_state,
        fills=combined,
        event_cursor=event_cursor,
        created_at=observed_at,
    )


class PositionStatus(StrEnum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    position_id: PositionId
    run_ref: RunId
    instrument: InstrumentId
    as_of: datetime
    quantity: Decimal
    average_price: Decimal | None
    realized_pnl: SignedMoney
    unrealized_pnl: SignedMoney
    status: PositionStatus
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_decimal(self.quantity, "quantity")
        if self.average_price is not None:
            _require_decimal(self.average_price, "average_price", positive=True)
        currency = self.instrument.quote_currency
        if self.realized_pnl.currency != currency or self.unrealized_pnl.currency != currency:
            raise ContractError("position money must use the instrument quote currency")
        if self.status is PositionStatus.OPEN and (
            self.quantity == 0 or self.average_price is None
        ):
            raise ContractError("an open position requires quantity and average price")
        if self.status is not PositionStatus.OPEN and self.quantity != 0:
            raise ContractError("flat and closed positions must have zero quantity")
        if self.status is PositionStatus.FLAT and self.average_price is not None:
            raise ContractError("a flat position cannot have an average price")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: AccountId
    run_ref: RunId
    as_of: datetime
    balances: tuple[Money, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    synthetic: bool = False

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_tuple(self.balances, "balances")
        if self.synthetic is not False:
            raise ContractError("synthetic wallets do not exist in S2")
        if len({money.currency for money in self.balances}) != len(self.balances):
            raise ContractError("account balances must have unique currencies")
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    portfolio_id: PortfolioId
    account_ref: AccountId
    run_ref: RunId
    as_of: datetime
    reporting_currency: str
    cash: tuple[Money, ...]
    positions: tuple[PositionSnapshot, ...]
    equity: tuple[Money, ...]
    event_cursor: int
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        if not isinstance(self.reporting_currency, str) or not _CURRENCY.fullmatch(
            self.reporting_currency
        ):
            raise ContractError("reporting_currency must be an uppercase currency code")
        for name in ("cash", "positions", "equity"):
            _require_tuple(getattr(self, name), name)
        money = (
            self.cash
            + self.equity
            + tuple(
                item
                for position in self.positions
                for item in (position.realized_pnl, position.unrealized_pnl)
            )
        )
        if any(item.currency != self.reporting_currency for item in money):
            raise ContractError("all portfolio money must use the reporting currency")
        if any(
            position.run_ref != self.run_ref
            or position.instrument.quote_currency != self.reporting_currency
            or position.as_of > self.as_of
            for position in self.positions
        ):
            raise ContractError(
                "portfolio positions must share its run, time, and currency context"
            )
        if not isinstance(self.event_cursor, int) or isinstance(self.event_cursor, bool):
            raise ContractError("event_cursor must be a nonnegative integer")
        if self.event_cursor < 0:
            raise ContractError("event_cursor must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class SyntheticPortfolioSnapshot:
    portfolio_id: PortfolioId
    account_ref: AccountId
    ledger_ref: LedgerId
    stage: Stage
    as_of: datetime
    reporting_currency: str
    cash: tuple[Money, ...]
    positions: tuple[PositionSnapshot, ...]
    equity: tuple[Money, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.as_of, "as_of")
        if not isinstance(self.reporting_currency, str) or not _CURRENCY.fullmatch(
            self.reporting_currency
        ):
            raise ContractError("reporting_currency must be an uppercase currency code")
        for name in ("cash", "positions", "equity", "evidence_refs"):
            _require_tuple(getattr(self, name), name)
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic portfolios are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError("synthetic portfolios must be explicitly non-real-money")
        if not self.evidence_refs:
            raise ContractError("synthetic portfolios require evidence")
        money = (
            self.cash
            + self.equity
            + tuple(
                item
                for position in self.positions
                for item in (position.realized_pnl, position.unrealized_pnl)
            )
        )
        if any(item.currency != self.reporting_currency for item in money):
            raise ContractError("all synthetic portfolio money must use the reporting currency")
        if any(
            position.instrument.quote_currency != self.reporting_currency
            or position.as_of > self.as_of
            for position in self.positions
        ):
            raise ContractError(
                "synthetic portfolio positions must share its time and currency context"
            )
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic portfolios cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticRuntimeRiskPolicy:
    policy_id: RiskId
    stage: Stage
    strategy_context_ref: DomainRef
    portfolio_ref: PortfolioId
    max_capital_at_risk: Money
    max_position_notional: Money
    max_daily_loss: Money
    max_drawdown_fraction: Decimal
    kill_switch_mode: KillSwitchMode
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "runtime risk policy evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic runtime risk policies are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError("synthetic runtime risk policies must be explicitly non-real-money")
        if not self.evidence_refs:
            raise ContractError("synthetic runtime risk policies require evidence")
        currency = self.max_capital_at_risk.currency
        if (
            self.max_position_notional.currency != currency
            or self.max_daily_loss.currency != currency
        ):
            raise ContractError("runtime risk money limits must use one currency")
        for name in ("max_capital_at_risk", "max_position_notional", "max_daily_loss"):
            _require_decimal(getattr(self, name).amount, name, positive=True)
        _require_decimal(self.max_drawdown_fraction, "max_drawdown_fraction", positive=True)
        if self.max_drawdown_fraction >= 1:
            raise ContractError("max_drawdown_fraction must be below 1")
        if self.max_position_notional.amount > self.max_capital_at_risk.amount:
            raise ContractError("max_position_notional cannot exceed max_capital_at_risk")
        if self.max_daily_loss.amount > self.max_capital_at_risk.amount:
            raise ContractError("max_daily_loss cannot exceed max_capital_at_risk")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic runtime risk policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticPortfolioRiskPolicy:
    policy_id: RiskId
    stage: Stage
    portfolio_ref: PortfolioId
    max_symbol_concentration_fraction: Decimal
    max_correlated_exposure_fraction: Decimal
    max_strategy_budget_fraction: Decimal
    max_open_positions: int
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "portfolio risk policy evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic portfolio risk policies are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError(
                "synthetic portfolio risk policies must be explicitly non-real-money"
            )
        if not self.evidence_refs:
            raise ContractError("synthetic portfolio risk policies require evidence")
        for name in (
            "max_symbol_concentration_fraction",
            "max_correlated_exposure_fraction",
            "max_strategy_budget_fraction",
        ):
            value = getattr(self, name)
            _require_decimal(value, name, positive=True)
            if value > 1:
                raise ContractError(f"{name} must be at most 1")
        if (
            not isinstance(self.max_open_positions, int)
            or isinstance(self.max_open_positions, bool)
            or self.max_open_positions <= 0
        ):
            raise ContractError("max_open_positions must be a positive integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic portfolio risk policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticStrategyBudgetPolicy:
    policy_id: RiskId
    stage: Stage
    strategy_context_ref: DomainRef
    portfolio_ref: PortfolioId
    max_portfolio_fraction: Decimal
    max_notional: Money
    max_daily_loss: Money
    max_open_positions: int
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "strategy budget policy evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("synthetic strategy budget policies are reserved for S3 paper/demo")
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError(
                "synthetic strategy budget policies must be explicitly non-real-money"
            )
        if not self.evidence_refs:
            raise ContractError("synthetic strategy budget policies require evidence")
        _require_decimal(self.max_portfolio_fraction, "max_portfolio_fraction", positive=True)
        if self.max_portfolio_fraction > 1:
            raise ContractError("max_portfolio_fraction must be at most 1")
        if self.max_notional.currency != self.max_daily_loss.currency:
            raise ContractError("strategy budget money limits must use one currency")
        _require_decimal(self.max_notional.amount, "max_notional", positive=True)
        _require_decimal(self.max_daily_loss.amount, "max_daily_loss", positive=True)
        if self.max_daily_loss.amount > self.max_notional.amount:
            raise ContractError("max_daily_loss cannot exceed max_notional")
        if (
            not isinstance(self.max_open_positions, int)
            or isinstance(self.max_open_positions, bool)
            or self.max_open_positions <= 0
        ):
            raise ContractError("max_open_positions must be a positive integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic strategy budget policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class SyntheticMarketConditionPolicy:
    policy_id: RiskId
    stage: Stage
    strategy_context_ref: DomainRef
    max_market_data_age_seconds: int
    max_quote_spread_bps: Decimal
    block_when_venue_health_degraded: bool
    require_monotonic_timestamps: bool
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    synthetic: bool = True
    real_money: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "market condition policy evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError(
                "synthetic market condition policies are reserved for S3 paper/demo"
            )
        if self.synthetic is not True or self.real_money is not False:
            raise ContractError(
                "synthetic market condition policies must be explicitly non-real-money"
            )
        if not self.evidence_refs:
            raise ContractError("synthetic market condition policies require evidence")
        if (
            not isinstance(self.max_market_data_age_seconds, int)
            or isinstance(self.max_market_data_age_seconds, bool)
            or self.max_market_data_age_seconds <= 0
        ):
            raise ContractError("max_market_data_age_seconds must be a positive integer")
        _require_decimal(self.max_quote_spread_bps, "max_quote_spread_bps", positive=True)
        if (
            self.block_when_venue_health_degraded is not True
            or self.require_monotonic_timestamps is not True
        ):
            raise ContractError("synthetic market condition policies must fail closed")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("synthetic market condition policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class RestrictedCredentialPolicy:
    policy_id: ApprovalId
    stage: Stage
    venue_family: VenueFamily
    allowed_future_permissions: tuple[CredentialPermission, ...]
    max_order_notional: Money
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    credential_material_present: bool = False
    outbound_funds_allowed: bool = False
    transfers_allowed: bool = False
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.allowed_future_permissions, "allowed_future_permissions")
        _require_tuple(self.evidence_refs, "credential policy evidence_refs")
        if self.stage is not Stage.S4_LIVE:
            raise ContractError("restricted credential policies are reserved for S4 live gates")
        if not self.allowed_future_permissions or not self.evidence_refs:
            raise ContractError("restricted credential policies require permissions and evidence")
        if len(set(self.allowed_future_permissions)) != len(self.allowed_future_permissions):
            raise ContractError("restricted credential permissions must be unique")
        forbidden = {
            CredentialPermission.FUNDS_OUT,
            CredentialPermission.TRANSFER_FUNDS,
        }
        if any(permission in forbidden for permission in self.allowed_future_permissions):
            raise ContractError("restricted credential policies cannot allow funds movement")
        if (
            self.credential_material_present is not False
            or self.outbound_funds_allowed is not False
            or self.transfers_allowed is not False
        ):
            raise ContractError("restricted credential policies cannot contain credential grants")
        _require_decimal(self.max_order_notional.amount, "max_order_notional", positive=True)
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("restricted credential policies cannot activate orders")


@dataclass(frozen=True, slots=True)
class PaperOperationsRunbook:
    runbook_id: ApprovalId
    stage: Stage
    paper_lane_ref: ApprovalId
    runtime_risk_policy_ref: RiskId
    heartbeat_interval_seconds: int
    heartbeat_timeout_seconds: int
    log_retention_days: int
    intervention_mode: PaperRunbookInterventionMode
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "paper operations runbook evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("paper operations runbooks are reserved for S3 paper/demo")
        if not self.evidence_refs:
            raise ContractError("paper operations runbooks require evidence")
        for name in (
            "heartbeat_interval_seconds",
            "heartbeat_timeout_seconds",
            "log_retention_days",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ContractError(f"{name} must be a positive integer")
        if self.heartbeat_timeout_seconds < self.heartbeat_interval_seconds:
            raise ContractError("heartbeat timeout must be at least the heartbeat interval")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("paper operations runbooks cannot activate orders")


@dataclass(frozen=True, slots=True)
class PaperOperationsEventRecord:
    event_id: ApprovalId
    stage: Stage
    runbook_ref: ApprovalId
    occurred_at: datetime
    kind: PaperOperationsEventKind
    severity: PaperOperationsEventSeverity
    detail: str
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.occurred_at, "occurred_at")
        _require_tuple(self.evidence_refs, "paper operations event evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("paper operations events are reserved for S3 paper/demo")
        if not self.detail.strip():
            raise ContractError("paper operations event detail must be non-empty")
        if not self.evidence_refs:
            raise ContractError("paper operations events require evidence")
        if self.occurred_at > self.created_at:
            raise ContractError("paper operations events cannot occur after creation")
        if (
            self.kind
            in (
                PaperOperationsEventKind.HEARTBEAT_MISSED,
                PaperOperationsEventKind.KILL_SWITCH_OBSERVED,
            )
            and self.severity is PaperOperationsEventSeverity.INFO
        ):
            raise ContractError("risk-relevant operations events cannot be INFO")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("paper operations events cannot activate orders")


@dataclass(frozen=True, slots=True)
class PaperStabilityReport:
    report_id: ApprovalId
    stage: Stage
    paper_lane_ref: ApprovalId
    divergence_report_ref: ApprovalId
    runbook_ref: ApprovalId
    runtime_risk_policy_ref: RiskId
    window_started_at: datetime
    window_ended_at: datetime
    required_observation_hours: Decimal
    observed_uptime_fraction: Decimal
    incident_count: int
    missed_heartbeat_count: int
    status: PaperStabilityStatus
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    blocker: str | None = None
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.window_started_at, "window_started_at")
        _require_utc(self.window_ended_at, "window_ended_at")
        _require_tuple(self.evidence_refs, "paper stability evidence_refs")
        if self.stage is not Stage.S3_PAPER_DEMO:
            raise ContractError("paper stability reports are reserved for S3 paper/demo")
        if self.window_started_at >= self.window_ended_at:
            raise ContractError("paper stability window start must precede end")
        if not self.evidence_refs:
            raise ContractError("paper stability reports require evidence")
        _require_decimal(
            self.required_observation_hours, "required_observation_hours", positive=True
        )
        _require_decimal(self.observed_uptime_fraction, "observed_uptime_fraction")
        if not 0 <= self.observed_uptime_fraction <= 1:
            raise ContractError("observed_uptime_fraction must be between 0 and 1")
        for name in ("incident_count", "missed_heartbeat_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ContractError(f"{name} must be a nonnegative integer")
        if self.status is PaperStabilityStatus.BLOCKED:
            if not self.blocker or not self.blocker.strip():
                raise ContractError("blocked paper stability reports require a blocker")
        elif self.blocker is not None:
            raise ContractError("non-blocked paper stability reports cannot carry a blocker")
        if self.status is PaperStabilityStatus.PASS and (
            self.incident_count != 0 or self.missed_heartbeat_count != 0
        ):
            raise ContractError("passing paper stability reports require zero incidents")
        observed_hours = Decimal(
            str((self.window_ended_at - self.window_started_at).total_seconds() / 3600)
        )
        if self.status is PaperStabilityStatus.PASS and (
            observed_hours < self.required_observation_hours or self.observed_uptime_fraction != 1
        ):
            raise ContractError(
                "passing paper stability reports must meet the observation window and uptime"
            )
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("paper stability reports cannot activate orders")


@dataclass(frozen=True, slots=True)
class LimitedLiveRiskPackage:
    package_id: ApprovalId
    stage: Stage
    paper_stability_ref: ApprovalId
    credential_policy_ref: ApprovalId
    operations_runbook_ref: ApprovalId
    runtime_risk_policy_ref: RiskId
    maximum_capital_at_risk: Money
    maximum_single_order_notional: Money
    maximum_daily_loss: Money
    kill_switch_mode: KillSwitchMode
    status: LimitedLiveRiskPackageStatus
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    blocker: str | None = None
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "limited live risk package evidence_refs")
        if self.stage is not Stage.S4_LIVE:
            raise ContractError("limited live risk packages are reserved for S4")
        if not self.evidence_refs:
            raise ContractError("limited live risk packages require evidence")
        currency = self.maximum_capital_at_risk.currency
        if (
            self.maximum_single_order_notional.currency != currency
            or self.maximum_daily_loss.currency != currency
        ):
            raise ContractError("limited live risk package money limits must use one currency")
        for name in (
            "maximum_capital_at_risk",
            "maximum_single_order_notional",
            "maximum_daily_loss",
        ):
            _require_decimal(getattr(self, name).amount, name, positive=True)
        if self.maximum_single_order_notional.amount > self.maximum_capital_at_risk.amount:
            raise ContractError("maximum_single_order_notional cannot exceed capital at risk")
        if self.maximum_daily_loss.amount > self.maximum_capital_at_risk.amount:
            raise ContractError("maximum_daily_loss cannot exceed capital at risk")
        if self.status is LimitedLiveRiskPackageStatus.BLOCKED:
            if not self.blocker or not self.blocker.strip():
                raise ContractError("blocked limited live risk packages require a blocker")
        elif self.blocker is not None:
            raise ContractError("non-blocked limited live risk packages cannot carry a blocker")
        if (
            self.status is LimitedLiveRiskPackageStatus.READY_FOR_OPERATOR_DECISION
            and self.kill_switch_mode is not KillSwitchMode.MANUAL_REQUIRED
        ):
            raise ContractError(
                "live risk packages require an operator-manual kill switch before review"
            )
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("limited live risk packages cannot activate orders")


@dataclass(frozen=True, slots=True)
class LiveOperationsRunbook:
    runbook_id: ApprovalId
    stage: Stage
    limited_live_risk_package_ref: ApprovalId
    credential_policy_ref: ApprovalId
    heartbeat_interval_seconds: int
    incident_response_minutes: int
    log_retention_days: int
    escalation_mode: LiveRunbookEscalationMode
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_tuple(self.evidence_refs, "live operations runbook evidence_refs")
        if self.stage is not Stage.S4_LIVE:
            raise ContractError("live operations runbooks are reserved for S4")
        if not self.evidence_refs:
            raise ContractError("live operations runbooks require evidence")
        for name in (
            "heartbeat_interval_seconds",
            "incident_response_minutes",
            "log_retention_days",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ContractError(f"{name} must be a positive integer")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("live operations runbooks cannot activate orders")


@dataclass(frozen=True, slots=True)
class LiveOperationsEventRecord:
    event_id: ApprovalId
    stage: Stage
    runbook_ref: ApprovalId
    limited_live_risk_package_ref: ApprovalId
    occurred_at: datetime
    kind: LiveOperationsEventKind
    severity: LiveOperationsEventSeverity
    detail: str
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.occurred_at, "occurred_at")
        _require_tuple(self.evidence_refs, "live operations event evidence_refs")
        if self.stage is not Stage.S4_LIVE:
            raise ContractError("live operations events are reserved for S4")
        if not self.detail.strip():
            raise ContractError("live operations event detail must be non-empty")
        if not self.evidence_refs:
            raise ContractError("live operations events require evidence")
        if self.occurred_at > self.created_at:
            raise ContractError("live operations events cannot occur after creation")
        if (
            self.kind
            in (
                LiveOperationsEventKind.HEARTBEAT_MISSED,
                LiveOperationsEventKind.RISK_LIMIT_BREACH,
                LiveOperationsEventKind.KILL_SWITCH_OBSERVED,
                LiveOperationsEventKind.ESCALATION_RECORDED,
            )
            and self.severity is LiveOperationsEventSeverity.INFO
        ):
            raise ContractError("risk-relevant live operations events cannot be INFO")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("live operations events cannot activate orders")


@dataclass(frozen=True, slots=True)
class OperationalIncidentRecord:
    incident_id: ApprovalId
    stage: Stage
    status: OperationalIncidentStatus
    severity: OperationalIncidentSeverity
    opened_at: datetime
    summary: str
    event_refs: tuple[ApprovalId, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    owner_ref: DomainRef | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_summary: str | None = None
    post_incident_ref: DomainRef | None = None
    schema_version: int = 1
    execution_authority: ExecutionAuthority = ExecutionAuthority.NONE
    venue_connection: VenueConnection = VenueConnection.NONE
    paper_orders: OrderCapability = OrderCapability.DISABLED
    live_orders: OrderCapability = OrderCapability.DISABLED

    def __post_init__(self) -> None:
        _validate_control_plane_record(self.schema_version, self.created_at, self.provenance)
        _require_utc(self.opened_at, "incident opened_at")
        _require_tuple(self.event_refs, "incident event_refs")
        _require_tuple(self.evidence_refs, "incident evidence_refs")
        if self.stage not in (Stage.S3_PAPER_DEMO, Stage.S4_LIVE):
            raise ContractError("operational incidents are reserved for S3/S4")
        if not self.summary.strip() or not self.event_refs or not self.evidence_refs:
            raise ContractError("operational incidents require summary, events, and evidence")
        if len(set(self.event_refs)) != len(self.event_refs):
            raise ContractError("operational incident event references must be unique")
        if self.status is OperationalIncidentStatus.OPEN:
            if any(
                value is not None
                for value in (
                    self.owner_ref,
                    self.acknowledged_at,
                    self.resolved_at,
                    self.resolution_summary,
                    self.post_incident_ref,
                )
            ):
                raise ContractError("open incidents cannot carry acknowledgement or resolution")
        else:
            if self.owner_ref is None or self.acknowledged_at is None:
                raise ContractError("acknowledged incidents require owner and timestamp")
            _require_utc(self.acknowledged_at, "incident acknowledged_at")
            if self.acknowledged_at < self.opened_at:
                raise ContractError("incident acknowledgement cannot precede opening")
        if self.status is OperationalIncidentStatus.ACKNOWLEDGED:
            if any(
                value is not None
                for value in (self.resolved_at, self.resolution_summary, self.post_incident_ref)
            ):
                raise ContractError("acknowledged incidents cannot carry resolution")
        if self.status is OperationalIncidentStatus.RESOLVED:
            if (
                self.resolved_at is None
                or not self.resolution_summary
                or not self.resolution_summary.strip()
                or self.post_incident_ref is None
            ):
                raise ContractError(
                    "resolved incidents require resolution and post-incident evidence"
                )
            _require_utc(self.resolved_at, "incident resolved_at")
            assert self.acknowledged_at is not None
            if self.resolved_at < self.acknowledged_at:
                raise ContractError("incident resolution cannot precede acknowledgement")
        if (
            self.execution_authority is not ExecutionAuthority.NONE
            or self.venue_connection is not VenueConnection.NONE
            or self.paper_orders is not OrderCapability.DISABLED
            or self.live_orders is not OrderCapability.DISABLED
        ):
            raise ContractError("operational incidents cannot activate orders")


def advance_operational_incident(
    incident: OperationalIncidentRecord,
    target: OperationalIncidentStatus,
    *,
    at: datetime,
    owner_ref: DomainRef,
    evidence_ref: DomainRef,
    resolution_summary: str | None = None,
    post_incident_ref: DomainRef | None = None,
) -> OperationalIncidentRecord:
    """Advance the immutable incident lifecycle by exactly one valid transition."""
    allowed = {
        OperationalIncidentStatus.OPEN: OperationalIncidentStatus.ACKNOWLEDGED,
        OperationalIncidentStatus.ACKNOWLEDGED: OperationalIncidentStatus.RESOLVED,
    }
    if allowed.get(incident.status) is not target:
        raise ContractError(
            f"invalid operational incident transition: {incident.status} -> {target}"
        )
    if target is OperationalIncidentStatus.ACKNOWLEDGED:
        return replace(
            incident,
            status=target,
            owner_ref=owner_ref,
            acknowledged_at=at,
            evidence_refs=tuple(dict.fromkeys(incident.evidence_refs + (evidence_ref,))),
            created_at=at,
        )
    return replace(
        incident,
        status=target,
        owner_ref=owner_ref,
        resolved_at=at,
        resolution_summary=resolution_summary,
        post_incident_ref=post_incident_ref,
        evidence_refs=tuple(dict.fromkeys(incident.evidence_refs + (evidence_ref,))),
        created_at=at,
    )


class RiskOutcome(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class RiskCheck:
    rule_code: str
    outcome: RiskOutcome
    evidence_refs: tuple[DomainRef, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        if not self.rule_code or not self.rule_code.strip():
            raise ContractError("risk rule_code must be non-empty")
        _require_tuple(self.evidence_refs, "risk check evidence_refs")
        if self.outcome is not RiskOutcome.NOT_EVALUATED and not self.evidence_refs:
            raise ContractError("evaluated risk checks require evidence")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_id: RiskId
    subject_ref: DomainRef
    as_of: datetime
    decision: RiskOutcome
    rule_results: tuple[RiskCheck, ...]
    evidence_refs: tuple[DomainRef, ...]
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH
    independent: bool = True

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.as_of, "as_of")
        _require_tuple(self.rule_results, "rule_results")
        _require_tuple(self.evidence_refs, "evidence_refs")
        if self.independent is not True:
            raise ContractError("risk decisions must remain independent")
        expected = RiskOutcome.NOT_EVALUATED
        if self.rule_results:
            if any(check.outcome is RiskOutcome.BLOCK for check in self.rule_results):
                expected = RiskOutcome.BLOCK
            elif all(check.outcome is RiskOutcome.PASS for check in self.rule_results):
                expected = RiskOutcome.PASS
        if self.decision is not expected:
            raise ContractError("risk decision must equal its independent rule outcomes")


class ApprovalState(StrEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    RESEARCH = "RESEARCH"
    VALIDATION = "VALIDATION"


class ApprovalDecision(StrEnum):
    NONE = "NONE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: ApprovalId
    strategy_version_ref: StrategyVersionId
    market: Market
    current_state: ApprovalState
    proposed_target: ApprovalState | None
    evidence_refs: tuple[DomainRef, ...]
    validation_refs: tuple[DomainRef, ...]
    risk_refs: tuple[RiskId, ...]
    decision: ApprovalDecision
    decided_by: DomainRef | None
    decided_at: datetime | None
    review_rule: str
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        for name in ("evidence_refs", "validation_refs", "risk_refs"):
            _require_tuple(getattr(self, name), name)
        if not self.review_rule or not self.review_rule.strip():
            raise ContractError("review_rule must be non-empty")
        decided = self.decision is not ApprovalDecision.NONE
        if decided != (self.decided_by is not None and self.decided_at is not None):
            raise ContractError("recorded decisions require both decider and UTC decision time")
        if self.decided_at is not None:
            _require_utc(self.decided_at, "decided_at")


class AnnotationKind(StrEnum):
    SIGNAL = "SIGNAL"
    FILL = "FILL"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True, slots=True)
class ChartAnnotation:
    annotation_id: AnnotationId
    chart_ref: str
    instrument: InstrumentId
    timeframe: Timeframe
    timestamp: datetime
    kind: AnnotationKind
    source_ref: DomainRef
    price: Decimal | None
    label: str | None
    created_at: datetime
    creator_type: CreatorType
    provenance: Provenance
    schema_version: int = 1
    environment: Environment = Environment.HISTORICAL_RESEARCH

    def __post_init__(self) -> None:
        _validate_record(self.schema_version, self.created_at, self.provenance, self.environment)
        _require_utc(self.timestamp, "timestamp")
        if not self.chart_ref or not self.chart_ref.strip():
            raise ContractError("chart_ref must be non-empty")
        if self.price is not None:
            _require_decimal(self.price, "price", positive=True)
        expected_prefix = {
            AnnotationKind.SIGNAL: "SIG-",
            AnnotationKind.FILL: "FILL-",
            AnnotationKind.TAKE_PROFIT: "ORD-",
            AnnotationKind.STOP_LOSS: "ORD-",
        }[self.kind]
        if self.source_ref.prefix != expected_prefix:
            raise ContractError("annotation kind must match its retained typed source")
