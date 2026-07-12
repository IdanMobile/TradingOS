"""Read-only local registry and artifact search for the dashboard."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.knowledge import ConceptError, ConceptRegistry
from tios.research_assets import (
    ResearchAssetError,
    ResearchAssetRegistry,
    ResearchSourceError,
    ResearchSourceRegistry,
)

MAX_QUERY_CHARS = 120
DEFAULT_LIMIT = 25
MAX_LIMIT = 50


@dataclass(frozen=True)
class SearchDocument:
    kind: str
    identifier: str
    title: str
    summary: str
    path: str
    status: str
    text: str


def _terms(query: str) -> tuple[str, ...]:
    clean = query.strip()
    if len(clean) > MAX_QUERY_CHARS:
        raise ValueError(f"query must be {MAX_QUERY_CHARS} characters or fewer")
    return tuple(term.casefold() for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", clean))


def _score(document: SearchDocument, terms: tuple[str, ...]) -> int:
    if not terms:
        return 0
    identifier = document.identifier.casefold()
    title = document.title.casefold()
    summary = document.summary.casefold()
    text = document.text.casefold()
    score = 0
    for term in terms:
        if term == identifier:
            score += 80
        if term in identifier:
            score += 45
        if term in title:
            score += 35
        if term in summary:
            score += 20
        if term in text:
            score += 8
    if all(term in text for term in terms):
        score += 15
    return score


def _snippet(text: str, terms: tuple[str, ...]) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    lowered = compact.casefold()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(0, min(positions) - 80) if positions else 0
    snippet = compact[start : start + 220].strip()
    return f"...{snippet}" if start else snippet


def _first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("#"):
            return clean.lstrip("#").strip() or fallback
    return fallback


def _read_text(path: Path, max_chars: int = 20_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _concept_documents(root: Path) -> list[SearchDocument]:
    path = root / "research" / "DICTIONARY_CONCEPTS_V1.json"
    try:
        registry = ConceptRegistry.load(path)
    except (OSError, ConceptError):
        return []
    rel = str(path.relative_to(root))
    return [
        SearchDocument(
            kind="concept",
            identifier=record.concept_id,
            title=record.canonical_name,
            summary=record.definition,
            path=rel,
            status=record.freshness.value,
            text=" ".join(
                (
                    record.concept_id,
                    record.canonical_name,
                    *record.abbreviations,
                    *record.aliases,
                    record.definition,
                    record.category,
                    *record.market_contexts,
                    *record.venue_variants,
                    *record.sources,
                )
            ),
        )
        for record in registry.list()
    ]


def _research_asset_documents(root: Path) -> list[SearchDocument]:
    path = root / "research" / "RESEARCH_ASSETS_V1.json"
    try:
        registry = ResearchAssetRegistry.load(path)
    except (OSError, ResearchAssetError):
        return []
    rel = str(path.relative_to(root))
    return [
        SearchDocument(
            kind="research_asset",
            identifier=record.asset_id,
            title=record.title,
            summary=record.question,
            path=rel,
            status=record.freshness.value,
            text=" ".join(
                (
                    record.asset_id,
                    record.title,
                    record.question,
                    record.creator,
                    *record.sources,
                    *record.quality_score_refs,
                    *record.consumers,
                    record.reverify_trigger,
                )
            ),
        )
        for record in registry.list()
    ]


def _research_source_documents(root: Path) -> list[SearchDocument]:
    path = root / "research" / "PRIMARY_STRATEGY_RESEARCH_SOURCES_V1.yaml"
    try:
        registry = ResearchSourceRegistry.load(path)
    except (OSError, ResearchSourceError):
        return []
    rel = str(path.relative_to(root))
    return [
        SearchDocument(
            kind="research_source",
            identifier=record.source_id,
            title=record.title,
            summary=record.claim_summary,
            path=rel,
            status=record.evidence_strength.value,
            text=" ".join(
                (
                    record.source_id,
                    record.title,
                    *record.authors,
                    record.publication,
                    record.claim_summary,
                    record.source_class.value,
                    *[family.value for family in record.hypothesis_families],
                    record.reverify_trigger,
                )
            ),
        )
        for record in registry.list()
    ]


def _strategy_documents(root: Path) -> list[SearchDocument]:
    documents: list[SearchDocument] = []
    for path in sorted(root.glob("strategies/*/*/reproduction_status.md")):
        if not path.is_file():
            continue
        text = _read_text(path)
        status_match = re.search(r"(?:\*\*Status\*\*|Status):\s*\*?\*?([^*\n]+)", text)
        status = status_match.group(1).strip() if status_match else "UNKNOWN"
        strategy_id = path.parent.name
        spec = path.parent / "canonical_strategy_spec.yaml"
        spec_text = _read_text(spec, max_chars=8_000)
        id_match = re.search(r"^strategy_id:\s*([^\n]+)$", spec_text, re.MULTILINE)
        identifier = id_match.group(1).strip() if id_match else strategy_id
        documents.append(
            SearchDocument(
                kind="strategy",
                identifier=identifier,
                title=strategy_id,
                summary=status,
                path=str(path.relative_to(root)),
                status=status,
                text=f"{identifier} {strategy_id} {status} {text} {spec_text}",
            )
        )
    return documents


def _tradingview_candidate_documents(root: Path) -> list[SearchDocument]:
    path = (
        root / "artifacts/source_intake/tradingview_public_strategies/"
        "selected_candidates_2026_07_11.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return []
    rel = str(path.relative_to(root))
    documents = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get("candidate_id", ""))
        title = str(candidate.get("title", ""))
        family = str(candidate.get("family", ""))
        why = str(candidate.get("why_selected", ""))
        documents.append(
            SearchDocument(
                kind="tradingview_candidate",
                identifier=identifier,
                title=title,
                summary=why,
                path=rel,
                status=str(candidate.get("tester_status", "PENDING")),
                text=" ".join(
                    (
                        identifier,
                        title,
                        str(candidate.get("author", "")),
                        str(candidate.get("canonical_url", "")),
                        family,
                        why,
                        " ".join(str(step) for step in candidate.get("next_steps", [])),
                    )
                ),
            )
        )
    return documents


def _report_documents(root: Path) -> list[SearchDocument]:
    documents: list[SearchDocument] = []
    for path in sorted((root / "artifacts" / "reports").glob("*.md")):
        if not path.is_file():
            continue
        text = _read_text(path)
        title = _first_heading(text, path.stem.replace("_", " ").title())
        documents.append(
            SearchDocument(
                kind="report",
                identifier=path.stem,
                title=title,
                summary=_snippet(text, ()),
                path=str(path.relative_to(root)),
                status="RETAINED",
                text=f"{path.stem} {title} {text}",
            )
        )
    return documents


def _documents(root: Path) -> list[SearchDocument]:
    return [
        *_concept_documents(root),
        *_research_asset_documents(root),
        *_research_source_documents(root),
        *_strategy_documents(root),
        *_tradingview_candidate_documents(root),
        *_report_documents(root),
    ]


def build_search_results(
    root: Path | None = None,
    query: str = "",
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Search local registries and retained reports without mutating the workspace."""
    root = root or Path(__file__).resolve().parents[4]
    if limit < 1:
        raise ValueError("limit must be at least 1")
    limit = min(limit, MAX_LIMIT)
    terms = _terms(query)
    scored = [
        (score, document) for document in _documents(root) if (score := _score(document, terms)) > 0
    ]
    scored.sort(key=lambda item: (-item[0], item[1].kind, item[1].identifier))
    rows = [
        {
            "kind": document.kind,
            "id": document.identifier,
            "title": document.title,
            "summary": document.summary,
            "path": document.path,
            "status": document.status,
            "score": score,
            "snippet": _snippet(document.text, terms),
        }
        for score, document in scored[:limit]
    ]
    by_kind: dict[str, int] = {}
    for row in rows:
        kind = str(row["kind"])
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "query": query.strip(),
        "mode": "LOCAL_READ_ONLY",
        "capabilities": {
            "writes": "DISABLED",
            "credential_access": "ABSENT",
            "order_endpoint": "ABSENT",
            "venue_connection": "NONE",
            "execution_authority": "NONE",
        },
        "counts": {
            "returned": len(rows),
            "by_kind": dict(sorted(by_kind.items())),
        },
        "results": rows,
    }
