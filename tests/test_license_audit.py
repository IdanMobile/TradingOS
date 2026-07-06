"""License-compatibility audit (T-018-03, REQ-054, AD-02).

The core venv (src/tios runtime deps) must stay free of GPL/AGPL code — GPL
engines (Freqtrade) are subprocess-isolated in engines/, never linked. LGPL is
flagged for review (allowed dynamically-linked, but must be a conscious call).
"""

from importlib.metadata import distributions

FORBIDDEN_FRAGMENTS = ("GNU GENERAL PUBLIC", "GPL-2", "GPL-3", "AGPL", "GPLV2", "GPLV3")
REVIEW_FRAGMENTS = ("LGPL", "LESSER GENERAL PUBLIC")
# LGPL deps consciously accepted after review (none yet)
LGPL_ALLOWLIST: frozenset[str] = frozenset()


def license_of(dist_metadata: dict[str, str], classifiers: list[str]) -> str:
    parts = [dist_metadata.get("License-Expression", ""), dist_metadata.get("License", "")]
    parts += [c for c in classifiers if c.startswith("License ::")]
    return " | ".join(p for p in parts if p)


def classify(name: str, license_text: str) -> str | None:
    """Return a violation string or None. AGPL/GPL forbidden; LGPL needs allowlisting."""
    up = license_text.upper()
    if "LGPL" in up or "LESSER GENERAL PUBLIC" in up:
        return None if name.lower() in LGPL_ALLOWLIST else f"{name}: LGPL requires review"
    if any(f in up for f in FORBIDDEN_FRAGMENTS):
        return f"{name}: forbidden copyleft license in core venv ({license_text[:80]})"
    return None


def test_core_venv_has_no_copyleft() -> None:
    violations = []
    for dist in distributions():
        name = dist.metadata["Name"] or "?"
        classifiers = [v for k, v in dist.metadata.items() if k == "Classifier"]
        v = classify(name, license_of(dict(dist.metadata), classifiers))
        if v:
            violations.append(v)
    assert violations == []


def test_planted_agpl_is_flagged() -> None:
    """Prove the checker can fail (T-018-03 acceptance)."""
    assert classify("evil-dep", "AGPL-3.0-only") is not None
    assert classify("evil-dep", "GNU General Public License v3 (GPLv3)") is not None
    assert classify("sneaky-dep", "GNU Lesser General Public License") is not None
    assert classify("fine-dep", "Apache-2.0") is None
    assert classify("fine-dep", "MIT License") is None
