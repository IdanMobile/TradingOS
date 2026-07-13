from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tios.strategy.liquidation_stress import LiquidationStressError
from tios.strategy.prospective_labels import gross_return, label_times, parse_exact_kline

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/prospective/BTC-LIQUIDATION-STRESS-V1"
SCRIPT = ROOT / "scripts/run_prospective_liquidation_labels.py"
CONTRACT = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_LABEL_CONTRACT_V1.yaml"
AUTHORITY = {
    "execution_authority": "NONE",
    "venue_connection": "NONE",
    "market_data_transport": "PUBLIC_READ_ONLY",
    "paper_orders": "DISABLED",
    "live_orders": "DISABLED",
    "credentials_used": False,
}


def kline(at: datetime, price: str = "60000.10") -> bytes:
    start = int(at.timestamp() * 1000)
    row = [start, price, price, price, price, "1", start + 59_999, "1", 1, "1", "1", "0"]
    return json.dumps([row]).encode()


def test_frozen_label_timing_is_strictly_later_and_causal() -> None:
    window = datetime(2026, 7, 13, 18, 45, tzinfo=UTC)
    timing = label_times(window, "1H")
    assert timing.window_close == datetime(2026, 7, 13, 18, 50, tzinfo=UTC)
    assert timing.entry_open == datetime(2026, 7, 13, 18, 51, tzinfo=UTC)
    assert timing.exit_open == datetime(2026, 7, 13, 19, 51, tzinfo=UTC)
    assert timing.available_at == datetime(2026, 7, 13, 19, 52, tzinfo=UTC)


def test_exact_kline_and_return_reconstruct() -> None:
    at = datetime(2026, 7, 13, 18, 51, tzinfo=UTC)
    assert parse_exact_kline(kline(at), expected_open=at) == Decimal("60000.10")
    assert gross_return(Decimal("100"), Decimal("105")) == Decimal("0.05")


def test_exact_kline_rejects_wrong_time_and_shape() -> None:
    at = datetime(2026, 7, 13, 18, 51, tzinfo=UTC)
    with pytest.raises(LiquidationStressError):
        parse_exact_kline(kline(at), expected_open=at + timedelta(minutes=1))
    with pytest.raises(LiquidationStressError):
        parse_exact_kline(b"[]", expected_open=at)


def canonical(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def verify(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--verify-only", "--output-dir", str(directory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_verifier_rejects_rehashed_future_and_authority_drift(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    shutil.rmtree(target / "labels", ignore_errors=True)
    complete_sessions = [
        path
        for path in target.glob("session_*.json")
        if json.loads(path.read_text())["observation"].get("complete_windows")
    ]
    session_path = min(
        complete_sessions,
        key=lambda path: json.loads(path.read_text())["observation"]["complete_windows"][0][
            "start"
        ],
    )
    session = json.loads(session_path.read_text())
    window = datetime.fromisoformat(session["observation"]["complete_windows"][0]["start"])
    evaluated_at = window + timedelta(minutes=6)
    rows = []
    for horizon in ("1H", "6H", "24H"):
        timing = label_times(window, horizon)
        rows.append(
            {
                "source_session_sha256": session_path.stem.removeprefix("session_"),
                "window_start": window.isoformat(),
                "window_close": timing.window_close.isoformat(),
                "horizon": horizon,
                "entry_open_time": timing.entry_open.isoformat(),
                "exit_open_time": timing.exit_open.isoformat(),
                "available_at": timing.available_at.isoformat(),
                "status": "NOT_AVAILABLE",
                "entry_raw_sha256": None,
                "exit_raw_sha256": None,
                "entry_open": None,
                "exit_open": None,
                "gross_return": None,
            }
        )
    payload = {
        "schema_version": 1,
        "label_contract_id": "PROSPECTIVE-BTC-LIQUIDATION-LABELS-V1",
        "label_contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
        "evaluated_at": evaluated_at.isoformat(),
        "source": {
            "endpoint": "https://data-api.binance.vision/api/v3/klines",
            "symbol": "BTCUSDT",
            "interval": "1m",
            "authentication": "NONE",
        },
        "labels": rows,
        "analysis": "PROHIBITED_DURING_WARMUP",
        "metric_eligible": False,
        "scorecard_eligible": False,
        "promotion_eligible": False,
        "authority": AUTHORITY,
    }
    labels = target / "labels"
    labels.mkdir()
    original = canonical(payload)
    path = labels / f"label_snapshot_{hashlib.sha256(original).hexdigest()}.json"
    path.write_bytes(original)
    assert verify(target).returncode == 0

    after_one_hour = label_times(window, "1H").available_at + timedelta(minutes=1)
    payload["evaluated_at"] = after_one_hour.isoformat()
    changed = canonical(payload)
    path.unlink()
    path = labels / f"label_snapshot_{hashlib.sha256(changed).hexdigest()}.json"
    path.write_bytes(changed)
    future_drift = verify(target)
    assert future_drift.returncode != 0
    assert "causally available label is missing" in future_drift.stderr

    payload["evaluated_at"] = evaluated_at.isoformat()
    payload["authority"]["paper_orders"] = "ENABLED"
    changed = canonical(payload)
    path.unlink()
    path = labels / f"label_snapshot_{hashlib.sha256(changed).hexdigest()}.json"
    path.write_bytes(changed)
    authority_drift = verify(target)
    assert authority_drift.returncode != 0
    assert "authority boundary changed" in authority_drift.stderr


def test_older_snapshot_ignores_windows_completed_after_its_evaluation(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    snapshots = sorted((target / "labels").glob("label_snapshot_*.json"))
    assert snapshots
    first = json.loads(snapshots[0].read_text())
    evaluated_at = datetime.fromisoformat(first["evaluated_at"])
    assert any(
        datetime.fromisoformat(row["start"]) + timedelta(minutes=5) > evaluated_at
        for session_path in target.glob("session_*.json")
        for row in json.loads(session_path.read_text())["observation"].get("complete_windows", [])
    )
    assert verify(target).returncode == 0
