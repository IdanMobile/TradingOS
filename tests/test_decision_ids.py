"""Decision-ID uniqueness check (REQ-032, D-031): every `### D-NNN` heading unique."""

import re
from collections import Counter
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "DECISION_LOG.md"
HEADING = re.compile(r"^### (D-\d{3})\b", re.MULTILINE)


def duplicate_ids(text: str) -> list[str]:
    counts = Counter(HEADING.findall(text))
    return sorted(i for i, n in counts.items() if n > 1)


def test_decision_ids_unique() -> None:
    assert duplicate_ids(LOG.read_text()) == []


def test_checker_detects_duplicates() -> None:
    assert duplicate_ids("### D-001 — a\n### D-002 — b\n### D-001 — c\n") == ["D-001"]
