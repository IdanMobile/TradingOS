"""The public checkpoint reaches a typed signal and independent blocking risk decision."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from tios.services.observations import build_observation_projection
from tios.services.observations.flow import OBSERVATION_ROOT
from tios.services.observations.risk_signal import (
    INSTRUMENT,
    SIGNAL_SPEC_ID,
    build_risk_signal_projection,
)
from tios.trading_domain import (
    ContractError,
    CreatorType,
    DomainRef,
    OrderCapability,
    Provenance,
    RiskStateSignalEvent,
    RunId,
    Side,
    SignalId,
    Timeframe,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_prospective_risk_signal_flow.py"


def _latest_real_checkpoint() -> Path:
    observation = build_observation_projection(ROOT)
    finalized = [
        row for row in observation["evidence"]["latest"] if row["checkpoint_status"] == "FINALIZED"
    ]
    return ROOT / max(finalized, key=lambda row: row["checkpoint_index"])["artifact_ref"]


def _write_checkpoint(root: Path, payload: dict[str, object]) -> tuple[Path, dict[str, object]]:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    directory = root / OBSERVATION_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"session_{digest}.json"
    path.write_bytes(encoded)
    metadata = payload["persistent_observation"]
    assert isinstance(metadata, dict)
    observation = {
        "availability": "AVAILABLE",
        "evidence": {
            "latest": [
                {
                    "artifact_ref": path.relative_to(root).as_posix(),
                    "checkpoint_status": "FINALIZED",
                    "checkpoint_index": metadata["checkpoint_index"],
                }
            ]
        },
    }
    return path, observation


def test_real_checkpoint_reaches_order_inert_independent_block() -> None:
    observation = build_observation_projection(ROOT)
    projection = build_risk_signal_projection(ROOT, observation)

    assert projection["availability"] == "AVAILABLE"
    assert projection["flow_state"] == "RISK_BLOCKED"
    assert projection["signal"]["side"] == "FLAT"
    assert projection["signal"]["metric_eligible"] is False
    assert projection["signal"]["scorecard_eligible"] is False
    assert projection["signal"]["promotion_eligible"] is False
    assert projection["risk_decision"]["decision"] == "BLOCK"
    assert projection["risk_decision"]["independent"] is True
    assert projection["capabilities"] == {
        "credentials_used": False,
        "execution_authority": "NONE",
        "live_orders": "DISABLED",
        "market_data_transport": "PUBLIC_READ_ONLY",
        "order_creation": False,
        "paper_orders": "DISABLED",
        "venue_connection": "NONE",
    }


def test_semantic_signal_or_authority_drift_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(_latest_real_checkpoint().read_text())
    payload["signal"]["promotion_eligible"] = True
    _, observation = _write_checkpoint(tmp_path / "signal", payload)
    signal_drift = build_risk_signal_projection(tmp_path / "signal", observation)
    assert signal_drift["availability"] == "ERROR"
    assert signal_drift["flow_state"] == "BLOCKED"
    assert "warmup boundary" in signal_drift["blockers"][0]
    assert signal_drift["capabilities"]["order_creation"] is False

    payload = json.loads(_latest_real_checkpoint().read_text())
    payload["authority"]["paper_orders"] = "ENABLED"
    _, observation = _write_checkpoint(tmp_path / "authority", payload)
    authority_drift = build_risk_signal_projection(tmp_path / "authority", observation)
    assert authority_drift["availability"] == "ERROR"
    assert authority_drift["flow_state"] == "BLOCKED"
    assert "authority boundary changed" in authority_drift["blockers"][0]


def test_risk_state_signal_type_cannot_grant_eligibility_or_orders() -> None:
    at = datetime(2026, 7, 13, 22, 35, tzinfo=UTC)
    signal = RiskStateSignalEvent(
        signal_id=SignalId("SIG-risk-state-contract"),
        signal_spec_id=SIGNAL_SPEC_ID,
        run_ref=RunId("RUN-risk-state-contract"),
        instrument=INSTRUMENT,
        timeframe=Timeframe.M5,
        observed_at=at,
        side=Side.FLAT,
        rationale_code="PROSPECTIVE_WARMUP_BLOCK",
        metric_eligible=False,
        scorecard_eligible=False,
        promotion_eligible=False,
        created_at=at,
        creator_type=CreatorType.SYSTEM,
        provenance=Provenance((DomainRef("EV-risk-state-contract"),)),
    )
    with pytest.raises(ContractError, match="cannot grant strategy eligibility"):
        replace(signal, promotion_eligible=True)
    with pytest.raises(ContractError, match="cannot activate orders"):
        replace(signal, paper_orders=cast(OrderCapability, "ENABLED"))


def test_fixed_offline_verifier_passes_current_evidence() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    projection = json.loads(result.stdout)
    assert projection["risk_decision"]["decision"] == "BLOCK"
    assert projection["capabilities"]["execution_authority"] == "NONE"
