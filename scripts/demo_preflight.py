#!/usr/bin/env python3
"""Bybit DEMO preflight — the first thing to run when demo API keys arrive.

Proves, WITHOUT placing any order, that a Bybit demo key is usable and SAFE before the paper
lane is ever pointed at a venue:
  * the base URL is the demo host (never mainnet);
  * request signing + connectivity work (authenticated read);
  * the key is safe — trade permission present, NO withdrawal/transfer permission;
  * demo balances are visible.

Read-only: no order/cancel/transfer is ever sent. Requires DEMO keys in the environment; it
reads nothing on import. Live activation of the execution adapter is a separate, later step.
See docs/program/DEMO_LANE_PLAN.md.

Run: BYBIT_DEMO_API_KEY=... BYBIT_DEMO_API_SECRET=... python scripts/demo_preflight.py

ponytail: stdlib only (hmac/urllib/json); the transport is injectable so the whole flow is
unit-tested offline with no network and no real key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEMO_HOST = "api-demo.bybit.com"
DEMO_BASE = f"https://{DEMO_HOST}"
RECV_WINDOW = "5000"
NETWORK_QUARANTINE = (
    "authenticated Bybit demo networking is quarantined until the required signed "
    "HG-3/HG-4, security-review, validation, and venue-approval evidence exists"
)

# (url, headers) -> raw response body. Injected in tests; real urllib version in main().
Transport = Callable[[str, dict[str, str]], bytes]


def require_demo_base(base: str) -> None:
    parsed = urllib.parse.urlsplit(base)
    if (
        parsed.scheme != "https"
        or parsed.hostname != DEMO_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"preflight refuses a non-demo host: {base}")


def sign(secret: str, timestamp: str, api_key: str, query: str) -> str:
    """Bybit V5 signature: HMAC-SHA256 over timestamp + apiKey + recvWindow + queryString."""
    payload = f"{timestamp}{api_key}{RECV_WINDOW}{query}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _signed_get(
    transport: Transport,
    base: str,
    path: str,
    params: dict[str, str],
    api_key: str,
    secret: str,
    timestamp: str,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(sorted(params.items()))
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": sign(secret, timestamp, api_key, query),
    }
    url = f"{base}{path}" + (f"?{query}" if query else "")
    decoded = json.loads(transport(url, headers))
    return decoded if isinstance(decoded, dict) else {}


def _permissions(api_info: dict[str, Any]) -> list[str]:
    groups = api_info.get("result", {}).get("permissions", {})
    flat: list[str] = []
    for actions in groups.values():
        if isinstance(actions, list):
            flat.extend(str(action) for action in actions)
    return flat


def _grants_fund_removal(permissions: list[str]) -> bool:
    """True if the key can move funds off the account (must be FALSE for a safe demo key)."""
    return any(("withdraw" in p.lower() or "transfer" in p.lower()) for p in permissions)


def _can_trade(permissions: list[str], *, read_only: bool) -> bool:
    return not read_only and any("trade" in p.lower() for p in permissions)


def _balances(wallet: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for account in wallet.get("result", {}).get("list", []):
        for coin in account.get("coin", []):
            name, amount = coin.get("coin"), coin.get("walletBalance")
            if name is not None and amount not in (None, ""):
                out[str(name)] = str(amount)
    return out


def preflight(
    transport: Transport,
    api_key: str,
    secret: str,
    *,
    base: str = DEMO_BASE,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Run the read-only safety checks. Never places an order. `ok` is the go/no-go."""
    require_demo_base(base)
    ts = timestamp or str(int(time.time() * 1000))
    api_info = _signed_get(transport, base, "/v5/user/query-api", {}, api_key, secret, ts)
    if api_info.get("retCode") != 0:
        return {"ok": False, "stage": "auth", "error": str(api_info.get("retMsg", "auth failed"))}
    permissions = _permissions(api_info)
    read_only = str(api_info.get("result", {}).get("readOnly", "")) in {"1", "true", "True"}
    fund_removal = _grants_fund_removal(permissions)
    wallet = _signed_get(
        transport,
        base,
        "/v5/account/wallet-balance",
        {"accountType": "UNIFIED"},
        api_key,
        secret,
        ts,
    )
    can_trade = _can_trade(permissions, read_only=read_only)
    wallet_ok = wallet.get("retCode") == 0
    return {
        "ok": can_trade and wallet_ok and not fund_removal,
        "host": base,
        "is_demo_host": True,
        "permissions": permissions,
        "read_only": read_only,
        "can_trade": can_trade,
        "fund_removal_enabled": fund_removal,
        "wallet_ok": wallet_ok,
        "balances": _balances(wallet),
        "note": (
            "SAFE: trade-only demo key, cannot move funds."
            if not fund_removal
            else "UNSAFE: this key can move funds off the account — regenerate it without that "
            "permission before using it anywhere."
        ),
    }


def _urllib_transport(url: str, headers: dict[str, str]) -> bytes:
    raise RuntimeError(NETWORK_QUARANTINE)


ROOT = Path(__file__).resolve().parents[1]
KEY_NAMES = ("BYBIT_DEMO_API_KEY",)
SECRET_NAMES = ("BYBIT_DEMO_API_SECRET",)


def load_dotenv(path: Path) -> None:
    """Load only the two demo-specific names from a local ignored `.env`."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        name = key.removeprefix("export ").strip()
        if name in {*KEY_NAMES, *SECRET_NAMES}:
            os.environ.setdefault(name, value.strip().strip("'\""))


def _first(names: tuple[str, ...]) -> str:
    return next((os.environ[name] for name in names if os.environ.get(name)), "")


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key, secret = _first(KEY_NAMES), _first(SECRET_NAMES)
    if not api_key or not secret:
        print(
            "No demo key found in .env. Add BYBIT_DEMO_API_KEY / "
            "BYBIT_DEMO_API_SECRET — a DEMO key, trade-only, no withdrawal. "
            "See docs/program/DEMO_LANE_PLAN.md."
        )
        return 2
    report = preflight(_urllib_transport, api_key, secret)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
