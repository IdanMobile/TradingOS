"""EngineAdapter port + NormalizedResult (T-006-01, REQ-014; type catalog §4).

This is the parity boundary: every engine lane produces a NormalizedResult and a
CapabilityReport. An unsupported feature is an explicit CapabilityGap — never a
silent approximation. Money/qty fields are Decimal (type catalog decimal law).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

# ── Fee/slippage scenarios (specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md) ──


@dataclass(frozen=True)
class FeeSlippageScenario:
    scenario_id: str  # e.g. "F1/S2"
    fee_rate_per_side: Decimal  # fraction, e.g. 0.001 = 0.10%
    slippage_bps_per_side: Decimal
    diagnostic_only: bool = False  # F0/S0 must never count as economic evidence


MANDATORY_GRID: tuple[FeeSlippageScenario, ...] = (
    FeeSlippageScenario("F0/S0", Decimal("0"), Decimal("0"), diagnostic_only=True),
    FeeSlippageScenario("F1/S1", Decimal("0.001"), Decimal("1")),
    FeeSlippageScenario("F1/S2", Decimal("0.001"), Decimal("5")),
    FeeSlippageScenario("F1/S3", Decimal("0.001"), Decimal("10")),
    FeeSlippageScenario("F2/S2", Decimal("0.0015"), Decimal("5")),
    FeeSlippageScenario("F2/S3", Decimal("0.0015"), Decimal("10")),
)


# ── Normalized result (canonical trades/equity/metrics) ──


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Trade:
    ts_signal: datetime | None  # engine may not expose signal time -> None + semantic note
    ts_order: datetime | None
    ts_fill: datetime
    side: Side
    price: Decimal
    qty: Decimal
    fee: Decimal


@dataclass(frozen=True)
class EquityPoint:
    ts: datetime
    equity: Decimal


@dataclass(frozen=True)
class NormalizedResult:
    engine: str
    sv_id: str
    dataset_id: str
    scenario: FeeSlippageScenario
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    metrics: dict[str, Decimal]
    warnings: tuple[str, ...] = ()
    semantic_notes: tuple[str, ...] = ()


# ── Capability reporting (explicit gaps, never silent approximation) ──


@dataclass(frozen=True)
class CapabilityGap:
    feature: str  # what the canonical spec required
    detail: str  # what the engine cannot express, exactly
    workaround: str | None = None  # explicit + documented, or None = lane limitation


@dataclass(frozen=True)
class CapabilityReport:
    engine: str
    gaps: tuple[CapabilityGap, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnginePlan:
    """Adapter-prepared execution plan; `native` holds engine-specific config."""

    engine: str
    sv_id: str
    dataset_id: str
    scenario: FeeSlippageScenario
    native: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VersionManifest:
    engine: str
    version: str
    commit: str | None
    env_hash: str


class EngineAdapter(Protocol):
    """One per engine (type catalog §4). Engines run isolated (subprocess/Docker);
    this port is the only surface src/tios sees."""

    def prepare(self, dataset_id: str, sv_id: str, scenario: FeeSlippageScenario) -> EnginePlan: ...

    def run(self, plan: EnginePlan) -> dict[str, Any]: ...  # EngineRawResult, engine-native

    def normalize(self, raw: dict[str, Any]) -> NormalizedResult: ...

    def capabilities(self) -> CapabilityReport: ...

    def version_manifest(self) -> VersionManifest: ...
