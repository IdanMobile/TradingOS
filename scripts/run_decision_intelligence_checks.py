#!/usr/bin/env python3
"""Fast, measured feedback lane for the decision-intelligence vertical slice."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from time import perf_counter
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/quality/decision_intelligence_fast_checks.json"

SOURCE_PATHS = (
    "src/tios/dataset/arrow_time.py",
    "src/tios/trading_domain/decision_intelligence.py",
    "src/tios/services/reporting/decision_intelligence.py",
    "src/tios/services/reporting/backtest_attribution.py",
    "src/tios/approval/authority_audit.py",
    "src/tios/ai_eval/decision_inspector.py",
    "src/tios/ops/self_modification.py",
    "scripts/run_decision_intelligence_probe.py",
    "scripts/run_inspector_improvement_simulation.py",
    "scripts/run_backtest_loss_attribution.py",
    "scripts/build_cross_venue_premium_data.py",
    "scripts/verify_btc_mvrv_data.py",
    "scripts/verify_btc_tx_activity_data.py",
    "scripts/verify_funding_pressure_data.py",
    "scripts/verify_calendar_utc_data.py",
    "scripts/verify_cftc_btc_positioning_data.py",
    "scripts/verify_btc_spot_taker_imbalance_data.py",
    "scripts/run_decision_intelligence_checks.py",
    "tests/test_decision_intelligence.py",
    "tests/test_authority_audit.py",
    "tests/test_decision_inspector.py",
    "tests/test_backtest_attribution.py",
    "tests/test_arrow_time.py",
    "tests/test_self_modification.py",
)


class CheckResult(TypedDict):
    name: str
    command: list[str]
    passed: bool
    returncode: int
    elapsed_ms: float
    stdout: str
    stderr: str


def _run(name: str, command: tuple[str, ...]) -> CheckResult:
    started = perf_counter()
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": name,
        "command": list(command),
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> None:
    checks = (
        _run("ruff", ("uv", "run", "ruff", "check", *SOURCE_PATHS)),
        _run(
            "mypy",
            (
                "uv",
                "run",
                "mypy",
                "src/tios/trading_domain/decision_intelligence.py",
                "src/tios/dataset/arrow_time.py",
                "src/tios/services/reporting/decision_intelligence.py",
                "src/tios/services/reporting/backtest_attribution.py",
                "src/tios/approval/authority_audit.py",
                "src/tios/ai_eval/decision_inspector.py",
                "src/tios/ops/self_modification.py",
                "scripts/run_decision_intelligence_probe.py",
                "scripts/run_inspector_improvement_simulation.py",
                "scripts/run_backtest_loss_attribution.py",
                "scripts/run_decision_intelligence_checks.py",
                "tests/test_decision_intelligence.py",
                "tests/test_authority_audit.py",
                "tests/test_decision_inspector.py",
                "tests/test_backtest_attribution.py",
                "tests/test_arrow_time.py",
                "tests/test_self_modification.py",
            ),
        ),
        _run(
            "pytest",
            (
                "uv",
                "run",
                "pytest",
                "tests/test_decision_intelligence.py",
                "tests/test_authority_audit.py",
                "tests/test_decision_inspector.py",
                "tests/test_backtest_attribution.py",
                "tests/test_arrow_time.py",
                "tests/test_self_modification.py",
                "-q",
            ),
        ),
    )
    report = {
        "schema_version": 1,
        "lane": "DECISION_INTELLIGENCE_FOCUSED",
        "passed": all(check["passed"] for check in checks),
        "total_elapsed_ms": round(sum(check["elapsed_ms"] for check in checks), 3),
        "checks": checks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
