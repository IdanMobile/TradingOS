"""The prospective session verifier reconstructs evidence and rejects semantic drift."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_prospective_liquidation_observer.py"
SOURCE = ROOT / "artifacts/prospective/BTC-LIQUIDATION-STRESS-V1"
PERSISTENT_CONTRACT = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml"


def verify(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--verify-only", "--output-dir", str(directory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_verifier_rejects_byte_and_rehashed_semantic_drift(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    assert verify(target).returncode == 0

    session = next(target.glob("session_*.json"))
    original = session.read_bytes()
    session.write_bytes(original + b" ")
    byte_drift = verify(target)
    assert byte_drift.returncode != 0
    assert "session hash mismatch" in byte_drift.stderr

    payload = json.loads(original)
    payload["authority"]["paper_orders"] = "ENABLED"
    changed = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    session.unlink()
    rehashed = target / f"session_{hashlib.sha256(changed).hexdigest()}.json"
    rehashed.write_bytes(changed)
    semantic_drift = verify(target)
    assert semantic_drift.returncode != 0
    assert "authority boundary changed" in semantic_drift.stderr


def test_v3_reconstructs_rejected_source_event_and_error(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    failed = next(
        path
        for path in target.glob("session_*.json")
        if json.loads(path.read_text())["source"]["status"].startswith("FAILED_")
    )
    payload = json.loads(failed.read_text())
    payload["schema_version"] = 3
    payload["source_failure"] = {
        "error_type": "LiquidationStressError",
        "error_message": "invalid force-order snapshot schema",
        "rejected_event": {
            "raw_message": "{}",
            "received_at": payload["source"]["coverage_ended_at"],
        },
    }
    changed = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    failed.unlink()
    failed = target / f"session_{hashlib.sha256(changed).hexdigest()}.json"
    failed.write_bytes(changed)
    assert verify(target).returncode == 0

    payload["source_failure"]["error_message"] = "different failure"
    changed = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    failed.unlink()
    failed = target / f"session_{hashlib.sha256(changed).hexdigest()}.json"
    failed.write_bytes(changed)
    mismatch = verify(target)
    assert mismatch.returncode != 0
    assert "rejected source event failure mismatch" in mismatch.stderr


def test_v5_checkpoint_and_planned_overlap_reconstruct(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    checkpoint = next(
        path
        for path in target.glob("session_*.json")
        if json.loads(path.read_text()).get("schema_version") == 4
        and json.loads(path.read_text())["source"]["status"] == "COMPLETE"
    )
    payload = json.loads(checkpoint.read_text())
    payload["schema_version"] = 5
    payload["persistent_observation"] = {
        "operations_contract_sha256": hashlib.sha256(PERSISTENT_CONTRACT.read_bytes()).hexdigest(),
        "run_id": "1" * 24,
        "checkpoint_index": 1,
        "connection_epoch": 2,
        "continuity_epoch": 1,
        "connection_opened_at": payload["started_at"],
        "checkpoint_status": "FINALIZED",
        "planned_handoff": {
            "from_connection_epoch": 1,
            "overlap_started_at": payload["started_at"],
            "handoff_boundary": payload["started_at"],
        },
    }
    changed = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    checkpoint.unlink()
    checkpoint = target / f"session_{hashlib.sha256(changed).hexdigest()}.json"
    checkpoint.write_bytes(changed)
    assert verify(target).returncode == 0

    payload["persistent_observation"]["planned_handoff"]["overlap_started_at"] = payload["ended_at"]
    changed = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    checkpoint.unlink()
    checkpoint = target / f"session_{hashlib.sha256(changed).hexdigest()}.json"
    checkpoint.write_bytes(changed)
    invalid_overlap = verify(target)
    assert invalid_overlap.returncode != 0
    assert "handoff coverage is invalid" in invalid_overlap.stderr
