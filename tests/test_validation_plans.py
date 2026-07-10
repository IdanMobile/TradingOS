import json
from pathlib import Path


def test_validation_plans_are_materialized_before_execution() -> None:
    root = Path(__file__).resolve().parents[1] / "artifacts" / "validation" / "B2_F0_S0"
    oos = json.loads((root / "oos_report.json").read_text())
    walk = json.loads((root / "walk_forward_report.json").read_text())
    robustness = json.loads((root / "parameter_robustness.json").read_text())
    assert oos["status"] in {"PLAN_MATERIALIZED_NOT_EXECUTED", "COMPLETE_ENGINE_RUNS"}
    assert walk["windows"]
    assert len(robustness.get("neighborhood", robustness.get("variants", []))) >= 3
