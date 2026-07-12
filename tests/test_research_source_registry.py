"""Primary research registry contract and S2 seed-set checks."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tios.research_assets import (
    EvidenceStrength,
    ExactSpanStatus,
    HypothesisFamily,
    ResearchSourceError,
    ResearchSourceRegistry,
    SourceClass,
)

ROOT = Path(__file__).parent.parent
REGISTRY_PATH = ROOT / "research" / "PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
PAPER2_PATH = ROOT / "strategies" / "seed" / "10-paper-reversal-jegadeesh1990"


@pytest.fixture
def registry() -> ResearchSourceRegistry:
    return ResearchSourceRegistry.load(REGISTRY_PATH)


def test_parses_all_verified_primary_sources(registry: ResearchSourceRegistry) -> None:
    assert len(registry.list()) == 15
    assert {record.doi.casefold() for record in registry.list() if record.doi is not None} == {
        "10.1111/j.1540-6261.1993.tb04702.x",
        "10.1016/j.jfineco.2011.11.003",
        "10.1111/j.1540-6261.1990.tb05110.x",
        "10.1016/j.jfineco.2014.11.010",
        "10.1111/jofi.12513",
        "10.1111/j.1540-6261.2004.00656.x",
        "10.21314/jcf.2016.322",
        "10.3905/jpm.2014.40.5.094",
        "10.1111/1468-0262.00152",
        "10.1198/073500105000000063",
    }
    assert registry.get("SRC-PAPER1").authors == (
        "Narasimhan Jegadeesh",
        "Sheridan Titman",
    )
    assert registry.get("SRC-BINANCE-TRADING-BOTS").doi is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_id": "paper 1"}, "source_id"),
        ({"doi": "not-a-doi"}, "DOI"),
        ({"canonical_publisher_url": "http://example.com/paper"}, "HTTPS"),
        ({"checked_at": "2026-07-10"}, "UTC timestamp"),
        ({"authors": ()}, "authors"),
        ({"hypothesis_families": ()}, "hypothesis_families"),
        ({"profit_claims_inherited": True}, "profit proof"),
        ({"locally_reproduced": True}, "local reproduction"),
        ({"approval_eligible": True}, "approval eligible"),
    ],
)
def test_record_validation(
    registry: ResearchSourceRegistry, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ResearchSourceError, match=message):
        replace(registry.list()[0], **changes)


def test_duplicate_ids_and_dois_are_rejected(registry: ResearchSourceRegistry) -> None:
    first, second = registry.list()[:2]
    with pytest.raises(ResearchSourceError, match="duplicate source_id"):
        ResearchSourceRegistry([first, replace(second, source_id=first.source_id)])
    paper_records = [record for record in registry.list() if record.doi is not None]
    paper_one, paper_two = paper_records[:2]
    with pytest.raises(ResearchSourceError, match="duplicate DOI"):
        ResearchSourceRegistry([paper_one, replace(paper_two, doi=paper_one.doi.upper())])


def test_family_queries_keep_research_hypotheses_distinct(
    registry: ResearchSourceRegistry,
) -> None:
    expected = {
        HypothesisFamily.CROSS_SECTIONAL_MOMENTUM: {
            "SRC-PAPER1",
            "SRC-TCOST-KS2004",
            "SRC-VOLSCALE-BS2015",
        },
        HypothesisFamily.TIME_SERIES_MOMENTUM: {"SRC-TSMOM-MOP2012"},
        HypothesisFamily.REVERSAL: {"SRC-PAPER2"},
        HypothesisFamily.VOLATILITY_SCALING: {
            "SRC-VOLMANAGED-MM2017",
            "SRC-VOLSCALE-BS2015",
        },
        HypothesisFamily.TRANSACTION_COSTS: {"SRC-TCOST-KS2004"},
        HypothesisFamily.MULTIPLE_TESTING_CONTROLS: {
            "SRC-DSR-2014",
            "SRC-PBO-2016",
            "SRC-SPA-2005",
            "SRC-WRC-2000",
        },
        HypothesisFamily.EXCHANGE_BOT_REPLAY: {"SRC-BINANCE-TRADING-BOTS"},
        HypothesisFamily.COPY_TRADING_REPLAY: {"SRC-BINANCE-COPY-TRADING"},
        HypothesisFamily.SIGNAL_REPLAY: {"SRC-TRADINGVIEW-IDEAS"},
        HypothesisFamily.PUBLIC_STRATEGY_REPRODUCTION: {"SRC-TRADINGVIEW-PUBLIC-STRATEGIES"},
        HypothesisFamily.BOT_PLATFORM_REPLAY: {"SRC-3COMMAS-DCA-BOT"},
    }
    for family, source_ids in expected.items():
        assert {record.source_id for record in registry.family(family)} == source_ids
        assert registry.family(family.value) == registry.family(family)


def test_digest_is_deterministic_and_order_independent(
    registry: ResearchSourceRegistry,
) -> None:
    assert len(registry.digest()) == 64
    assert ResearchSourceRegistry(reversed(registry.list())).digest() == registry.digest()
    changed = replace(registry.list()[0], claim_summary="A changed hypothesis-only summary.")
    assert ResearchSourceRegistry([changed, *registry.list()[1:]]).digest() != registry.digest()


def test_all_initial_seeds_are_hypothesis_only_and_noneligible(
    registry: ResearchSourceRegistry,
) -> None:
    for record in registry.list():
        assert record.evidence_strength is EvidenceStrength.HYPOTHESIS_ONLY
        assert record.exact_span_status is ExactSpanStatus.NOT_CAPTURED
        assert record.profit_claims_inherited is False
        assert record.locally_reproduced is False
        assert record.approval_eligible is False


def test_external_bot_signal_and_copy_sources_are_read_only_hypothesis_inputs(
    registry: ResearchSourceRegistry,
) -> None:
    external = {
        SourceClass.EXCHANGE_BOT_MARKETPLACE,
        SourceClass.COPY_TRADING_LEADERBOARD,
        SourceClass.ONLINE_SIGNAL_FEED,
        SourceClass.PUBLIC_STRATEGY_LIBRARY,
        SourceClass.THIRD_PARTY_BOT_PLATFORM,
    }
    records = [record for record in registry.list() if record.source_class in external]
    assert {record.source_id for record in records} == {
        "SRC-BINANCE-TRADING-BOTS",
        "SRC-BINANCE-COPY-TRADING",
        "SRC-TRADINGVIEW-IDEAS",
        "SRC-TRADINGVIEW-PUBLIC-STRATEGIES",
        "SRC-3COMMAS-DCA-BOT",
    }
    for record in records:
        assert record.canonical_publisher_url.startswith("https://")
        assert record.doi is None
        assert record.evidence_strength is EvidenceStrength.HYPOTHESIS_ONLY
        assert record.profit_claims_inherited is False
        assert record.locally_reproduced is False
        assert record.approval_eligible is False
        assert "approve" not in record.claim_summary.casefold()


def test_src_paper2_doi_is_corrected_without_changing_ambiguity_state(
    registry: ResearchSourceRegistry,
) -> None:
    source_record = yaml.safe_load((PAPER2_PATH / "source_record.yaml").read_text())
    assert source_record["url"] == "https://doi.org/10.1111/j.1540-6261.1990.tb05110.x"
    assert source_record["profit_claims_inherited"] is False
    assert registry.get("SRC-PAPER2").doi == "10.1111/j.1540-6261.1990.tb05110.x"
    assert "VALID_WITH_AMBIGUITIES" in (PAPER2_PATH / "reproduction_status.md").read_text()
    assert "NOT_REPRODUCED" in (PAPER2_PATH / "reproduction_status.md").read_text()
