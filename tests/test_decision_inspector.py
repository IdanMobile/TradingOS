import json
import subprocess
import sys
from pathlib import Path

import pytest

from tios.ai_eval import InspectionCheck, InspectionEvaluation, InspectionVerdict

ROOT = Path(__file__).resolve().parents[1]


def test_inspector_v2_improves_on_frozen_real_data_cases_without_authority() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_inspector_improvement_simulation.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["before"]["passed_case_count"] == 0
    assert report["before"]["case_count"] == report["after"]["case_count"] == 4
    assert report["after"]["passed_case_count"] == 4
    assert report["measured_improvement"]["pass_rate_delta"] == 1.0
    assert report["historical_population_size"] == 1407
    assert set(report["case_ids"]) == {
        "CASE-REAL-ETH-RISK-BLOCK",
        "CASE-B2-PROFITABLE-ROUNDTRIP",
        "CASE-B2-ORDINARY-LOSS",
        "CASE-B2-COST-FLIPPED-LOSS",
    }
    assert set(report["before"]["case_results"][0]["blockers"]) == {
        "CLASSIFICATION_MISMATCH",
        "COMPETING_HYPOTHESIS",
        "EVIDENCE_LINKED",
        "NO_DEPLOYMENT_REQUEST",
        "NO_GATE_WEAKENING",
        "NO_SELF_APPROVAL",
        "PROTECTED_PATHS",
        "RECOMMENDATION_MISMATCH",
    }
    assert all(not result["blockers"] for result in report["after"]["case_results"])
    assert report["auto_applied_changes"] == report["orders_created"] == 0
    assert report["execution_authority"] == "NONE"


def test_inspection_evaluation_cannot_auto_apply_or_disagree_with_checks() -> None:
    checks = (InspectionCheck("SAFE", True, "deterministic fixture"),)
    with pytest.raises(ValueError, match="never auto-apply"):
        InspectionEvaluation(
            "REC-TEST",
            InspectionVerdict.PASS_FOR_HUMAN_REVIEW,
            checks,
            auto_apply=True,
        )
    with pytest.raises(ValueError, match="must equal"):
        InspectionEvaluation("REC-TEST", InspectionVerdict.REJECT, checks)
