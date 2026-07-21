"""Deterministic attribution of normalized long-only backtest round trips."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tios.trading_domain import (
    DecisionOutcome,
    DomainRef,
    HistoricalTradeTrace,
    OutcomeClassification,
    Provenance,
)


class BacktestAttributionError(ValueError):
    """Normalized fills are incomplete or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class RoundTripAttribution:
    trade_id: int
    pair: str
    opened_at: datetime
    closed_at: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    cost_flipped: bool


@dataclass(frozen=True, slots=True)
class BacktestAttributionReport:
    label: str
    source_path: str
    source_sha256: str
    fill_count: int
    roundtrip_count: int
    profitable_count: int
    ordinary_loss_count: int
    breakeven_count: int
    cost_flipped_loss_count: int
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    roundtrips: tuple[RoundTripAttribution, ...]

    def as_dict(self, *, include_roundtrips: bool = False) -> dict[str, object]:
        result: dict[str, object] = {
            "label": self.label,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "fill_count": self.fill_count,
            "roundtrip_count": self.roundtrip_count,
            "profitable_count": self.profitable_count,
            "ordinary_loss_count": self.ordinary_loss_count,
            "breakeven_count": self.breakeven_count,
            "cost_flipped_loss_count": self.cost_flipped_loss_count,
            "gross_pnl": str(self.gross_pnl),
            "fees": str(self.fees),
            "net_pnl": str(self.net_pnl),
        }
        if include_roundtrips:
            result["roundtrips"] = [
                {
                    "trade_id": item.trade_id,
                    "pair": item.pair,
                    "opened_at": item.opened_at.isoformat(),
                    "closed_at": item.closed_at.isoformat(),
                    "quantity": str(item.quantity),
                    "entry_price": str(item.entry_price),
                    "exit_price": str(item.exit_price),
                    "gross_pnl": str(item.gross_pnl),
                    "fees": str(item.fees),
                    "net_pnl": str(item.net_pnl),
                    "cost_flipped": item.cost_flipped,
                }
                for item in self.roundtrips
            ]
        return result


@dataclass(frozen=True, slots=True)
class BacktestValidationEvidence:
    input_integrity_passed: bool
    fee_audit_passed: bool
    walk_forward_positive_windows: int | None
    neighboring_positive_variants: int | None
    benchmark_outperformed: bool | None


class BacktestRecommendation(StrEnum):
    REJECT_WITHOUT_RESCUE = "REJECT_WITHOUT_RESCUE"
    TEST_PREREGISTERED_LOWER_TURNOVER_HYPOTHESIS = "TEST_PREREGISTERED_LOWER_TURNOVER_HYPOTHESIS"
    REPAIR_EVIDENCE = "REPAIR_EVIDENCE"
    GATHER_MORE_EVIDENCE = "GATHER_MORE_EVIDENCE"


@dataclass(frozen=True, slots=True)
class BacktestFailureDiagnosis:
    classification: OutcomeClassification
    recommendation: BacktestRecommendation
    facts: tuple[str, ...]
    creates_strategy_version: bool = False
    promotion_eligible: bool = False


