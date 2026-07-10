import json
from pathlib import Path

import pytest

from tios.core_types.engine import MANDATORY_GRID
from tios.validation import evaluate_risk_preconditions


def _valid_validation() -> dict[str, object]:
    return {
        "status": "COMPLETE_APPROVABLE",
        "metrics": {"max_drawdown_abs": "12.5", "losses": 3},
        "gates": {
            gate: {"status": "PASS"} for gate in (*[f"G{number}" for number in range(1, 10)], "G11")
        },
    }


def _valid_cost_grid() -> dict[str, object]:
    return {
        "scenarios": [
            {
                "scenario": scenario.scenario_id,
                "fee_rate_per_side": str(scenario.fee_rate_per_side),
                "slippage_bps_per_side": str(scenario.slippage_bps_per_side),
                "diagnostic_only": scenario.diagnostic_only,
            }
            for scenario in MANDATORY_GRID
        ]
    }


def test_b2_validation_has_independent_risk_preconditions_and_no_promotion() -> None:
    root = Path(__file__).resolve().parents[1]
    validation = json.loads(
        (root / "artifacts/validation/B2_F0_S0/validation_summary.json").read_text()
    )
    cost = json.loads((root / "artifacts/validation/B2_F0_S0/cost_sensitivity.json").read_text())
    result = evaluate_risk_preconditions(validation, cost, live_orders_enabled=False)
    assert result.status == "PASS"
    assert result.no_live_capability
    assert result.complete_cost_grid
    assert result.drawdown_and_tail_metrics_reported
    assert not result.promotion_eligible


def test_missing_cost_grid_and_live_capability_fail_closed() -> None:
    result = evaluate_risk_preconditions(
        {"status": "COMPLETE_APPROVABLE", "metrics": {"max_drawdown_abs": 1, "losses": 1}},
        {"scenarios": []},
        live_orders_enabled=True,
    )
    assert result.status == "FAIL"
    assert not result.promotion_eligible


def test_promotion_requires_exact_valid_evidence() -> None:
    result = evaluate_risk_preconditions(
        _valid_validation(), _valid_cost_grid(), live_orders_enabled=False
    )
    assert result.status == "PASS"
    assert result.promotion_eligible


@pytest.mark.parametrize("bad_gate", [None, "UNKNOWN", "NOT_RUN", "PASSING", float("nan")])
def test_missing_or_unknown_mandatory_gate_fails_closed(bad_gate: object) -> None:
    validation = _valid_validation()
    gates = validation["gates"]
    assert isinstance(gates, dict)
    if bad_gate is None:
        gates.pop("G9")
    else:
        gates["G9"] = {"status": bad_gate}

    result = evaluate_risk_preconditions(validation, _valid_cost_grid(), live_orders_enabled=False)
    assert not result.promotion_eligible


def test_unknown_gate_and_duplicate_or_mismatched_cost_scenario_fail_closed() -> None:
    validation = _valid_validation()
    gates = validation["gates"]
    assert isinstance(gates, dict)
    gates["G10"] = {"status": "PASS"}
    cost = _valid_cost_grid()
    scenarios = cost["scenarios"]
    assert isinstance(scenarios, list)
    scenarios.append(dict(scenarios[0]))
    scenarios[0]["fee_rate_per_side"] = "NaN"

    result = evaluate_risk_preconditions(validation, cost, live_orders_enabled=False)
    assert not result.complete_cost_grid
    assert not result.promotion_eligible


@pytest.mark.parametrize(
    "metrics",
    [
        {"max_drawdown_abs": "NaN", "losses": 1},
        {"max_drawdown_abs": "Infinity", "losses": 1},
        {"max_drawdown_abs": -1, "losses": 1},
        {"max_drawdown_abs": 1, "losses": -1},
        {"max_drawdown_abs": 1, "losses": 1.5},
        {"max_drawdown_abs": 1},
    ],
)
def test_invalid_drawdown_or_loss_metrics_fail_closed(metrics: dict[str, object]) -> None:
    validation = _valid_validation()
    validation["metrics"] = metrics
    result = evaluate_risk_preconditions(validation, _valid_cost_grid(), live_orders_enabled=False)
    assert result.status == "FAIL"
    assert not result.drawdown_and_tail_metrics_reported
    assert not result.promotion_eligible
