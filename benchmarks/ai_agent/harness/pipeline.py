"""Fixtures -> prompt assembly -> schema validation -> scoring plumbing (T-011-03).

Provenance fields on each run record follow
specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md's "Provenance requirements" list.
`evaluator_results` is intentionally empty for the null provider: there is
nothing real to score, and scoring plumbing must not fabricate a verdict.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from harness.provider import NullProvider, ProviderResponse

# Required output keys per task class, matching NullProvider._STUBS and the
# suite spec's "Output" line for each Tn.
TASK_SCHEMAS: dict[str, tuple[str, ...]] = {
    "T1": ("label", "evidence_span"),
    "T2": ("family", "entry_rule", "exit_rule", "ambiguities"),
    "T3": ("mismatches",),
    "T4": ("plan",),
    "T5": ("failure_modes", "recommended_tests"),
    "T6": ("matrix", "decision"),
    "T7": ("concepts",),
    "T8": ("asset", "contradictions"),
}

_GROUP_TO_TASK_CLASS = {
    "t1_source_verification": "T1",
    "t2_strategy_extraction": "T2",
    "t3_semantic_review": "T3",
    "t4_backtest_plan": "T4",
    "t5_redteam_critique": "T5",
    "t6_tool_comparison": "T6",
    "t7_dictionary_ontology": "T7",
    "t8_research_synthesis": "T8",
}


def task_class_for_fixture_path(rel_path: str) -> str:
    group = rel_path.split("/", 1)[0]
    try:
        return _GROUP_TO_TASK_CLASS[group]
    except KeyError as e:
        raise ValueError(f"fixture path {rel_path!r} has no known task-class group") from e


def assemble_prompt(task_class: str, fixture: dict[str, Any]) -> str:
    """Deterministic, human-readable prompt text (no external template engine needed)."""
    return f"[{task_class}] " + json.dumps(fixture, sort_keys=True)


def validate_output(task_class: str, output: dict[str, Any]) -> list[str]:
    required = TASK_SCHEMAS.get(task_class)
    if required is None:
        return [f"unknown task_class {task_class!r}"]
    return [key for key in required if key not in output]


def _context_hash(fixture: dict[str, Any]) -> str:
    canonical = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_fixture(
    rel_path: str,
    fixture: dict[str, Any],
    corpus_hash: str,
    provider: NullProvider,
    timestamp: str,
) -> dict[str, Any]:
    """Run one fixture through the pipeline and return a fully-provenanced run record."""
    task_class = task_class_for_fixture_path(rel_path)
    prompt = assemble_prompt(task_class, fixture)
    response: ProviderResponse = provider.call(task_class, prompt)
    schema_errors = validate_output(task_class, response.raw_output)
    return {
        "task_id": fixture.get("id", rel_path),
        "task_class": task_class,
        "fixture_path": rel_path,
        "model_identifier": response.model_identifier,
        "provider": response.provider,
        "agent_key": "AGT-null-selfcheck",
        "prompt_key": f"PRM-{task_class.lower()}",
        "tool_versions": {},
        "source_corpus_hash": corpus_hash,
        "context_package_hash": _context_hash(fixture),
        "timestamp": timestamp,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
        "raw_output": response.raw_output,
        "normalized_output": response.raw_output,
        "schema_errors": schema_errors,
        "evaluator_results": {},
        "downstream_links": [],
    }


def load_corpus(corpus_dir: Path) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    manifest = json.loads((corpus_dir / "manifest.json").read_text())
    items = []
    for rel_path in sorted(manifest["files"]):
        fixture = json.loads((corpus_dir / rel_path).read_text())
        items.append((rel_path, fixture))
    return manifest, items
