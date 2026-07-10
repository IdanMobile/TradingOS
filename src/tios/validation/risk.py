"""Independent S1 risk preconditions for validation packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from tios.core_types.engine import MANDATORY_GRID

REQUIRED_METRICS = frozenset({"max_drawdown_abs", "losses"})
MANDATORY_GATES = frozenset({*(f"G{number}" for number in range(1, 10)), "G11"})


@dataclass(frozen=True)
class RiskPreconditionResult:
    status: str
    no_live_capability: bool
    complete_cost_grid: bool
    drawdown_and_tail_metrics_reported: bool
    promotion_eligible: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


def evaluate_risk_preconditions(
    validation: Mapping[str, Any],
    cost_sensitivity: Mapping[str, Any],
    *,
    live_orders_enabled: bool,
) -> RiskPreconditionResult:
    """Evaluate prototype risk posture without trusting strategy logic."""
    expected = {scenario.scenario_id: scenario for scenario in MANDATORY_GRID}
    raw_rows = cost_sensitivity.get("scenarios")
    rows = raw_rows if isinstance(raw_rows, (list, tuple)) else ()
    actual: dict[str, Mapping[str, Any]] = {}
    valid_cost_rows = isinstance(raw_rows, (list, tuple))
    if valid_cost_rows:
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("scenario"), str):
                valid_cost_rows = False
                continue
            scenario_id = row["scenario"]
            if scenario_id in actual:
                valid_cost_rows = False
            actual[scenario_id] = row
    if set(actual) != set(expected):
        valid_cost_rows = False
    for scenario_id, scenario in expected.items():
        row = actual.get(scenario_id, {})
        try:
            fee = Decimal(str(row.get("fee_rate_per_side")))
            slippage = Decimal(str(row.get("slippage_bps_per_side")))
        except (InvalidOperation, ValueError):
            valid_cost_rows = False
            continue
        if (
            not fee.is_finite()
            or not slippage.is_finite()
            or fee != scenario.fee_rate_per_side
            or slippage != scenario.slippage_bps_per_side
            or row.get("diagnostic_only") is not scenario.diagnostic_only
        ):
            valid_cost_rows = False
    metrics = validation.get("metrics", {})
    metrics_reported = isinstance(metrics, Mapping) and REQUIRED_METRICS <= set(metrics)
    if metrics_reported:
        try:
            drawdown = Decimal(str(metrics["max_drawdown_abs"]))
            losses = metrics["losses"]
            metrics_reported = (
                drawdown.is_finite()
                and drawdown >= 0
                and isinstance(losses, int)
                and not isinstance(losses, bool)
                and losses >= 0
            )
        except (InvalidOperation, ValueError):
            metrics_reported = False
    complete_cost_grid = valid_cost_rows
    no_live = not live_orders_enabled
    reasons = []
    if not no_live:
        reasons.append("live order capability must be absent")
    if not complete_cost_grid:
        reasons.append("mandatory fee/slippage grid is incomplete")
    if not metrics_reported:
        reasons.append("drawdown and loss metrics are required")
    gates = validation.get("gates", {})
    all_gates_pass = (
        isinstance(gates, Mapping)
        and set(gates) == MANDATORY_GATES
        and all(
            isinstance(gate, Mapping) and gate.get("status") == "PASS" for gate in gates.values()
        )
    )
    promotion_eligible = (
        not reasons and validation.get("status") == "COMPLETE_APPROVABLE" and all_gates_pass
    )
    return RiskPreconditionResult(
        status="PASS" if not reasons else "FAIL",
        no_live_capability=no_live,
        complete_cost_grid=complete_cost_grid,
        drawdown_and_tail_metrics_reported=metrics_reported,
        promotion_eligible=promotion_eligible,
        reasons=tuple(reasons),
    )
