"""Pure, non-executing risk evaluation for future synthetic paper state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import (
    ApprovalId,
    ContractError,
    CreatorType,
    DomainRef,
    KillSwitchMode,
    LimitedLiveRiskPackage,
    LimitedLiveRiskPackageStatus,
    Money,
    OperationalDrillKind,
    OperationalDrillRecord,
    OperationalDrillStatus,
    PaperOperationsRunbook,
    PaperRunbookInterventionMode,
    PaperStabilityReport,
    PaperStabilityStatus,
    Provenance,
    RestrictedCredentialPolicy,
    RiskCheck,
    RiskDecision,
    RiskId,
    RiskOutcome,
    SyntheticMarketConditionPolicy,
    SyntheticPortfolioRiskPolicy,
    SyntheticRuntimeRiskPolicy,
    SyntheticStrategyBudgetPolicy,
)


@dataclass(frozen=True, slots=True)
class SyntheticRiskInputs:
    proposed_notional: Money
    capital_at_risk: Money
    daily_loss: Money
    drawdown_fraction: Decimal
    symbol_concentration_fraction: Decimal
    correlated_exposure_fraction: Decimal
    strategy_budget_fraction: Decimal
    open_positions: int
    market_data_age_seconds: int
    quote_spread_bps: Decimal
    venue_health_degraded: bool = False
    timestamps_monotonic: bool = True
    kill_switch_triggered: bool = False


@dataclass(frozen=True, slots=True)
class LimitedLiveReadinessValidation:
    package_ref: ApprovalId
    ready: bool
    blockers: tuple[str, ...]


def validate_limited_live_readiness(
    *,
    package: LimitedLiveRiskPackage,
    stability: PaperStabilityReport,
    credential_policy: RestrictedCredentialPolicy,
    operations_runbook: PaperOperationsRunbook,
    runtime_policy: SyntheticRuntimeRiskPolicy,
    drills: tuple[OperationalDrillRecord, ...],
) -> LimitedLiveReadinessValidation:
    """Resolve the future limited-live evidence graph without activating capability."""
    blockers: list[str] = []
    if package.status is not LimitedLiveRiskPackageStatus.READY_FOR_OPERATOR_DECISION:
        blockers.append("risk package is not ready for operator decision")
    references = {
        "paper stability": package.paper_stability_ref == stability.report_id,
        "credential policy": package.credential_policy_ref == credential_policy.policy_id,
        "operations runbook": package.operations_runbook_ref == operations_runbook.runbook_id,
        "runtime risk policy": package.runtime_risk_policy_ref == runtime_policy.policy_id,
    }
    blockers.extend(
        f"{name} reference does not resolve" for name, valid in references.items() if not valid
    )
    if stability.status is not PaperStabilityStatus.PASS:
        blockers.append("paper stability has not passed")
    if operations_runbook.paper_lane_ref != stability.paper_lane_ref:
        blockers.append("operations runbook and stability report use different paper lanes")
    if operations_runbook.runtime_risk_policy_ref != runtime_policy.policy_id:
        blockers.append("operations runbook runtime risk reference does not resolve")
    if package.kill_switch_mode is not KillSwitchMode.MANUAL_REQUIRED:
        blockers.append("limited-live package lacks an operator-manual kill switch")
    if runtime_policy.kill_switch_mode is not KillSwitchMode.MANUAL_REQUIRED:
        blockers.append("runtime policy lacks an operator-manual kill switch")
    if operations_runbook.intervention_mode is not PaperRunbookInterventionMode.MANUAL_ONLY:
        blockers.append("paper operations runbook is not manual-intervention capable")
    if package.maximum_single_order_notional.amount > credential_policy.max_order_notional.amount:
        blockers.append("single-order limit exceeds credential policy")
    if package.maximum_capital_at_risk.amount > runtime_policy.max_capital_at_risk.amount:
        blockers.append("capital-at-risk exceeds runtime policy")
    if package.maximum_single_order_notional.amount > runtime_policy.max_position_notional.amount:
        blockers.append("single-order limit exceeds runtime position policy")
    if package.maximum_daily_loss.amount > runtime_policy.max_daily_loss.amount:
        blockers.append("daily-loss limit exceeds runtime policy")
    required_drills = {
        OperationalDrillKind.FEED_LOSS,
        OperationalDrillKind.STALE_DATA,
        OperationalDrillKind.ENGINE_CRASH,
        OperationalDrillKind.MANUAL_KILL_SWITCH,
        OperationalDrillKind.CREDENTIAL_REVOCATION,
    }
    passed_drills = {drill.kind for drill in drills if drill.status is OperationalDrillStatus.PASS}
    blockers.extend(
        f"required drill has not passed: {kind.value}"
        for kind in sorted(required_drills - passed_drills, key=lambda item: item.value)
    )
    return LimitedLiveReadinessValidation(package.package_id, not blockers, tuple(blockers))


def evaluate_synthetic_risk(
    *,
    risk_id: RiskId,
    subject_ref: DomainRef,
    as_of: datetime,
    runtime_policy: SyntheticRuntimeRiskPolicy,
    portfolio_policy: SyntheticPortfolioRiskPolicy,
    strategy_budget: SyntheticStrategyBudgetPolicy,
    market_policy: SyntheticMarketConditionPolicy,
    inputs: SyntheticRiskInputs,
    evidence_refs: tuple[DomainRef, ...],
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> RiskDecision:
    """Evaluate every independent synthetic risk guard without routing an order."""
    if not evidence_refs:
        raise ContractError("synthetic risk evaluation requires evidence")
    if not (
        runtime_policy.strategy_context_ref
        == strategy_budget.strategy_context_ref
        == market_policy.strategy_context_ref
        == subject_ref
    ):
        raise ContractError("synthetic risk policies must share the strategy context")
    if not (
        runtime_policy.portfolio_ref
        == portfolio_policy.portfolio_ref
        == strategy_budget.portfolio_ref
    ):
        raise ContractError("synthetic risk policies must share the portfolio")
    currency = runtime_policy.max_capital_at_risk.currency
    money = (inputs.proposed_notional, inputs.capital_at_risk, inputs.daily_loss)
    if any(item.currency != currency for item in money):
        raise ContractError("synthetic risk inputs must use the policy currency")
    numeric = (
        inputs.proposed_notional.amount,
        inputs.capital_at_risk.amount,
        inputs.daily_loss.amount,
        inputs.drawdown_fraction,
        inputs.symbol_concentration_fraction,
        inputs.correlated_exposure_fraction,
        inputs.strategy_budget_fraction,
        inputs.quote_spread_bps,
    )
    if any(value < 0 or not value.is_finite() for value in numeric):
        raise ContractError("synthetic risk inputs must be finite and nonnegative")
    if inputs.open_positions < 0 or inputs.market_data_age_seconds < 0:
        raise ContractError("synthetic risk counts and ages must be nonnegative")

    limits = (
        ("KILL_SWITCH", not inputs.kill_switch_triggered),
        (
            "CAPITAL_AT_RISK",
            inputs.capital_at_risk.amount <= runtime_policy.max_capital_at_risk.amount,
        ),
        (
            "POSITION_NOTIONAL",
            inputs.proposed_notional.amount <= runtime_policy.max_position_notional.amount,
        ),
        ("DAILY_LOSS", inputs.daily_loss.amount <= runtime_policy.max_daily_loss.amount),
        ("DRAWDOWN", inputs.drawdown_fraction <= runtime_policy.max_drawdown_fraction),
        (
            "SYMBOL_CONCENTRATION",
            inputs.symbol_concentration_fraction
            <= portfolio_policy.max_symbol_concentration_fraction,
        ),
        (
            "CORRELATED_EXPOSURE",
            inputs.correlated_exposure_fraction
            <= portfolio_policy.max_correlated_exposure_fraction,
        ),
        (
            "PORTFOLIO_STRATEGY_BUDGET",
            inputs.strategy_budget_fraction <= portfolio_policy.max_strategy_budget_fraction,
        ),
        (
            "STRATEGY_NOTIONAL",
            inputs.proposed_notional.amount <= strategy_budget.max_notional.amount,
        ),
        ("STRATEGY_DAILY_LOSS", inputs.daily_loss.amount <= strategy_budget.max_daily_loss.amount),
        (
            "OPEN_POSITIONS",
            inputs.open_positions
            <= min(portfolio_policy.max_open_positions, strategy_budget.max_open_positions),
        ),
        (
            "MARKET_DATA_AGE",
            inputs.market_data_age_seconds <= market_policy.max_market_data_age_seconds,
        ),
        ("QUOTE_SPREAD", inputs.quote_spread_bps <= market_policy.max_quote_spread_bps),
        ("VENUE_HEALTH", not inputs.venue_health_degraded),
        ("TIMESTAMP_MONOTONIC", inputs.timestamps_monotonic),
    )
    checks = tuple(
        RiskCheck(
            rule_code=code,
            outcome=RiskOutcome.PASS if passed else RiskOutcome.BLOCK,
            evidence_refs=evidence_refs,
            detail="within limit" if passed else "limit breached; synthetic action blocked",
        )
        for code, passed in limits
    )
    decision = RiskOutcome.BLOCK if any(not passed for _, passed in limits) else RiskOutcome.PASS
    return RiskDecision(
        risk_id=risk_id,
        subject_ref=subject_ref,
        as_of=as_of,
        decision=decision,
        rule_results=checks,
        evidence_refs=evidence_refs,
        created_at=created_at,
        creator_type=creator_type,
        provenance=provenance,
    )
