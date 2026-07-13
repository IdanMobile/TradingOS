"""Canonical registration checks for the retained funding-carry hypothesis."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from tios.strategy.spec import parse_spec
from tios.strategy.validator import validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_funding_carry_basis as basis  # noqa: E402
import scripts.run_funding_carry_s3_paper as cost_stress  # noqa: E402

SPEC_DIR = ROOT / "strategies" / "research" / "funding-carry-basis-delta-neutral"


def _payload() -> dict:
    return yaml.safe_load((SPEC_DIR / "canonical_strategy_spec.yaml").read_text())


def test_funding_carry_registration_is_explicitly_non_executable() -> None:
    payload = _payload()
    report = validate(payload)
    spec = parse_spec(payload)

    assert report.verdict == "VALID_WITH_AMBIGUITIES"
    assert payload["strategy_id"] == "STRAT-FUNDING-CARRY-BASIS-DELTA-NEUTRAL"
    assert payload["risk"]["execution_authority"] == "NONE"
    assert payload["risk"]["status"] == "RESEARCH_ONLY_NOT_VALIDATED"
    assert len(payload["risk"]["no_trade_conditions"]) >= 7
    assert len(payload["risk"]["failure_modes"]) >= 8
    assert spec.entry_long is None and spec.exit_long is None
    assert spec.multi_leg is not None and spec.multi_leg.research_only
    assert [leg.instrument for leg in spec.multi_leg.legs] == [
        "SAME_SYMBOL_USDT_SPOT",
        "SAME_SYMBOL_USDT_PERPETUAL",
    ]
    assert [leg.side for leg in spec.multi_leg.legs] == ["LONG", "SHORT"]
    assert all(leg.execution_assumptions for leg in spec.multi_leg.legs)
    assert any("MUST NOT be interpreted as executable" in a for a in report.ambiguities)


def test_funding_carry_spec_hash_and_retained_parameters_have_parity() -> None:
    payload = _payload()
    pinned_hash = (SPEC_DIR / "canonical_strategy_spec.sha256").read_text().strip()

    assert parse_spec(payload).spec_hash() == pinned_hash

    params = payload["indicators"][0]["parameters"]
    sizing = payload["position_sizing"]
    costs = payload["risk"]["costs"]
    multi_leg = parse_spec(payload).multi_leg
    assert multi_leg is not None
    assert params["lookback_periods"] in basis.LOOKBACKS
    assert sizing["rebalance_periods"] in basis.REBALANCES
    assert (
        sum(leg.notional_fraction for leg in multi_leg.legs)
        == sizing["target_gross_notional_fraction"]
    )
    assert (
        sum(leg.notional_fraction * (1 if leg.side == "LONG" else -1) for leg in multi_leg.legs)
        == sizing["target_net_delta_fraction"]
    )
    assert costs["basis_backtest_toggle_fraction"] == basis.FEE
    assert costs["static_cost_stress_toggle_fraction"] == cost_stress.PAPER_TOGGLE_COST
