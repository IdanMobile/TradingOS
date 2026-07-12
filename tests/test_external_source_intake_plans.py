"""External source-intake plans stay offline, replay-only, and source-linked."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from tios.research_assets import (
    CaptureMode,
    IntakeStatus,
    ReplayHypothesisRegistry,
    ReplayHypothesisStatus,
    ResearchSourceRegistry,
    SourceIntakePlanError,
    SourceIntakePlanRegistry,
)

ROOT = Path(__file__).parent.parent
SOURCES = ROOT / "research" / "PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
PLANS = ROOT / "research" / "EXTERNAL_SOURCE_INTAKE_PLANS_V1.yaml"
REPLAY = ROOT / "research" / "EXTERNAL_REPLAY_HYPOTHESES_V1.yaml"
SNAPSHOT_SCRIPT = ROOT / "scripts" / "build_external_source_intake_snapshots.py"
REQUIRED_PROHIBITIONS = {
    "credential_request",
    "account_connection",
    "subscription_or_copy_action",
    "order_routing",
    "paper_demo_or_live_activation",
    "profit_claim_inheritance",
}


spec = importlib.util.spec_from_file_location("external_source_snapshots", SNAPSHOT_SCRIPT)
assert spec is not None and spec.loader is not None
snapshot_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot_module)


@pytest.fixture
def source_registry() -> ResearchSourceRegistry:
    return ResearchSourceRegistry.load(SOURCES)


@pytest.fixture
def registry(source_registry: ResearchSourceRegistry) -> SourceIntakePlanRegistry:
    return SourceIntakePlanRegistry.load(PLANS, source_registry=source_registry)


@pytest.fixture
def replay_registry(
    source_registry: ResearchSourceRegistry,
    registry: SourceIntakePlanRegistry,
) -> ReplayHypothesisRegistry:
    return ReplayHypothesisRegistry.load(
        REPLAY,
        source_registry=source_registry,
        intake_registry=registry,
    )


def test_external_source_intake_plans_resolve_seeded_sources(
    registry: SourceIntakePlanRegistry,
) -> None:
    plans = registry.list()
    assert {plan.plan_id for plan in plans} == {
        "INTAKE-BINANCE-TRADING-BOTS",
        "INTAKE-BINANCE-COPY-TRADING",
        "INTAKE-TRADINGVIEW-IDEAS",
        "INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES",
        "INTAKE-3COMMAS-DCA-BOT",
    }
    assert {plan.source_ref for plan in plans} == {
        "SRC-BINANCE-TRADING-BOTS",
        "SRC-BINANCE-COPY-TRADING",
        "SRC-TRADINGVIEW-IDEAS",
        "SRC-TRADINGVIEW-PUBLIC-STRATEGIES",
        "SRC-3COMMAS-DCA-BOT",
    }
    assert registry.get("INTAKE-BINANCE-TRADING-BOTS").capture_mode is (
        CaptureMode.CONFIG_RECONSTRUCTION
    )
    assert registry.get("INTAKE-BINANCE-COPY-TRADING").status is IntakeStatus.DESIGN_ONLY
    tv_public = registry.get("INTAKE-TRADINGVIEW-PUBLIC-STRATEGIES")
    assert tv_public.capture_mode is CaptureMode.STRATEGY_TESTER_REPRODUCTION
    assert "license_or_reuse_status" in tv_public.required_capture_fields
    assert "profit_factor" in tv_public.required_capture_fields
    assert any("Protected and invite-only" in note for note in tv_public.notes)


def test_external_source_intake_plans_are_not_execution_authority(
    registry: SourceIntakePlanRegistry,
) -> None:
    for plan in registry.list():
        assert plan.approval_eligible is False
        assert set(plan.prohibited_actions) >= REQUIRED_PROHIBITIONS
        assert plan.target_artifact.startswith("artifacts/")
        assert plan.validation_prerequisites


def test_external_source_intake_plan_validation_fails_closed(
    registry: SourceIntakePlanRegistry,
    source_registry: ResearchSourceRegistry,
) -> None:
    first = registry.list()[0]
    with pytest.raises(SourceIntakePlanError, match="unknown source_ref"):
        SourceIntakePlanRegistry(
            [replace(first, source_ref="SRC-DOES-NOT-EXIST")],
            source_registry=source_registry,
        )
    with pytest.raises(SourceIntakePlanError, match="prohibited_actions"):
        SourceIntakePlanRegistry(
            [replace(first, prohibited_actions=("credential_request",))],
            source_registry=source_registry,
        )
    with pytest.raises(SourceIntakePlanError, match="approval eligible"):
        SourceIntakePlanRegistry(
            [replace(first, approval_eligible=True)],
            source_registry=source_registry,
        )


def test_external_source_intake_digest_is_deterministic(
    registry: SourceIntakePlanRegistry,
    source_registry: ResearchSourceRegistry,
) -> None:
    assert len(registry.digest()) == 64
    reversed_registry = SourceIntakePlanRegistry(
        reversed(registry.list()),
        source_registry=source_registry,
    )
    assert reversed_registry.digest() == registry.digest()


def test_external_source_intake_snapshot_builder_retains_nonexecution_boundary(
    registry: SourceIntakePlanRegistry,
) -> None:
    index = snapshot_module.build_snapshots("2026-07-11T00:00:00Z")
    assert index["plan_count"] == 5
    assert index["execution_authority"] == "NONE"
    assert index["venue_connection"] == "NONE"
    assert index["paper_demo_live"] == "DISABLED"
    for row in index["rows"]:
        assert row["approval_eligible"] is False
        payload = json.loads((snapshot_module.ROOT / row["artifact"]).read_text())
        plan = registry.get(row["plan_id"])
        assert payload["source_ref"] == plan.source_ref
        assert payload["content_capture_status"] == "METADATA_ONLY_PENDING_PLATFORM_CAPTURE"
        assert payload["approval_eligible"] is False
        assert set(payload["prohibited_actions"]) >= REQUIRED_PROHIBITIONS
        assert payload["required_capture_fields"]["captured_at_utc"]["value"] == (
            "2026-07-11T00:00:00Z"
        )
        captured_fields = [
            field
            for field in payload["required_capture_fields"].values()
            if field["status"] == "PUBLIC_SOURCE_CAPTURED"
        ]
        assert captured_fields
        assert all(field["evidence_url"].startswith("https://") for field in captured_fields)


def test_external_replay_hypotheses_are_source_linked_and_noneligible(
    replay_registry: ReplayHypothesisRegistry,
) -> None:
    hypotheses = replay_registry.list()
    assert {item.hypothesis_id for item in hypotheses} == {
        "RPH-BINANCE-SPOT-GRID-CONFIG",
        "RPH-BINANCE-COPY-TRADING-OPAQUE",
        "RPH-TRADINGVIEW-RULED-SIGNAL-REPLAY",
        "RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER",
        "RPH-3COMMAS-DCA-CONFIG",
    }
    for item in hypotheses:
        assert item.execution_authority == "NONE"
        assert item.profit_claims_inherited is False
        assert item.approval_eligible is False
        assert item.artifact_refs
        assert item.validation_plan
    tv_public = replay_registry.get("RPH-TRADINGVIEW-PUBLIC-STRATEGY-TESTER")
    assert tv_public.status is ReplayHypothesisStatus.SPEC_CANDIDATE
    assert "open-source/visible-code confirmation" in tv_public.required_inputs
    assert any("TV-versus-OS divergence report" in step for step in tv_public.validation_plan)


def test_copy_trading_replay_hypothesis_fails_closed_until_action_history_exists(
    replay_registry: ReplayHypothesisRegistry,
) -> None:
    item = replay_registry.get("RPH-BINANCE-COPY-TRADING-OPAQUE")
    assert item.status is ReplayHypothesisStatus.NON_RECONSTRUCTABLE
    assert "historical actions" in item.missing_inputs
    assert "sizing semantics" in item.missing_inputs


def test_external_replay_hypothesis_validation_rejects_execution_authority(
    replay_registry: ReplayHypothesisRegistry,
    source_registry: ResearchSourceRegistry,
    registry: SourceIntakePlanRegistry,
) -> None:
    first = replay_registry.list()[0]
    with pytest.raises(SourceIntakePlanError, match="execution_authority"):
        ReplayHypothesisRegistry(
            [replace(first, execution_authority="PAPER")],
            source_registry=source_registry,
            intake_registry=registry,
        )
    with pytest.raises(SourceIntakePlanError, match="profit claims"):
        ReplayHypothesisRegistry(
            [replace(first, profit_claims_inherited=True)],
            source_registry=source_registry,
            intake_registry=registry,
        )
    with pytest.raises(SourceIntakePlanError, match="approval eligible"):
        ReplayHypothesisRegistry(
            [replace(first, approval_eligible=True)],
            source_registry=source_registry,
            intake_registry=registry,
        )
