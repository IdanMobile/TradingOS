"""Detect research artifacts whose code or data has moved underneath them.

`provenance.py` validates that an artifact *declares* complete lineage. It deliberately
reads no files, so a declaration can be perfectly well-formed while the modules it names
have since been rewritten. SUP-007 calls for the other half: making artifact/code mismatch
visible and failing on deliberate byte drift.

That is what this module does. Every substantive research artifact records
`code.module_sha256_by_path` — the exact bytes of every module that produced it. Re-hashing
those paths today answers a question no metadata check can: *would this result still
reproduce?*

The distinction matters because a stale artifact is not wrong, it is unverified. The
numbers were true for the code that produced them. Once that code changes, the artifact
becomes a historical record rather than a current claim, and any gate still counting it as
current evidence is overstating what is known.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.evidence.provenance import ARTIFACT_SCHEMA

SCHEMA_VERSION = 1
REPORT_PATH = Path("artifacts") / "evidence" / "ARTIFACT_STALENESS.json"

CURRENT = "CURRENT"
STALE = "STALE"
BROKEN = "BROKEN"


@dataclass(frozen=True)
class ModuleDrift:
    path: str
    declared_sha256: str
    observed_sha256: str | None  # None when the file no longer exists

    @property
    def missing(self) -> bool:
        return self.observed_sha256 is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "declared_sha256": self.declared_sha256,
            "observed_sha256": self.observed_sha256,
            "missing": self.missing,
        }


@dataclass(frozen=True)
class ArtifactStatus:
    artifact_path: str
    artifact_id: str
    state: str  # CURRENT | STALE | BROKEN
    generated_at: str
    git_commit: str
    drifted_modules: tuple[ModuleDrift, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_id": self.artifact_id,
            "state": self.state,
            "generated_at": self.generated_at,
            "git_commit": self.git_commit,
            "drifted_modules": [drift.as_dict() for drift in self.drifted_modules],
        }


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_research_artifacts(
    root: Path, subdir: str = "artifacts"
) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield every JSON artifact carrying the substantive-research schema."""
    for candidate in sorted((root / subdir).rglob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("artifact_schema") == ARTIFACT_SCHEMA:
            yield candidate, payload


def check_artifact(root: Path, artifact_path: Path, payload: Mapping[str, Any]) -> ArtifactStatus:
    """Re-hash every module an artifact names and classify the result."""
    code = payload.get("code") or {}
    by_path = code.get("module_sha256_by_path") or {}

    drifts: list[ModuleDrift] = []
    for module_path, declared in sorted(by_path.items()):
        observed = sha256_file(root / module_path)
        if observed != declared:
            drifts.append(ModuleDrift(module_path, str(declared), observed))

    if not by_path:
        # An artifact with no per-path map cannot be checked at all; that is itself a
        # provenance gap, not a pass.
        state = BROKEN
    elif any(drift.missing for drift in drifts):
        state = BROKEN
    elif drifts:
        state = STALE
    else:
        state = CURRENT

    return ArtifactStatus(
        artifact_path=str(artifact_path.relative_to(root)),
        artifact_id=str(payload.get("artifact_id", "")),
        state=state,
        generated_at=str(payload.get("generated_at", "")),
        git_commit=str(code.get("git_commit", "")),
        drifted_modules=tuple(drifts),
    )


def scan(root: Path, subdir: str = "artifacts") -> tuple[ArtifactStatus, ...]:
    return tuple(
        check_artifact(root, path, payload)
        for path, payload in iter_research_artifacts(root, subdir)
    )


def write_report(root: Path, statuses: tuple[ArtifactStatus, ...]) -> Path:
    counts = {
        state: sum(status.state == state for status in statuses)
        for state in (CURRENT, STALE, BROKEN)
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "artifact_count": len(statuses),
        "counts": counts,
        "interpretation": (
            "STALE artifacts were computed with code that has since changed. They remain "
            "historical records but must not be counted as current evidence for any gate "
            "without regeneration."
        ),
        "artifacts": [status.as_dict() for status in statuses],
    }
    target = root / REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def stale_artifact_refs(root: Path, subdir: str = "artifacts") -> tuple[str, ...]:
    """Artifact ids that must not be cited as current evidence."""
    return tuple(
        status.artifact_id for status in scan(root, subdir) if status.state in {STALE, BROKEN}
    )
