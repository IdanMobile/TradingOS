from copy import deepcopy

import pytest

from tios.evidence import (
    ARTIFACT_SCHEMA,
    ProvenanceError,
    validate_substantive_research_metadata,
)

HASH = "a" * 64


def _metadata() -> dict[str, object]:
    return {
        "artifact_schema": ARTIFACT_SCHEMA,
        "artifact_id": "ART-2026-07-13-001",
        "generated_at": "2026-07-13T04:00:00Z",
        "code": {"git_commit": "b" * 40, "dirty": True, "module_sha256": HASH},
        "dataset": {
            "dataset_id": "DS-BTCUSDT-1H-2026-07-12",
            "data_sha256": HASH,
            "manifest_sha256": HASH,
            "range_start": "2020-01-01T00:00:00Z",
            "range_end": "2026-07-12T23:00:00Z",
        },
        "strategy": {
            "canonical_spec_sha256": HASH,
            "parameters": {"lookback": 20},
            "search_campaign_ref": "SEARCH-2026-07-13-001",
        },
        "method": {
            "cost_model": {"fee_bps": 10, "slippage_bps": 5},
            "split": {"train": "2020/2023", "validation": "2024", "holdout": "2025/2026"},
            "selection_metric": "validation_sharpe_net_costs",
            "all_trials_population_ref": "artifacts/search/SEARCH-2026-07-13-001.jsonl",
        },
        "output_sha256": HASH,
        "execution_authority": "NONE",
        "promotion_eligible": False,
    }


def test_complete_research_metadata_passes() -> None:
    assert validate_substantive_research_metadata(_metadata()) is None


@pytest.mark.parametrize(
    ("section", "field"),
    [
        (None, "artifact_schema"),
        (None, "artifact_id"),
        (None, "generated_at"),
        ("code", "git_commit"),
        ("code", "dirty"),
        ("code", "module_sha256"),
        ("dataset", "dataset_id"),
        ("dataset", "data_sha256"),
        ("dataset", "manifest_sha256"),
        ("dataset", "range_start"),
        ("dataset", "range_end"),
        ("strategy", "canonical_spec_sha256"),
        ("strategy", "parameters"),
        ("strategy", "search_campaign_ref"),
        ("method", "cost_model"),
        ("method", "split"),
        ("method", "selection_metric"),
        ("method", "all_trials_population_ref"),
        (None, "output_sha256"),
    ],
)
def test_missing_required_lineage_fails_closed(section: str | None, field: str) -> None:
    metadata = deepcopy(_metadata())
    target = metadata if section is None else metadata[section]
    assert isinstance(target, dict)
    target.pop(field)

    with pytest.raises(ProvenanceError, match=field):
        validate_substantive_research_metadata(metadata)


@pytest.mark.parametrize(
    ("field", "value"),
    [("execution_authority", "PAPER"), ("promotion_eligible", True)],
)
def test_metadata_cannot_grant_execution_or_promotion(field: str, value: object) -> None:
    metadata = _metadata()
    metadata[field] = value

    with pytest.raises(ProvenanceError, match=field):
        validate_substantive_research_metadata(metadata)


def test_invalid_time_range_and_empty_method_declarations_fail() -> None:
    metadata = _metadata()
    dataset = metadata["dataset"]
    method = metadata["method"]
    assert isinstance(dataset, dict) and isinstance(method, dict)
    dataset["range_start"] = "2026-07-13T00:00:00Z"
    dataset["range_end"] = "2026-07-12T00:00:00Z"
    method["cost_model"] = {}

    with pytest.raises(ProvenanceError) as caught:
        validate_substantive_research_metadata(metadata)
    assert "range_start" in str(caught.value)
    assert "cost_model" in str(caught.value)
