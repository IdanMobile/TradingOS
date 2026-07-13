"""Read-only dashboard adapter for the frozen ETH signal-flow verifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast


class EthSignalCheckError(RuntimeError):
    """Raised when the fixed verifier cannot produce a safe result."""


def build_eth_signal_check(root: Path) -> dict[str, object]:
    """Run the fixed offline verifier and reject any authority drift."""
    verifier = (root / "scripts/verify_eth_volume_breakout_flow.py").resolve()
    scripts_root = (root / "scripts").resolve()
    if verifier.parent != scripts_root or not verifier.is_file():
        raise EthSignalCheckError("ETH signal verifier is unavailable")

    try:
        completed = subprocess.run(
            [sys.executable, str(verifier)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as error:
        raise EthSignalCheckError("ETH signal verifier failed safely") from error

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise EthSignalCheckError("ETH signal verifier returned an invalid result")
    capabilities = payload.get("capabilities")
    safe_capabilities = {
        "order_creation": False,
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "venue_connection": "NONE",
        "execution_authority": "NONE",
    }
    if capabilities != safe_capabilities or payload.get("risk_decision") != "BLOCK":
        raise EthSignalCheckError("ETH signal verifier authority boundary changed")
    return cast(dict[str, object], payload)
