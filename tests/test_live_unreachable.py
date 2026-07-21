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


def test_demo_preflight_is_read_only_and_cannot_place_an_order() -> None:
    """Preflight is network-reachable by design since D-104/D-105; it must stay read-only.

    This assertion replaces an earlier one requiring preflight to be network-quarantined.
    That quarantine was deliberately lifted by a recorded operator decision — stage-1
    read-only GETs were security-reviewed and preflight ran GREEN on the operator's demo
    key, which is impossible while quarantined. The test was not updated at the time.

    Asserting reachability alone would be a weaker guarantee than the one it replaces, so
    this checks the property that actually matters: preflight can read, and cannot write.
    A single write verb or order endpoint appearing here is the regression to catch.
    """
    source = (SCRIPTS / "demo_preflight.py").read_text()

    for write_endpoint in ("/v5/order/", "/v5/position/", "/asset/withdraw", "/asset/transfer"):
        assert write_endpoint not in source, f"preflight must not reach {write_endpoint}"

    # Every HTTP request it issues must be a GET.
    assert 'method="GET"' in source
    assert 'method="POST"' not in source
    assert "data=" not in source, "a request body implies a write"
