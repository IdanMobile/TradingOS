#!/usr/bin/env python3
"""Verify frozen ETH volume-breakout data -> signal -> independent risk block."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tios.strategy.evaluator import evaluate_strategy_signals  # noqa: E402
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402
from tios.trading_domain import (  # noqa: E402
    CreatorType,
    DatasetId,
    DomainRef,
    InstrumentId,
    Market,
    MarketBar,
    MarketName,
    Provenance,
    RiskCheck,
    RiskDecision,
    RiskId,
    RiskOutcome,
    RunId,
    StrategyVersionId,
    Timeframe,
    VenueFamily,
)

SPEC = ROOT / "strategies/research/eth-volume-breakout-prospective/canonical_strategy_spec.yaml"
DATA = ROOT / "data/normalized/ETHUSDT_1h.parquet"
DATA_SHA256 = "324b3a704560103d9d49453e48d5b24839df6ab2ca67c6fcd5da2d2365d3b1da"
FREEZE = datetime(2026, 7, 13, 22, 52, 40, tzinfo=UTC)
PARAMETERS = {
    "instrument": "ETH-USDT.BINANCE_SPOT",
    "timeframe": "1h",
    "window": 40,
    "volume_multiplier": "1.5",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_projection() -> dict[str, object]:
    if _sha256(DATA) != DATA_SHA256:
        raise RuntimeError("ETHUSDT 1h reproduction dataset hash mismatch")
    raw_spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    report = validate(raw_spec)
    if report.verdict != "VALID":
        raise RuntimeError(f"candidate spec is not valid: {report}")
    spec = parse_spec(raw_spec)
    version = create_version(spec, PARAMETERS)
    table = pq.read_table(  # type: ignore[no-untyped-call]
        DATA,
        columns=["timestamp_open_utc", "open", "high", "low", "close", "volume_base"],
    )
    rows = table.to_pylist()
    evidence = DomainRef(f"EV-{DATA_SHA256}")
    provenance = Provenance((evidence,))
    market = Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BINANCE_SPOT"),
        InstrumentId("ETH-USDT.BINANCE_SPOT"),
        Timeframe.H1,
        DatasetId("DS-ETH-VOLUME-BREAKOUT-REPRO-V1"),
    )
    bars = tuple(
        MarketBar(
            market=market,
            open_time=row["timestamp_open_utc"].astimezone(UTC),
            close_time=row["timestamp_open_utc"].astimezone(UTC) + timedelta(hours=1),
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=Decimal(row["volume_base"]),
            created_at=FREEZE,
            creator_type=CreatorType.SYSTEM,
            provenance=provenance,
        )
        for row in rows
    )
    signals = evaluate_strategy_signals(
        spec=spec,
        bars=bars,
        strategy_version_ref=StrategyVersionId(version.sv_id),
        run_ref=RunId("RUN-ETH-VOLUME-BREAKOUT-REPRO-V1"),
        created_at=FREEZE,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    if not signals:
        raise RuntimeError("candidate produced no historical reproduction signal")
    check = RiskCheck(
        rule_code="PROMOTION_GATE",
        outcome=RiskOutcome.BLOCK,
        evidence_refs=(evidence,),
        detail="PROSPECTIVE_VALIDATION_INCOMPLETE",
    )
    risk = RiskDecision(
        risk_id=RiskId("RISK-ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1"),
        subject_ref=DomainRef(str(signals[-1].signal_id)),
        as_of=signals[-1].observed_at,
        decision=RiskOutcome.BLOCK,
        rule_results=(check,),
        evidence_refs=(evidence,),
        created_at=FREEZE,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )
    return {
        "schema_version": 1,
        "candidate_id": "ETH-VOLUME-BREAKOUT-PROSPECTIVE-V1",
        "status": "SIGNAL_FLOW_AVAILABLE_RISK_BLOCKED",
        "strategy_version_id": version.sv_id,
        "spec_hash": version.spec_hash,
        "dataset_sha256": DATA_SHA256,
        "historical_reproduction_only": True,
        "bars": len(bars),
        "signal_count": len(signals),
        "first_signal": {
            "observed_at": signals[0].observed_at.isoformat(),
            "side": signals[0].side.value,
        },
        "last_signal": {
            "signal_id": str(signals[-1].signal_id),
            "observed_at": signals[-1].observed_at.isoformat(),
            "side": signals[-1].side.value,
        },
        "risk_decision": risk.decision.value,
        "risk_reason": check.detail,
        "prospective_boundary_utc": "2026-07-14T00:00:00Z",
        "promotion_eligible": False,
        "capabilities": {
            "order_creation": False,
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "venue_connection": "NONE",
            "execution_authority": "NONE",
        },
    }


def main() -> None:
    print(json.dumps(build_projection(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
