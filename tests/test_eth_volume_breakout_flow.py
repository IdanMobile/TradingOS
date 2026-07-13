import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eth_volume_breakout_vertical_flow_is_deterministic_and_order_inert() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_eth_volume_breakout_flow.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    projection = json.loads(completed.stdout)
    assert projection["strategy_version_id"] == "SV-418ab5d64825c74b"
    assert projection["signal_count"] == 511
    assert projection["status"] == "SIGNAL_FLOW_AVAILABLE_RISK_BLOCKED"
    assert projection["risk_decision"] == "BLOCK"
    assert projection["promotion_eligible"] is False
    assert projection["capabilities"] == {
        "order_creation": False,
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "venue_connection": "NONE",
        "execution_authority": "NONE",
    }