def build_historical_trade_traces(
    report: BacktestAttributionReport,
    *,
    strategy_version_ref: DomainRef,
    strategy_spec_sha256: str,
    evidence_refs: tuple[DomainRef, ...],
) -> tuple[HistoricalTradeTrace, ...]:
    """Convert complete fill round trips into immutable, capability-free learning records."""

    if not evidence_refs:
        raise BacktestAttributionError("historical traces require retained evidence references")
    limitations = (
        "The retained fill artifact does not preserve the originating signal identifier.",
        "The retained fill artifact does not preserve the contemporaneous risk decision.",
        "Classification describes realized accounting, not a proven causal explanation.",
    )
    traces = tuple(
        HistoricalTradeTrace(
            trace_id=(f"TRACE-HIST-{report.source_sha256[:16]}-{report.label}-{item.trade_id}"),
            source_sha256=report.source_sha256,
            strategy_spec_sha256=strategy_spec_sha256,
            strategy_version_ref=strategy_version_ref,
            split_label=report.label,
            source_trade_id=item.trade_id,
            pair=item.pair,
            opened_at=item.opened_at,
            closed_at=item.closed_at,
            quantity=item.quantity,
            entry_price=item.entry_price,
            exit_price=item.exit_price,
            outcome=DecisionOutcome(
                classification=(
                    OutcomeClassification.PROFITABLE
                    if item.net_pnl > 0
                    else OutcomeClassification.ORDINARY_STATISTICAL_LOSS
                    if item.net_pnl < 0
                    else OutcomeClassification.BREAKEVEN
                ),
                gross_pnl=item.gross_pnl,
                fees=item.fees,
                slippage_cost=Decimal("0"),
                net_pnl=item.net_pnl,
                currency=item.pair.split("/", maxsplit=1)[1],
                horizon_seconds=int((item.closed_at - item.opened_at).total_seconds()),
                reconciled=True,
            ),
            cost_flipped=item.cost_flipped,
            evidence_refs=evidence_refs,
            provenance=Provenance(evidence_refs),
            reconstruction_limitations=limitations,
        )
        for item in report.roundtrips
    )
    if len({trace.trace_id for trace in traces}) != len(traces):
        raise BacktestAttributionError("historical trace identifiers must be unique")
    return traces


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise BacktestAttributionError(f"{name} must be a finite Decimal")
    return value


def analyze_long_only_roundtrips(path: Path, *, label: str) -> BacktestAttributionReport:
    """Pair normalized buy/sell fills and reconcile realized P&L exactly."""

    if not path.is_file():
        raise BacktestAttributionError(f"trade artifact does not exist: {path}")
    table = pq.read_table(path)  # type: ignore[no-untyped-call]
    required = {"ts_fill", "side", "pair", "price", "qty", "fee", "trade_id"}
    if not required <= set(table.column_names):
        raise BacktestAttributionError("trade artifact is missing normalized fill columns")
    rows = table.select(sorted(required)).to_pylist()
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        trade_id = row["trade_id"]
        if not isinstance(trade_id, int) or isinstance(trade_id, bool):
            raise BacktestAttributionError("trade_id must be an integer")
        grouped.setdefault(trade_id, []).append(row)

    roundtrips: list[RoundTripAttribution] = []
    for trade_id, fills in sorted(grouped.items()):
        buys = [fill for fill in fills if fill["side"] == "buy"]
        sells = [fill for fill in fills if fill["side"] == "sell"]
        if len(fills) != 2 or len(buys) != 1 or len(sells) != 1:
            raise BacktestAttributionError(
                f"trade {trade_id} must contain exactly one buy and one sell fill"
            )
        buy, sell = buys[0], sells[0]
        if buy["pair"] != sell["pair"] or not isinstance(buy["pair"], str):
            raise BacktestAttributionError(f"trade {trade_id} pair mismatch")
        opened_at, closed_at = buy["ts_fill"], sell["ts_fill"]
        if not isinstance(opened_at, datetime) or not isinstance(closed_at, datetime):
            raise BacktestAttributionError(f"trade {trade_id} timestamps must be datetimes")
        if (
            opened_at.tzinfo is None
            or closed_at.tzinfo is None
            or opened_at.utcoffset() != timedelta(0)
            or closed_at.utcoffset() != timedelta(0)
            or opened_at >= closed_at
        ):
            raise BacktestAttributionError(f"trade {trade_id} timestamps are invalid")
        buy_qty = _decimal(buy["qty"], "buy quantity")
        sell_qty = _decimal(sell["qty"], "sell quantity")
        if buy_qty <= 0 or buy_qty != sell_qty:
            raise BacktestAttributionError(f"trade {trade_id} quantities do not reconcile")
        entry = _decimal(buy["price"], "entry price")
        exit_price = _decimal(sell["price"], "exit price")
        buy_fee = _decimal(buy["fee"], "buy fee")
        sell_fee = _decimal(sell["fee"], "sell fee")
        if entry <= 0 or exit_price <= 0 or buy_fee < 0 or sell_fee < 0:
            raise BacktestAttributionError(f"trade {trade_id} prices/fees are invalid")
        gross = (exit_price - entry) * buy_qty
        fees = buy_fee + sell_fee
        net = gross - fees
        roundtrips.append(
            RoundTripAttribution(
                trade_id=trade_id,
                pair=buy["pair"],
                opened_at=opened_at,
                closed_at=closed_at,
                quantity=buy_qty,
                entry_price=entry,
                exit_price=exit_price,
                gross_pnl=gross,
                fees=fees,
                net_pnl=net,
                cost_flipped=gross > 0 and net < 0,
            )
        )
    gross_total = sum((item.gross_pnl for item in roundtrips), start=Decimal("0"))
    fee_total = sum((item.fees for item in roundtrips), start=Decimal("0"))
    net_total = sum((item.net_pnl for item in roundtrips), start=Decimal("0"))
    if gross_total - fee_total != net_total:
        raise BacktestAttributionError("aggregate P&L does not reconcile")
    return BacktestAttributionReport(
        label=label,
        source_path=str(path),
        source_sha256=_sha256(path),
        fill_count=len(rows),
        roundtrip_count=len(roundtrips),
        profitable_count=sum(item.net_pnl > 0 for item in roundtrips),
        ordinary_loss_count=sum(item.net_pnl < 0 for item in roundtrips),
        breakeven_count=sum(item.net_pnl == 0 for item in roundtrips),
        cost_flipped_loss_count=sum(item.cost_flipped for item in roundtrips),
        gross_pnl=gross_total,
        fees=fee_total,
        net_pnl=net_total,
        roundtrips=tuple(roundtrips),
    )


