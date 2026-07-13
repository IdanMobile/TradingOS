"""Fail-closed metadata contract for substantive strategy-research artifacts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta

ARTIFACT_SCHEMA = "tios.substantive_strategy_research.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


class ProvenanceError(ValueError):
    """Raised when research metadata is incomplete or unsafe."""


def _mapping(value: object, name: str, errors: list[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        errors.append(f"{name} must be a mapping")
        return {}
    return value


def _text(value: object, name: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")
        return ""
    return value


def _hash(value: object, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        errors.append(f"{name} must be a lowercase SHA-256")


def _utc_time(value: object, name: str, errors: list[str]) -> datetime | None:
    text = _text(value, name, errors)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{name} must be an ISO-8601 timestamp")
        return None
    if parsed.utcoffset() != timedelta(0):
        errors.append(f"{name} must be UTC")
        return None
    return parsed


def validate_substantive_research_metadata(metadata: Mapping[str, object]) -> None:
    """Validate declared lineage without reading files or rewriting legacy artifacts.

    ``output_sha256`` identifies the substantive output outside this metadata envelope.
    Validation succeeds by returning ``None`` and otherwise raises ``ProvenanceError``.
    """

    errors: list[str] = []
    if metadata.get("artifact_schema") != ARTIFACT_SCHEMA:
        errors.append(f"artifact_schema must be {ARTIFACT_SCHEMA}")
    _text(metadata.get("artifact_id"), "artifact_id", errors)
    _utc_time(metadata.get("generated_at"), "generated_at", errors)

    code = _mapping(metadata.get("code"), "code", errors)
    commit = code.get("git_commit")
    if not isinstance(commit, str) or _GIT_COMMIT.fullmatch(commit) is None:
        errors.append("code.git_commit must be a full lowercase Git commit hash")
    if type(code.get("dirty")) is not bool:
        errors.append("code.dirty must be a boolean")
    _hash(code.get("module_sha256"), "code.module_sha256", errors)

    dataset = _mapping(metadata.get("dataset"), "dataset", errors)
    _text(dataset.get("dataset_id"), "dataset.dataset_id", errors)
    _hash(dataset.get("data_sha256"), "dataset.data_sha256", errors)
    _hash(dataset.get("manifest_sha256"), "dataset.manifest_sha256", errors)
    start = _utc_time(dataset.get("range_start"), "dataset.range_start", errors)
    end = _utc_time(dataset.get("range_end"), "dataset.range_end", errors)
    if start is not None and end is not None and start > end:
        errors.append("dataset range_start must not be after range_end")

    strategy = _mapping(metadata.get("strategy"), "strategy", errors)
    _hash(strategy.get("canonical_spec_sha256"), "strategy.canonical_spec_sha256", errors)
    if not isinstance(strategy.get("parameters"), Mapping):
        errors.append("strategy.parameters must be a mapping")
    _text(strategy.get("search_campaign_ref"), "strategy.search_campaign_ref", errors)

    method = _mapping(metadata.get("method"), "method", errors)
    cost_model = method.get("cost_model")
    if not isinstance(cost_model, Mapping) or not cost_model:
        errors.append("method.cost_model must be a non-empty mapping")
    split = method.get("split")
    if not isinstance(split, Mapping) or not split:
        errors.append("method.split must be a non-empty mapping")
    _text(method.get("selection_metric"), "method.selection_metric", errors)
    _text(
        method.get("all_trials_population_ref"),
        "method.all_trials_population_ref",
        errors,
    )

    _hash(metadata.get("output_sha256"), "output_sha256", errors)
    if metadata.get("execution_authority") != "NONE":
        errors.append("execution_authority must be NONE")
    if metadata.get("promotion_eligible") is not False:
        errors.append("promotion_eligible must be false")

    if errors:
        raise ProvenanceError("; ".join(errors))
