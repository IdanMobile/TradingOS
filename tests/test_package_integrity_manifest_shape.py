"""The package verifier must never silently skip a malformed Path/SHA row."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "PACKAGE_INTEGRITY_MANIFEST.md"
TABLE_HEADER = "| Path | SHA-256 |"
TABLE_DELIMITER = "|---|---|"
STRICT_ROW = re.compile(r"\| `([^`\r\n]+)` \| `([a-f0-9]{64})` \|\Z")


def _candidate_rows(text: str) -> list[str]:
    """Discover data lines by table structure, before trusting cell syntax."""
    lines = text.splitlines()
    candidates: list[str] = []
    header_count = 0
    for index, line in enumerate(lines):
        if line != TABLE_HEADER:
            continue
        header_count += 1
        assert index + 1 < len(lines), "Path/SHA table is missing its delimiter"
        assert lines[index + 1] == TABLE_DELIMITER, "Path/SHA table delimiter is malformed"
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].startswith("|"):
            candidates.append(lines[cursor])
            cursor += 1
    assert header_count, "package manifest contains no Path/SHA tables"
    return candidates


def _strict_rows(text: str) -> list[tuple[str, str]]:
    candidates = _candidate_rows(text)
    parsed: list[tuple[str, str]] = []
    malformed: list[str] = []
    for row in candidates:
        match = STRICT_ROW.fullmatch(row)
        if match is None:
            malformed.append(row)
        else:
            parsed.append((match.group(1), match.group(2)))
    assert not malformed, f"malformed package-integrity rows: {malformed}"
    assert len(parsed) == len(candidates), "strict verifier silently skipped a Path/SHA row"
    return parsed


def test_every_manifest_path_sha_row_is_strict_and_verified() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    rows = _strict_rows(text)

    mismatches: list[str] = []
    for path, expected_digest in rows:
        referenced = ROOT / path
        if not referenced.is_file():
            mismatches.append(f"{path}: missing")
            continue
        actual_digest = hashlib.sha256(referenced.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            mismatches.append(f"{path}: expected {expected_digest}, got {actual_digest}")
    assert not mismatches, "package-integrity mismatches: " + "; ".join(mismatches)

    malformed_rows = (
        f"| `example.txt` | `{'a' * 64} |",
        f"| `example.txt` | `{'a' * 64}`",
    )
    for malformed_row in malformed_rows:
        synthetic = "\n".join((TABLE_HEADER, TABLE_DELIMITER, malformed_row))
        assert _candidate_rows(synthetic) == [malformed_row]
        with pytest.raises(AssertionError, match="malformed package-integrity rows"):
            _strict_rows(synthetic)
