"""T-011 acceptance checks: registry round-trip, null-harness end-to-end with
no credentials, no-network enforcement, and credential-gated real-provider
behavior (T-011-05 must raise rather than fabricate).
"""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from harness.pipeline import load_corpus, run_fixture, validate_output
from harness.provider import (
    PROVIDER_ENV_VARS,
    CredentialNotConfiguredError,
    NullProvider,
    RealProviderGate,
)
from registries.records import (
    RegistryError,
    load_registry,
    parse_agent,
    parse_model,
    parse_prompt,
)

BASE = Path(__file__).parent.parent
CORPUS_DIR = BASE / "fixtures" / "corpus"
SEED_DIR = BASE / "registries" / "seed"


def test_model_registry_round_trip() -> None:
    raw = json.loads((SEED_DIR / "models.json").read_text())
    records = load_registry(raw, parse_model)
    assert len(records) == len(raw)
    for rec, original in zip(records, raw, strict=True):
        assert rec.to_obj() == original
        assert len(rec.record_hash()) == 64  # sha256 hex


def test_agent_and_prompt_registries_round_trip() -> None:
    agents = load_registry(json.loads((SEED_DIR / "agents.json").read_text()), parse_agent)
    prompts = load_registry(json.loads((SEED_DIR / "prompts.json").read_text()), parse_prompt)
    assert agents and prompts
    for p in prompts:
        assert p.task_class in {f"T{i}" for i in range(1, 9)}
        assert len(p.template_hash()) == 64


def test_model_registry_rejects_bad_key() -> None:
    with pytest.raises(RegistryError):
        parse_model({"model_key": "not-a-valid-key"})


def test_fixture_manifest_hashes_match_files() -> None:
    manifest, items = load_corpus(CORPUS_DIR)
    assert len(items) == sum(manifest["counts"].values())
    for rel_path, fixture in items:
        digest = hashlib.sha256(
            (CORPUS_DIR / rel_path).read_bytes()
        ).hexdigest()
        assert digest == manifest["files"][rel_path]
        # every fixture round-trips through JSON unchanged (frozen corpus, no drift)
        assert json.loads(json.dumps(fixture, sort_keys=True)) == fixture


def test_null_provider_harness_runs_without_any_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in PROVIDER_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)
    manifest, items = load_corpus(CORPUS_DIR)
    provider = NullProvider()
    records = [
        run_fixture(rel_path, fixture, "corpus-hash", provider, "2026-07-07T00:00:00Z")
        for rel_path, fixture in items
    ]
    assert len(records) == len(items)
    assert all(rec["provider"] == "null" for rec in records)
    assert all(rec["cost_usd"] == 0.0 for rec in records)
    assert all(not rec["schema_errors"] for rec in records)


def test_null_provider_never_touches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("NullProvider must never open a network socket")

    monkeypatch.setattr(socket, "socket", _blocked)
    manifest, items = load_corpus(CORPUS_DIR)
    provider = NullProvider()
    for rel_path, fixture in items:
        run_fixture(rel_path, fixture, "corpus-hash", provider, "2026-07-07T00:00:00Z")


def test_validate_output_flags_missing_keys() -> None:
    assert validate_output("T1", {"label": "supported"}) == ["evidence_span"]
    assert validate_output("T1", {"label": "supported", "evidence_span": "x"}) == []


@pytest.mark.parametrize("provider", list(PROVIDER_ENV_VARS))
def test_real_provider_gate_never_fabricates_without_credential(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.delenv(PROVIDER_ENV_VARS[provider], raising=False)
    gate = RealProviderGate(provider)
    assert gate.is_configured() is False
    with pytest.raises(CredentialNotConfiguredError):
        gate.require_configured()


def test_real_provider_gate_passes_when_credential_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PROVIDER_ENV_VARS["anthropic"], "test-value-not-a-real-key")
    gate = RealProviderGate("anthropic")
    assert gate.is_configured() is True
    gate.require_configured()  # must not raise
