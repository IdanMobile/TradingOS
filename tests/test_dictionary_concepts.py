from __future__ import annotations

from pathlib import Path

import pytest

from tios.knowledge import (
    ConceptError,
    ConceptEvidenceStatus,
    ConceptFreshness,
    ConceptRecord,
    ConceptRegistry,
)


def test_dictionary_concepts_cover_bounded_s1_s2_terms_and_sources() -> None:
    root = Path(__file__).parents[1]
    registry = ConceptRegistry.load(root / "research/DICTIONARY_CONCEPTS_V1.json")
    records = registry.list()

    assert len(records) >= 12
    assert all(record.freshness is ConceptFreshness.CURRENT for record in records)
    assert all((root / source).is_file() for record in records for source in record.sources)
    assert {record.evidence_status for record in records} >= {
        ConceptEvidenceStatus.LOCAL_CONTRACT,
        ConceptEvidenceStatus.FIBO_PROVENANCE,
    }
    assert all(
        record.fibo_uri.startswith("https://spec.edmcouncil.org/fibo/")
        for record in records
        if record.evidence_status is ConceptEvidenceStatus.FIBO_PROVENANCE
    )
    assert registry.gaps()


def test_dictionary_concept_fts_resolves_aliases_and_contexts() -> None:
    root = Path(__file__).parents[1]
    registry = ConceptRegistry.load(root / "research/DICTIONARY_CONCEPTS_V1.json")

    assert registry.search('"canonical dataset"')[0].concept_id == "CON-DATASET"
    assert registry.search("approval")[0].concept_id in {
        "CON-APPROVAL-GATE",
        "CON-RISK-DECISION",
        "CON-VALIDATION-PACKAGE",
    }
    assert {record.concept_id for record in registry.search("venue")} >= {
        "CON-INERT-ORDER",
        "CON-JOB-SCHEDULE",
        "CON-RESEARCH-LAB-BATCH",
    }


def test_dictionary_concept_graph_and_parameter_guards() -> None:
    root = Path(__file__).parents[1]
    registry = ConceptRegistry.load(root / "research/DICTIONARY_CONCEPTS_V1.json")

    assert registry.get("CON-RESEARCH-ASSET").related == (
        "CON-EVIDENCE-RECORD",
        "CON-RESEARCH-SOURCE",
    )
    with pytest.raises(ConceptError, match="unknown concept"):
        registry.get("CON-MISSING")
    with pytest.raises(ConceptError, match="strategy parameter values"):
        ConceptRecord(
            concept_id="CON-BAD",
            canonical_name="Bad concept",
            abbreviations=(),
            aliases=(),
            definition="Stores fast=3 as a concept, which is forbidden.",
            category="strategy",
            market_contexts=(),
            venue_variants=(),
            related=(),
            sources=("docs/architecture/TYPE_AND_CONTRACT_CATALOG.md",),
            fibo_uri=None,
            examples=(),
            evidence_status=ConceptEvidenceStatus.LOCAL_CONTRACT,
            freshness=ConceptFreshness.CURRENT,
        )
