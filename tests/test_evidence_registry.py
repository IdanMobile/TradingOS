from pathlib import Path

import pytest

from tios.evidence import EvidenceError, EvidenceRecord, EvidenceRegistry


def _record() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="EV-001",
        hypothesis_id="HYP-001",
        strategy_version_id="STRAT-001",
        market="crypto_spot",
        instrument="BTC/USDT",
        timeframe="15m",
        run_ref="RUN-mlflow-public-001",
        dataset_ref="DS-dvc-public-001",
    )


def test_record_links_domain_semantics_to_replaceable_public_refs(tmp_path: Path) -> None:
    registry = EvidenceRegistry(tmp_path / "trading_evidence.jsonl")
    registry.add(_record())

    loaded = registry.get("EV-001")
    assert loaded == _record()
    assert loaded.to_dict()["run_ref"] == "RUN-mlflow-public-001"
    assert loaded.to_dict()["dataset_ref"] == "DS-dvc-public-001"


def test_registry_is_append_only_and_unvalidated_cannot_be_eligible(tmp_path: Path) -> None:
    registry = EvidenceRegistry(tmp_path / "trading_evidence.jsonl")
    registry.add(_record())
    before = registry.path.read_bytes()
    with pytest.raises(EvidenceError, match="already exists"):
        registry.add(_record())
    assert registry.path.read_bytes() == before

    with pytest.raises(EvidenceError, match="NOT_ELIGIBLE"):
        EvidenceRecord(**{**_record().to_dict(), "approval_state": "ELIGIBLE"})


def test_record_rejects_whitespace_in_external_refs() -> None:
    with pytest.raises(EvidenceError, match="stable reference"):
        EvidenceRecord(**{**_record().to_dict(), "run_ref": "internal run id"})
