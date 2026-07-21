"""Read-only projection of the skills/ directory (agent skill specs)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TITLE_RE = re.compile(r"^#\s*Skill:\s*(.+?)\s*\(v(\d+)\)\s*$", re.MULTILINE)
_META_RE = re.compile(
    r"^Role:\s*(.+?)\s*·\s*Cost tier:\s*(.+?)\s*·\s*Status:\s*(.+)$", re.MULTILINE
)


def _section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_skill(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text()
    title_match = _TITLE_RE.search(text)
    meta_match = _META_RE.search(text)
    return {
        "skill_id": path.stem,
        "name": title_match.group(1) if title_match else path.stem,
        "version": title_match.group(2) if title_match else "1",
        "role": meta_match.group(1).strip() if meta_match else "—",
        "cost_tier": meta_match.group(2).strip() if meta_match else "—",
        "status": meta_match.group(3).strip() if meta_match else "—",
        "purpose": _section(text, "Purpose"),
        "trigger_conditions": _section(text, "Trigger conditions"),
        "when_not_to_use": _section(text, "When NOT to use"),
        "model_suitability": _section(text, "Model suitability"),
        "file": str(path.relative_to(root)),
    }


def build_skills(root: Path) -> dict[str, Any]:
    skills_dir = root / "skills"
    files = sorted(skills_dir.glob("SKILL_*.md")) if skills_dir.is_dir() else []
    skills = [_parse_skill(f, root) for f in files]
    return {
        "schema_version": 1,
        "skill_count": len(skills),
        "skills": skills,
    }