def diagnose_backtest_failure(
    reports: tuple[BacktestAttributionReport, ...],
    evidence: BacktestValidationEvidence,
) -> BacktestFailureDiagnosis:
    """Classify aggregate failure without turning individual losses into causal stories."""

    if not reports:
        raise BacktestAttributionError("diagnosis requires at least one split report")
    if not evidence.input_integrity_passed or not evidence.fee_audit_passed:
        return BacktestFailureDiagnosis(
            OutcomeClassification.UNKNOWN,
            BacktestRecommendation.REPAIR_EVIDENCE,
            ("Input integrity and fee accounting must pass before strategy diagnosis.",),
        )
    facts = tuple(
        f"{report.label}: gross={report.gross_pnl}, fees={report.fees}, net={report.net_pnl}, "
        f"losses={report.ordinary_loss_count}/{report.roundtrip_count}, "
        f"cost_flipped={report.cost_flipped_loss_count}"
        for report in reports
    )
    robust_failure = (
        all(report.net_pnl < 0 for report in reports)
        and evidence.walk_forward_positive_windows == 0
        and evidence.neighboring_positive_variants == 0
        and evidence.benchmark_outperformed is False
    )
    if robust_failure:
        return BacktestFailureDiagnosis(
            OutcomeClassification.STRATEGY_WEAKNESS,
            BacktestRecommendation.REJECT_WITHOUT_RESCUE,
            facts
            + (
                "No positive walk-forward windows, no positive neighboring variants, and "
                "the benchmark was not outperformed.",
            ),
        )
    if any(report.gross_pnl > 0 > report.net_pnl for report in reports):
        return BacktestFailureDiagnosis(
            OutcomeClassification.STRATEGY_WEAKNESS,
            BacktestRecommendation.TEST_PREREGISTERED_LOWER_TURNOVER_HYPOTHESIS,
            facts + ("At least one split had positive gross edge erased by recorded fees.",),
        )
    return BacktestFailureDiagnosis(
        OutcomeClassification.UNKNOWN,
        BacktestRecommendation.GATHER_MORE_EVIDENCE,
        facts,
    )
