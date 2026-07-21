from pathlib import Path

import pytest

from tios.strategy.registry import (
    REGISTRY_PATH,
    list_versions,
    register,
    resolve,
    resolve_by_spec_hash,
    spec_sha256,
    unregistered_artifact_refs,
    verify_artifact_spec,
    version_id_for,
)

SPEC = {
    "strategy_id": "STRAT-TEST-DONCHIAN",
    "family": "breakout",
    "inputs": ["close", "high", "low"],
    "indicators": [
        {"name": "donchian", "parameters": {"lookback": 20}, "outputs": ["dc_upper", "dc_lower"]}
    ],
    "entry_long": {"all": ["close > dc_upper"]},
    "exit_long": {"all": ["close < dc_lower"]},
    "position_sizing": {"type": "all_in"},
    "risk": {"stop_loss": None, "take_profit": None, "execution_authority": "NONE"},
    "assumptions": ["fills at next open"],
    "ambiguities": [],
    "source_refs": ["TEST-FIXTURE"],
    "license_ref": "PROJECT-ORIGINAL-SPEC",
}


def test_registration_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    first = register(tmp_path, SPEC)
    second = register(tmp_path, SPEC)

    assert first.version_id == second.version_id
    assert first.version_id.startswith("SV-")
    assert len(list_versions(tmp_path)) == 1, "re-registering must not duplicate identity"


def test_changed_rules_produce_a_different_version(tmp_path: Path) -> None:
    """Identity derives from content, so a rule change cannot reuse an identity."""
    original = register(tmp_path, SPEC)
    widened = register(
        tmp_path,
        {
            **SPEC,
            "indicators": [
                {
                    "name": "donchian",
                    "parameters": {"lookback": 55},
                    "outputs": ["dc_upper", "dc_lower"],
                }
            ],
        },
    )

    assert original.version_id != widened.version_id
    assert len(list_versions(tmp_path)) == 2


def test_versions_resolve_by_id_and_by_spec_hash(tmp_path: Path) -> None:
    version = register(tmp_path, SPEC)

    assert resolve(tmp_path, version.version_id) == version
    assert resolve_by_spec_hash(tmp_path, version.canonical_spec_sha256) == version
    assert resolve(tmp_path, "SV-nonexistent") is None


def test_invalid_spec_cannot_be_registered(tmp_path: Path) -> None:
    """An unparseable specification must never acquire an identity."""
    with pytest.raises(Exception):  # noqa: B017 - SpecError type is internal to spec.py
        register(tmp_path, {"strategy_id": "not-a-valid-id", "family": "nope"})


def test_artifact_with_registered_spec_resolves(tmp_path: Path) -> None:
    version = register(tmp_path, SPEC)
    artifact = {
        "artifact_id": "ART-1",
        "strategy": {"canonical_spec_sha256": version.canonical_spec_sha256},
    }

    resolution = verify_artifact_spec(tmp_path, artifact)

    assert resolution.resolved
    assert resolution.version_id == version.version_id


def test_artifact_referencing_an_unregistered_strategy_is_blocked(tmp_path: Path) -> None:
    """The SUP-010 defect: a result citing a strategy with no resolvable identity."""
    artifact = {"artifact_id": "ART-1", "strategy": {"canonical_spec_sha256": "a" * 64}}

    resolution = verify_artifact_spec(tmp_path, artifact)

    assert not resolution.resolved
    assert "STRATEGY_VERSION_NOT_REGISTERED" in resolution.blockers


def test_artifact_without_a_spec_hash_is_blocked(tmp_path: Path) -> None:
    resolution = verify_artifact_spec(tmp_path, {"artifact_id": "ART-1", "strategy": {}})
    assert not resolution.resolved
    assert "CANONICAL_SPEC_HASH_MISSING" in resolution.blockers


def test_corrupt_registry_entry_is_detected(tmp_path: Path) -> None:
    """A registry that no longer re-hashes to its own identity cannot be trusted."""
    version = register(tmp_path, SPEC)
    target = tmp_path / REGISTRY_PATH
    tampered = target.read_text().replace('"lookback":20', '"lookback":99')
    target.write_text(tampered)

    resolution = verify_artifact_spec(
        tmp_path, {"strategy": {"canonical_spec_sha256": version.canonical_spec_sha256}}
    )

    assert not resolution.resolved
    assert "REGISTRY_ENTRY_CORRUPT" in resolution.blockers


def test_unregistered_artifact_refs_lists_offenders(tmp_path: Path) -> None:
    version = register(tmp_path, SPEC)
    known = version.canonical_spec_sha256
    artifacts = [
        {"artifact_id": "GOOD", "strategy": {"canonical_spec_sha256": known}},
        {"artifact_id": "BAD", "strategy": {"canonical_spec_sha256": "b" * 64}},
    ]

    assert unregistered_artifact_refs(tmp_path, artifacts) == ("BAD",)


def test_hash_is_stable_across_key_ordering() -> None:
    """Canonical serialization means construction order cannot change identity."""
    reordered = dict(reversed(list(SPEC.items())))
    assert version_id_for(SPEC) == version_id_for(reordered)
    assert spec_sha256(SPEC) == spec_sha256(reordered)


def test_shipped_specs_are_all_registered() -> None:
    """Every canonical spec in the repository must hold an immutable identity."""
    import yaml

    root = Path()
    spec_paths = sorted(root.glob("strategies/**/canonical_strategy_spec.yaml"))
    if not spec_paths:
        pytest.skip("no shipped specs in this checkout")

    registered = {version.strategy_id for version in list_versions(root)}
    for spec_path in spec_paths:
        strategy_id = yaml.safe_load(spec_path.read_text())["strategy_id"]
        assert strategy_id in registered, f"{strategy_id} has no registered version"
