"""S3/S4 readiness artifacts remain probe-only and non-executable."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_s3_s4_readiness_artifacts.py"
REPORT = ROOT / "artifacts" / "reports" / "S3_S4_CONTROL_PLANE_READINESS_2026_07_11.json"

spec = importlib.util.spec_from_file_location("s3_s4_readiness", SCRIPT)
assert spec is not None and spec.loader is not None
readiness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = readiness
spec.loader.exec_module(readiness)


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_s3_s4_readiness_builder_outputs_probe_only_payload() -> None:
    payload = readiness.build_payload()
    assert payload["schema"] == "tios-s3-s4-control-plane-readiness-v1"
    assert payload["mode"] == "CONTROL_PLANE_PROBE_ONLY"
    assert payload["status"] == "BLOCKED_BY_GATES"
    assert payload["execution_authority"] == "NONE"
    assert payload["venue_connection"] == "NONE"
    assert payload["paper_orders"] == "DISABLED"
    assert payload["live_orders"] == "DISABLED"
    assert payload["active_record_counts"] == {
        "stage_gate_records": 0,
        "paper_lane_proposals": 0,
        "paper_divergence_reports": 0,
        "paper_fill_policies": 0,
        "operational_drill_records": 0,
        "synthetic_ledgers": 0,
        "synthetic_accounts": 0,
        "synthetic_portfolios": 0,
        "runtime_risk_policies": 0,
        "portfolio_risk_policies": 0,
        "strategy_budget_policies": 0,
        "market_condition_policies": 0,
        "restricted_credential_policies": 0,
        "paper_operations_runbooks": 0,
        "paper_operations_events": 0,
        "operational_incidents": 0,
        "durable_evidence_events": 0,
        "paper_stability_reports": 0,
        "limited_live_risk_packages": 0,
        "live_operations_runbooks": 0,
        "live_operations_events": 0,
        "live_readiness_proposals": 0,
    }
    assert "order_submit_cancel_replace" in payload["prohibited"]
    assert "paper_demo_live_activation" in payload["prohibited"]
    assert payload["contract_probe_records"]["paper_divergence_probe"]["status"] == (
        "OUTSIDE_TOLERANCE"
    )
    assert payload["contract_probe_records"]["operational_drill_probe"]["status"] == "PASS"
    assert payload["contract_probe_records"]["blocked_operational_drill_probe"]["status"] == (
        "BLOCKED"
    )
    ledger = payload["contract_probe_records"]["synthetic_ledger_probe"]
    assert ledger["synthetic"] is True
    assert ledger["real_money"] is False
    assert ledger["execution_authority"] == "NONE"
    assert ledger["balances"] == [{"amount": "9999", "currency": "USDT"}]
    fill_policy = payload["contract_probe_records"]["synthetic_paper_fill_policy_probe"]
    assert fill_policy["synthetic"] is True
    assert fill_policy["real_money"] is False
    assert fill_policy["execution_authority"] == "NONE"
    assert fill_policy["paper_orders"] == "DISABLED"
    assert fill_policy["price_source"] == "BAR_MIDPOINT"
    account = payload["contract_probe_records"]["synthetic_account_probe"]
    assert account["synthetic"] is True
    assert account["real_money"] is False
    assert account["balances"] == [{"amount": "9999", "currency": "USDT"}]
    portfolio = payload["contract_probe_records"]["synthetic_portfolio_probe"]
    assert portfolio["synthetic"] is True
    assert portfolio["real_money"] is False
    assert portfolio["cash"] == [{"amount": "9999", "currency": "USDT"}]
    assert portfolio["equity"] == [{"amount": "9999", "currency": "USDT"}]
    risk_policy = payload["contract_probe_records"]["synthetic_runtime_risk_policy_probe"]
    assert risk_policy["synthetic"] is True
    assert risk_policy["real_money"] is False
    assert risk_policy["execution_authority"] == "NONE"
    assert risk_policy["kill_switch_mode"] == "MANUAL_REQUIRED"
    assert risk_policy["max_daily_loss"] == {"amount": "250", "currency": "USDT"}
    portfolio_risk = payload["contract_probe_records"]["synthetic_portfolio_risk_policy_probe"]
    assert portfolio_risk["synthetic"] is True
    assert portfolio_risk["real_money"] is False
    assert portfolio_risk["execution_authority"] == "NONE"
    assert portfolio_risk["max_symbol_concentration_fraction"] == "0.40"
    assert portfolio_risk["max_correlated_exposure_fraction"] == "0.60"
    assert portfolio_risk["max_strategy_budget_fraction"] == "0.25"
    assert portfolio_risk["max_open_positions"] == 8
    strategy_budget = payload["contract_probe_records"]["synthetic_strategy_budget_policy_probe"]
    assert strategy_budget["execution_authority"] == "NONE"
    assert strategy_budget["max_portfolio_fraction"] == "0.25"
    assert strategy_budget["max_notional"] == {"amount": "2500", "currency": "USDT"}
    assert strategy_budget["max_open_positions"] == 2
    market_guard = payload["contract_probe_records"]["synthetic_market_condition_policy_probe"]
    assert market_guard["execution_authority"] == "NONE"
    assert market_guard["max_market_data_age_seconds"] == 30
    assert market_guard["max_quote_spread_bps"] == "25"
    assert market_guard["block_when_venue_health_degraded"] is True
    credential_policy = payload["contract_probe_records"]["restricted_credential_policy_probe"]
    assert credential_policy["credential_material_present"] is False
    assert credential_policy["outbound_funds_allowed"] is False
    assert credential_policy["transfers_allowed"] is False
    assert credential_policy["execution_authority"] == "NONE"
    assert credential_policy["venue_connection"] == "NONE"
    assert credential_policy["max_order_notional"] == {"amount": "100", "currency": "USDT"}
    runbook = payload["contract_probe_records"]["paper_operations_runbook_probe"]
    assert runbook["execution_authority"] == "NONE"
    assert runbook["paper_orders"] == "DISABLED"
    assert runbook["heartbeat_interval_seconds"] == 60
    assert runbook["heartbeat_timeout_seconds"] == 180
    assert runbook["log_retention_days"] == 90
    assert runbook["intervention_mode"] == "MANUAL_ONLY"
    event = payload["contract_probe_records"]["paper_operations_event_probe"]
    assert event["execution_authority"] == "NONE"
    assert event["paper_orders"] == "DISABLED"
    assert event["kind"] == "HEARTBEAT"
    assert event["severity"] == "INFO"
    assert event["runbook_ref"] == {"value": "APR-PAPER-OPERATIONS-RUNBOOK-2026-07-11"}
    incident = payload["contract_probe_records"]["operational_incident_probe"]
    assert incident["status"] == "OPEN"
    assert incident["severity"] == "CRITICAL"
    assert incident["execution_authority"] == "NONE"
    assert incident["event_refs"] == [{"value": "APR-PAPER-OPERATIONS-EVENT-HEARTBEAT-2026-07-11"}]
    stability = payload["contract_probe_records"]["paper_stability_probe"]
    assert stability["status"] == "BLOCKED"
    assert stability["execution_authority"] == "NONE"
    assert stability["paper_orders"] == "DISABLED"
    assert stability["required_observation_hours"] == "168"
    assert stability["observed_uptime_fraction"] == "0"
    assert stability["blocker"] == "no active paper lane has run a stability window"
    live_risk = payload["contract_probe_records"]["limited_live_risk_package_probe"]
    assert live_risk["status"] == "BLOCKED"
    assert live_risk["execution_authority"] == "NONE"
    assert live_risk["live_orders"] == "DISABLED"
    assert live_risk["maximum_capital_at_risk"] == {"amount": "1000", "currency": "USDT"}
    assert live_risk["maximum_single_order_notional"] == {"amount": "100", "currency": "USDT"}
    assert live_risk["blocker"] == "S3 paper stability evidence is not complete"
    live_runbook = payload["contract_probe_records"]["live_operations_runbook_probe"]
    assert live_runbook["execution_authority"] == "NONE"
    assert live_runbook["live_orders"] == "DISABLED"
    assert live_runbook["heartbeat_interval_seconds"] == 60
    assert live_runbook["incident_response_minutes"] == 15
    assert live_runbook["log_retention_days"] == 365
    assert live_runbook["escalation_mode"] == "OPERATOR_MANUAL_ONLY"
    live_event = payload["contract_probe_records"]["live_operations_event_probe"]
    assert live_event["execution_authority"] == "NONE"
    assert live_event["live_orders"] == "DISABLED"
    assert live_event["kind"] == "HEARTBEAT"
    assert live_event["severity"] == "INFO"
    assert live_event["runbook_ref"] == {"value": "APR-LIVE-OPERATIONS-RUNBOOK-2026-07-11"}
    assert live_event["limited_live_risk_package_ref"] == {
        "value": "APR-LIMITED-LIVE-RISK-PACKAGE-2026-07-11"
    }


def test_retained_s3_s4_readiness_artifact_is_current_and_hash_checked() -> None:
    assert REPORT.is_file(), "run scripts/build_s3_s4_readiness_artifacts.py first"
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    expected = dict(payload)
    content_sha256 = expected.pop("content_sha256")
    assert content_sha256 == _hash(expected)
    assert payload["status"] == "BLOCKED_BY_GATES"
    assert payload["contract_probe_records"]["s3_gate"]["status"] == "BLOCKED"
    assert payload["contract_probe_records"]["s4_gate"]["status"] == "BLOCKED"
    assert "no candidate is validated or promotion eligible" in payload["s3_blockers"]
    assert "no venue credential is requested or configured" in payload["s4_blockers"]
