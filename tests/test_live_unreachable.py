"""Repository-level live/demo reachability guard."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "tios"
ROOT = SRC.parents[1]
SCRIPTS = ROOT / "scripts"

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


def test_authenticated_order_endpoint_exists_only_in_quarantined_transport() -> None:
    hits = [
        path.relative_to(ROOT)
        for tree in (SRC, SCRIPTS)
        for path in tree.rglob("*.py")
        if "/v5/order/create" in path.read_text()
    ]
    assert hits == [Path("scripts/demo_roundtrip.py")]
    assert (
        "raise RuntimeError(pf.NETWORK_QUARANTINE)" in (SCRIPTS / "demo_roundtrip.py").read_text()
    )
    assert "raise RuntimeError(NETWORK_QUARANTINE)" in (SCRIPTS / "demo_preflight.py").read_text()
