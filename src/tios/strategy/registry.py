"""Immutable strategy versions, content-addressed by their canonical specification.

SUP-010 found that the project's substantive research strategies — funding carry, stat-arb,
cross-sectional, MTF, combinations, generic public strategies — existed only as scripts and
artifacts. Their formulas, exits, sizing, invalidation conditions, and costs were never
versioned, so a result could reference "the strategy" without there being any fixed object
to reference. A candidate without a stable identity cannot be audited or promoted, because
there is nothing to audit or promote.

This registry gives every retained candidate that identity. A version id is the SHA-256 of
its canonical specification, so registration is idempotent, identity is derived from content
rather than assigned, and any change to the specification necessarily produces a different
version. Two artifacts claiming the same version id made the same claim about the same rules.

The enforcement point is `verify_artifact_spec`: an artifact's declared
`strategy.canonical_spec_sha256` must resolve to a registered version. Without it,
"we tested strategy X" is an unverifiable sentence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.strategy.spec import CanonicalStrategySpec, parse_spec

SCHEMA_VERSION = 1
REGISTRY_PATH = Path("artifacts") / "strategy_versions" / "registry.jsonl"


class RegistryError(RuntimeError):
    """Raised when a strategy version is malformed or cannot be resolved."""


@dataclass(frozen=True)
class StrategyVersion:
    version_id: str  # "SV-<sha256[:32]>"
    canonical_spec_sha256: str
    strategy_id: str
    family: str
    registered_at: str
    spec: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "version_id": self.version_id,
            "canonical_spec_sha256": self.canonical_spec_sha256,
            "strategy_id": self.strategy_id,
            "family": self.family,
            "registered_at": self.registered_at,
            "spec": self.spec,
        }


@dataclass(frozen=True)
class SpecResolution:
    resolved: bool
    declared_sha256: str
    version_id: str | None
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "declared_sha256": self.declared_sha256,
            "version_id": self.version_id,
            "blockers": list(self.blockers),
        }


def canonical_bytes(spec_obj: dict[str, Any]) -> bytes:
    """Deterministic serialization of a specification.

    Sorted keys and fixed separators mean the same rules always hash the same way,
    regardless of how the mapping was constructed or loaded.
    """
    return json.dumps(spec_obj, sort_keys=True, separators=(",", ":")).encode()


def spec_sha256(spec_obj: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(spec_obj)).hexdigest()


def version_id_for(spec_obj: dict[str, Any]) -> str:
    return f"SV-{spec_sha256(spec_obj)[:32]}"


def register(root: Path, spec: CanonicalStrategySpec | dict[str, Any]) -> StrategyVersion:
    """Register a canonical specification as an immutable version.

    Accepts a parsed spec or a raw mapping; a raw mapping is parsed first so an invalid
    specification cannot be registered. Registration is idempotent: re-registering the same
    rules returns the existing version rather than creating a duplicate identity.
    """
    if isinstance(spec, dict):
        parsed = parse_spec(spec)
    else:
        parsed = spec
    spec_obj = parsed.to_obj()

    digest = spec_sha256(spec_obj)
    version_id = version_id_for(spec_obj)

    existing = resolve(root, version_id)
    if existing is not None:
        return existing

    version = StrategyVersion(
        version_id=version_id,
        canonical_spec_sha256=digest,
        strategy_id=parsed.strategy_id,
        family=parsed.family,
        registered_at=datetime.now(tz=UTC).isoformat(),
        spec=spec_obj,
    )

    target = root / REGISTRY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(version.as_dict(), sort_keys=True, separators=(",", ":")) + "\n")
    return version


def list_versions(root: Path) -> tuple[StrategyVersion, ...]:
    target = root / REGISTRY_PATH
    if not target.is_file():
        return ()
    versions: list[StrategyVersion] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        versions.append(
            StrategyVersion(
                version_id=payload["version_id"],
                canonical_spec_sha256=payload["canonical_spec_sha256"],
                strategy_id=payload["strategy_id"],
                family=payload["family"],
                registered_at=payload["registered_at"],
                spec=payload["spec"],
            )
        )
    return tuple(versions)


def resolve(root: Path, version_id: str) -> StrategyVersion | None:
    for version in list_versions(root):
        if version.version_id == version_id:
            return version
    return None


def resolve_by_spec_hash(root: Path, canonical_spec_sha256: str) -> StrategyVersion | None:
    for version in list_versions(root):
        if version.canonical_spec_sha256 == canonical_spec_sha256:
            return version
    return None


def verify_artifact_spec(root: Path, artifact_metadata: dict[str, Any]) -> SpecResolution:
    """Check that an artifact's declared strategy resolves to a registered version.

    This is what makes "we tested strategy X" a verifiable statement: the artifact declares
    a spec hash, and that hash must correspond to rules someone can read back.
    """
    strategy = artifact_metadata.get("strategy") or {}
    declared = strategy.get("canonical_spec_sha256")

    if not isinstance(declared, str) or not declared.strip():
        return SpecResolution(False, "", None, ("CANONICAL_SPEC_HASH_MISSING",))

    version = resolve_by_spec_hash(root, declared)
    if version is None:
        return SpecResolution(
            False,
            declared,
            None,
            ("STRATEGY_VERSION_NOT_REGISTERED",),
        )

    # A registered version must re-hash to its own declared identity, or the registry
    # itself has drifted and can no longer be trusted to resolve anything.
    if spec_sha256(version.spec) != version.canonical_spec_sha256:
        return SpecResolution(False, declared, version.version_id, ("REGISTRY_ENTRY_CORRUPT",))

    return SpecResolution(True, declared, version.version_id, ())


def unregistered_artifact_refs(root: Path, artifacts: list[dict[str, Any]]) -> tuple[str, ...]:
    """Artifact ids whose strategy cannot be resolved to a registered version."""
    return tuple(
        str(artifact.get("artifact_id", ""))
        for artifact in artifacts
        if not verify_artifact_spec(root, artifact).resolved
    )
