"""Offline checks for the Bybit demo preflight (no network, no real key, no orders)."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_preflight as pf  # noqa: E402

KEY, SECRET, TS = "demo-key", "demo-secret", "1700000000000"


def _transport(query_api: dict, wallet: dict) -> Callable[[str, dict[str, str]], bytes]:
    def transport(url: str, headers: dict[str, str]) -> bytes:
        # The signature header must be present and correct for the query string in the URL.
        assert headers["X-BAPI-API-KEY"] == KEY
        payload = url.split("?", 1)[1] if "?" in url else ""
        assert headers["X-BAPI-SIGN"] == pf.sign(SECRET, headers["X-BAPI-TIMESTAMP"], KEY, payload)
        body = wallet if "wallet-balance" in url else query_api
        return json.dumps(body).encode()

    return transport


def test_sign_matches_independent_hmac() -> None:
    expected = hmac.new(
        SECRET.encode(), f"{TS}{KEY}{pf.RECV_WINDOW}accountType=UNIFIED".encode(), hashlib.sha256
    ).hexdigest()
    assert pf.sign(SECRET, TS, KEY, "accountType=UNIFIED") == expected


def test_preflight_refuses_non_demo_host() -> None:
    with pytest.raises(ValueError, match="non-demo host"):
        pf.preflight(_transport({}, {}), KEY, SECRET, base="https://api.bybit.com")
    with pytest.raises(ValueError, match="non-demo host"):
        pf.preflight(_transport({}, {}), KEY, SECRET, base="https://api-demo.bybit.com.evil.test")


def test_trade_only_key_is_safe() -> None:
    query_api = {
        "retCode": 0,
        "result": {
            "readOnly": 0,
            "permissions": {"Spot": ["SpotTrade"], "Derivatives": ["DerivativesTrade"]},
        },
    }
    wallet = {
        "retCode": 0,
        "result": {"list": [{"coin": [{"coin": "USDT", "walletBalance": "50000"}]}]},
    }
    report = pf.preflight(_transport(query_api, wallet), KEY, SECRET, timestamp=TS)
    assert report["ok"] is True
    assert report["can_trade"] is True
    assert report["fund_removal_enabled"] is False
    assert report["balances"] == {"USDT": "50000"}


def test_withdrawal_capable_key_is_flagged_unsafe() -> None:
    query_api = {
        "retCode": 0,
        "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"], "Wallet": ["Withdraw"]}},
    }
    report = pf.preflight(_transport(query_api, {"retCode": 0}), KEY, SECRET, timestamp=TS)
    assert report["ok"] is False
    assert report["fund_removal_enabled"] is True
    assert "UNSAFE" in report["note"]


def test_auth_failure_reports_cleanly() -> None:
    report = pf.preflight(
        _transport({"retCode": 10003, "retMsg": "invalid api key"}, {}), KEY, SECRET, timestamp=TS
    )
    assert report["ok"] is False and report["stage"] == "auth"


def test_preflight_requires_trade_permission_and_wallet_success() -> None:
    read_only = {"retCode": 0, "result": {"readOnly": 1, "permissions": {}}}
    report = pf.preflight(_transport(read_only, {"retCode": 0}), KEY, SECRET, timestamp=TS)
    assert report["ok"] is False and report["can_trade"] is False

    trade = {"retCode": 0, "result": {"readOnly": 0, "permissions": {"Spot": ["SpotTrade"]}}}
    report = pf.preflight(_transport(trade, {"retCode": 10001}), KEY, SECRET, timestamp=TS)
    assert report["ok"] is False and report["wallet_ok"] is False


def test_load_dotenv_fills_unset_and_respects_existing(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nBYBIT_DEMO_API_KEY='k1'\n"
        "export BYBIT_DEMO_API_SECRET = s1\nOPENAI_API_KEY=must-not-load\n"
    )
    monkeypatch.delenv("BYBIT_DEMO_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "already-set")
    pf.load_dotenv(env)
    assert pf._first(pf.KEY_NAMES) == "k1"
    assert pf._first(pf.SECRET_NAMES) == "already-set"
    assert "OPENAI_API_KEY" not in pf.os.environ


def test_first_reads_only_documented_name(monkeypatch) -> None:
    monkeypatch.delenv("BYBIT_DEMO_API_KEY", raising=False)
    monkeypatch.setenv("PYBIT_API_KEY", "fallback")
    assert pf._first(pf.KEY_NAMES) == ""
    monkeypatch.setenv("BYBIT_DEMO_API_KEY", "primary")
    assert pf._first(pf.KEY_NAMES) == "primary"


def test_get_transport_refuses_non_demo_urls() -> None:
    # D-104 stage 1: read-only GETs are live, but ONLY against https on the demo host.
    with pytest.raises(ValueError, match="non-demo"):
        pf._urllib_transport("http://api-demo.bybit.com/v5/user/query-api", {})
    with pytest.raises(ValueError, match="non-demo"):
        pf._urllib_transport("https://api.bybit.com/v5/user/query-api", {})
    with pytest.raises(ValueError, match="non-demo"):
        pf._urllib_transport("https://api-demo.bybit.com.evil.example/v5/user/query-api", {})
