from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tios.research_assets import (
    FreshnessState,
    HumanReviewStatus,
    ResearchAssetError,
    ResearchAssetRecord,
    ResearchAssetRegistry,
)


def test_research_asset_registry_backfills_retained_s0_s2_evidence() -> None:
    root = Path(__file__).parents[1]
    registry = ResearchAssetRegistry.load(root / "research/RESEARCH_ASSETS_V1.json")
    records = registry.list()

    assert len(records) >= 5
    assert len(registry.digest()) == 64
    assert {record.human_review for record in records} >= {
        HumanReviewStatus.REVIEWED,
        HumanReviewStatus.PENDING_HUMAN_REVIEW,
        HumanReviewStatus.NOT_REQUIRED,
    }
    assert all(record.sources or record.quality_score_refs for record in records)
    assert all(
        (root / evidence_ref).is_file()
        for record in records
        for evidence_ref in (*record.sources, *record.quality_score_refs)
    )
    assert {record.freshness for record in records} >= {
        FreshnessState.CURRENT,
        FreshnessState.AGING,
    }
    assert {record.asset_id for record in registry.consumers("research-lab")} >= {
        "RA-S1-DATASET-FREEZE",
        "RA-S2-RESEARCH-LAB-799",
        "RA-S2-SEED-CYCLE-QC",
    }
    assert registry.get("RA-S2-SEED-CYCLE-QC").dependencies == (
        "RA-S1-STRATEGY-SEED-BATCH",
        "RA-S2-RESEARCH-LAB-799",
    )
    assert (
        registry.digest()
        == ResearchAssetRegistry.load(root / "research/RESEARCH_ASSETS_V1.json").digest()
    )


def test_research_asset_registry_rejects_assets_without_evidence() -> None:
    with pytest.raises(ResearchAssetError, match="require source or quality evidence"):
        ResearchAssetRecord(
            asset_id="RA-EMPTY",
            title="Empty",
            question="No evidence?",
            creator="test",
            created_at="2026-07-10T00:00:00Z",
            cost_usd=0.0,
            sources=(),
            quality_score_refs=(),
            human_review=HumanReviewStatus.NOT_REQUIRED,
            dependencies=(),
            consumers=("test",),
            freshness=FreshnessState.CURRENT,
            contradiction_refs=(),
            supersedes=(),
            reverify_trigger="never",
        )


def test_research_asset_registry_rejects_bad_graphs() -> None:
    root = Path(__file__).parents[1]
    records = ResearchAssetRegistry.load(root / "research/RESEARCH_ASSETS_V1.json").list()
    first, second = records[:2]

    with pytest.raises(ResearchAssetError, match="unknown dependencies"):
        ResearchAssetRegistry([replace(first, dependencies=("RA-MISSING",)), *records[1:]])
    with pytest.raises(ResearchAssetError, match="cannot reference itself"):
        ResearchAssetRegistry([replace(first, supersedes=(first.asset_id,)), *records[1:]])
    with pytest.raises(ResearchAssetError, match="cyclic dependencies"):
        ResearchAssetRegistry(
            [
                replace(first, dependencies=(second.asset_id,)),
                replace(second, dependencies=(first.asset_id,)),
                *records[2:],
            ]
        )


def test_research_asset_freshness_filters_are_strict() -> None:
    root = Path(__file__).parents[1]
    registry = ResearchAssetRegistry.load(root / "research/RESEARCH_ASSETS_V1.json")

    assert all(
        record.freshness is FreshnessState.CURRENT for record in registry.freshness("CURRENT")
    )
    with pytest.raises(ResearchAssetError, match="unknown freshness state"):
        registry.freshness("FRESH_ENOUGH")


def test_research_asset_cost_amortization_uses_consumer_tracking() -> None:
    root = Path(__file__).parents[1]
    registry = ResearchAssetRegistry.load(root / "research/RESEARCH_ASSETS_V1.json")
    rows = registry.cost_amortization()

    assert len(rows) == len(registry.list())
    assert {row["asset_id"]: (row["consumer_count"], row["cost_per_consumer_usd"]) for row in rows}[
        "RA-S2-RESEARCH-LAB-799"
    ] == (3, 0.0)
    assert all(row["consumer_count"] > 0 for row in rows)
