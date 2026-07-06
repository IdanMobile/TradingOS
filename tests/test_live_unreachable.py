"""Live-state-unreachable placeholder (T-003-05, AD §AA, MODULE_CATALOG §11).

S1 placeholder: no code under src/tios may reference live-trading states or
live order execution. When the `approval` state machine lands, this file becomes
the forbidden-transition test (LIVE states must not be constructible/reachable).
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "tios"

FORBIDDEN = [
    re.compile(r"\bAPPROVED_LIVE\b", re.IGNORECASE),
    re.compile(r"\bLIVE_TRADING\b", re.IGNORECASE),
    re.compile(r"\bGO_LIVE\b", re.IGNORECASE),
    re.compile(r"withdraw", re.IGNORECASE),
]


def test_no_live_trading_states_in_source() -> None:
    hits = [
        f"{py.relative_to(SRC.parent)}: {p.pattern}"
        for py in SRC.rglob("*.py")
        for p in FORBIDDEN
        if p.search(py.read_text())
    ]
    assert hits == []


def test_placeholder_detects_planted_state() -> None:
    planted = "state = " + '"APPROVED_' + 'LIVE"'
    planted_mixed = "state = " + '"approved_' + 'Live"'
    assert any(p.search(planted) for p in FORBIDDEN)
    assert any(p.search(planted_mixed) for p in FORBIDDEN)
