from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tios.trading_domain import (
    ContractError,
    CreatorType,
    DomainRef,
    KillSwitchMode,
    Money,
    PortfolioId,
    Provenance,
    RiskId,
    RiskOutcome,
    Stage,
    SyntheticMarketConditionPolicy,
    SyntheticPortfolioRiskPolicy,
    SyntheticRiskInputs,
    SyntheticRuntimeRiskPolicy,
    SyntheticStrategyBudgetPolicy,
    evaluate_synthetic_risk,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
STRATEGY = DomainRef("SV-FUTURE-VALIDATED-CONTEXT")
PORTFOLIO = PortfolioId("PF-SYNTHETIC-PROBE")
EVIDENCE = (DomainRef("EV-SYNTHETIC-RISK-PROBE"),)
PROVENANCE = Provenance(EVIDENCE)


def policies() -> tuple[
    SyntheticRuntimeRiskPolicy,
    SyntheticPortfolioRiskPolicy,
    SyntheticStrategyBudgetPolicy,
    SyntheticMarketConditionPolicy,
]:
    common = {
        "stage": Stage.S3_PAPER_DEMO,
        "evidence_refs": EVIDENCE,
        "created_at": NOW,
        "creator_type": CreatorType.SYSTEM,
        "provenance": PROVENANCE,
    }
    return (
        SyntheticRuntimeRiskPolicy(
            policy_id=RiskId("RISK-runtime"),
            strategy_context_ref=STRATEGY,
            portfolio_ref=PORTFOLIO,
            max_capital_at_risk=Money(Decimal("10000"), "USDT"),
            max_position_notional=Money(Decimal("2500"), "USDT"),
            max_daily_loss=Money(Decimal("250"), "USDT"),
            max_drawdown_fraction=Decimal("0.10"),
            kill_switch_mode=KillSwitchMode.MANUAL_REQUIRED,
            **common,
        ),
        SyntheticPortfolioRiskPolicy(
            policy_id=RiskId("RISK-portfolio"),
            portfolio_ref=PORTFOLIO,
            max_symbol_concentration_fraction=Decimal("0.40"),
            max_correlated_exposure_fraction=Decimal("0.60"),
            max_strategy_budget_fraction=Decimal("0.25"),
            max_open_positions=8,
            **common,
        ),
        SyntheticStrategyBudgetPolicy(
            policy_id=RiskId("RISK-budget"),
            strategy_context_ref=STRATEGY,
            portfolio_ref=PORTFOLIO,
            max_portfolio_fraction=Decimal("0.25"),
            max_notional=Money(Decimal("2500"), "USDT"),
            max_daily_loss=Money(Decimal("100"), "USDT"),
            max_open_positions=2,
            **common,
        ),
        SyntheticMarketConditionPolicy(
            policy_id=RiskId("RISK-market"),
            strategy_context_ref=STRATEGY,
            max_market_data_age_seconds=30,
            max_quote_spread_bps=Decimal("25"),
            block_when_venue_health_degraded=True,
            require_monotonic_timestamps=True,
            **common,
        ),
    )


def safe_inputs() -> SyntheticRiskInputs:
    return SyntheticRiskInputs(
        proposed_notional=Money(Decimal("1000"), "USDT"),
        capital_at_risk=Money(Decimal("1000"), "USDT"),
        daily_loss=Money(Decimal("25"), "USDT"),
        drawdown_fraction=Decimal("0.02"),
        symbol_concentration_fraction=Decimal("0.10"),
        correlated_exposure_fraction=Decimal("0.20"),
        strategy_budget_fraction=Decimal("0.10"),
        open_positions=1,
        market_data_age_seconds=5,
        quote_spread_bps=Decimal("5"),
    )


def evaluate(inputs: SyntheticRiskInputs):  # type: ignore[no-untyped-def]
    runtime, portfolio, budget, market = policies()
    return evaluate_synthetic_risk(
        risk_id=RiskId("RISK-decision"),
        subject_ref=STRATEGY,
        as_of=NOW,
        runtime_policy=runtime,
        portfolio_policy=portfolio,
        strategy_budget=budget,
        market_policy=market,
        inputs=inputs,
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def test_synthetic_risk_evaluator_passes_or_blocks_without_execution() -> None:
    passed = evaluate(safe_inputs())
    assert passed.decision is RiskOutcome.PASS
    assert len(passed.rule_results) == 15
    assert all(check.outcome is RiskOutcome.PASS for check in passed.rule_results)

    blocked = evaluate(
        replace(
            safe_inputs(),
            daily_loss=Money(Decimal("125"), "USDT"),
            market_data_age_seconds=31,
            kill_switch_triggered=True,
        )
    )
    assert blocked.decision is RiskOutcome.BLOCK
    blocked_codes = {
        check.rule_code for check in blocked.rule_results if check.outcome is RiskOutcome.BLOCK
    }
    assert blocked_codes == {"KILL_SWITCH", "STRATEGY_DAILY_LOSS", "MARKET_DATA_AGE"}


def test_synthetic_risk_evaluator_rejects_incompatible_context_or_currency() -> None:
    runtime, portfolio, budget, market = policies()
    with pytest.raises(ContractError, match="strategy context"):
        evaluate_synthetic_risk(
            risk_id=RiskId("RISK-bad-context"),
            subject_ref=DomainRef("SV-OTHER"),
            as_of=NOW,
            runtime_policy=runtime,
            portfolio_policy=portfolio,
            strategy_budget=budget,
            market_policy=market,
            inputs=safe_inputs(),
            evidence_refs=EVIDENCE,
            created_at=NOW,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
    with pytest.raises(ContractError, match="policy currency"):
        evaluate(replace(safe_inputs(), proposed_notional=Money(Decimal("1"), "USD")))
