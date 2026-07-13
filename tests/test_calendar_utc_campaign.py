import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_calendar_utc_campaign import preflight  # noqa: E402

CAMPAIGN = ROOT / "research/CALENDAR_UTC_G1_G11_CAMPAIGN_V1.yaml"
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"


def test_calendar_campaign_is_frozen_safe_and_complete() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    assert campaign["status"] in {"PREREGISTERED_NOT_RUN", "COMPLETED_REJECTED"}
    if campaign["status"] == "COMPLETED_REJECTED":
        assert campaign["completion"]["numeric_verdict"] == "FAIL"
        assert campaign["completion"]["supervisory_verdict"] == ("REJECTED_NOT_PROMOTION_ELIGIBLE")
    assert campaign["safety"] == {
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "orders": "DISABLED",
        "network": "PROHIBITED",
        "credentials_required": False,
        "sealed_v2_holdout_access": "PROHIBITED",
    }
    assert [item["selected_weekday"] for item in campaign["trial_roster"]] == list(range(7))
    assert campaign["method"]["raw_statistical_trial_count"] == 7
    assert len(campaign["method"]["cost_scenarios"]) == 6
    assert set(campaign["hard_gates"]) == {
        f"G{index}_{name}"
        for index, name in [
            (1, "DATA_PROVENANCE"),
            (2, "CANONICAL_IDENTITY"),
            (3, "CAUSAL_GOLDENS"),
            (4, "INDEPENDENT_REPRODUCTION"),
            (5, "AFTER_COST_ECONOMICS"),
            (6, "CHRONOLOGICAL_OOS"),
            (7, "SAMPLE_AND_CLOCK_ROBUSTNESS"),
            (8, "REGIME_AND_TAIL"),
            (9, "BENCHMARK_AND_OPPORTUNITY"),
            (10, "MULTIPLE_TESTING"),
            (11, "INDEPENDENT_RISK_SUPERVISOR"),
        ]
    }


def test_calendar_campaign_preflight_verifies_without_scoring() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    if campaign["status"] == "COMPLETED_REJECTED":
        result = ROOT / campaign["completion"]["campaign_result"]
        assert result.is_file()
        assert result.name.endswith(f"{campaign['completion']['campaign_result_sha256']}.json")
        return
    result = preflight(require_clean=False)
    assert result["data_verification"]["status"] == "PASS"
    assert result["data_verification"]["network_allowed"] is False


def test_vectorbt_event_semantics_match_micro_golden() -> None:
    code = r"""
import json
import pandas as pd
from engines.vectorbt.calendar_utc_returns import build_events

index = pd.DatetimeIndex([
    "2026-07-12T23:00:00Z",
    "2026-07-13T00:00:00Z",
    "2026-07-13T02:00:00Z",
])
candles = pd.DataFrame({"open": [100.0, 100.0, 100.0], "close": [100.0, 100.0, 100.0]}, index=index)
entries, exits = build_events(candles)
print(json.dumps({
    "monday_entries": entries["weekday=0"].tolist(),
    "monday_exits": exits["weekday=0"].tolist(),
}))
"""
    result = subprocess.run(
        [str(ENGINE_PYTHON), "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        "monday_entries": [False, True, False],
        "monday_exits": [False, False, True],
    }
