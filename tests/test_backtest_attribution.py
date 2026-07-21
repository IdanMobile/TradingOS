import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tios.services.reporting import (
    BacktestAttributionError,
    DecisionTraceLedgerError,
    HistoricalTradeTraceLedger,
    analyze_long_only_roundtrips,
    build_historical_trade_traces,
)
from tios.trading_domain import DomainRef, HistoricalTradeTrace, OutcomeClassification

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    schema = pa.schema(
        [
            ("ts_fill", pa.timestamp("us", tz="UTC")),
            ("side", pa.string()),
            ("pair", pa.string()),
            ("price", pa.decimal128(20, 8)),
            ("qty", pa.decimal128(20, 8)),
            ("fee", pa.decimal128(20, 8)),
            ("trade_id", pa.int64()),
        ]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)  # type: ignore[no-untyped-call]


def _fills() -> list[dict[str, object]]:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    values = (
        (0, "100", "103", "0.5", "0.5"),
        (1, "100", "98", "0.5", "0.5"),
        (2, "100", "100.5", "0.4", "0.4"),
    )
    rows: list[dict[str, object]] = []
    for trade_id, entry, exit_price, buy_fee, sell_fee in values:
        rows.extend(
            (
                {
                    "ts_fill": now + timedelta(minutes=trade_id * 2),
                    "side": "buy",
                    "pair": "BTC/USDT",
                    "price": Decimal(entry),
                    "qty": Decimal("1"),
                    "fee": Decimal(buy_fee),
                    "trade_id": trade_id,
                },
                {
                    "ts_fill": now + timedelta(minutes=trade_id * 2 + 1),
                    "side": "sell",
                    "pair": "BTC/USDT",
                    "price": Decimal(exit_price),
                    "qty": Decimal("1"),
                    "fee": Decimal(sell_fee),
                    "trade_id": trade_id,
                },
            )
        )
    return rows


def test_roundtrip_attribution_reconciles_costs_and_cost_flipped_losses(tmp_path: Path) -> None:
    path = tmp_path / "trades.parquet"
    _write(path, _fills())
    report = analyze_long_only_roundtrips(path, label="TEST")
    assert report.fill_count == 6 and report.roundtrip_count == 3
    assert report.profitable_count == 1
    assert report.ordinary_loss_count == 2
    assert report.cost_flipped_loss_count == 1
    assert report.gross_pnl == Decimal("1.5")
    assert report.fees == Decimal("2.8")
    assert report.net_pnl == Decimal("-1.3")


def _historical_traces(path: Path) -> tuple[HistoricalTradeTrace, ...]:
    report = analyze_long_only_roundtrips(path, label="TEST")
    return build_historical_trade_traces(
        report,
        strategy_version_ref=DomainRef("SV-d807f4a811312a74d73ddcf955078a78"),
        strategy_spec_sha256=("d807f4a811312a74d73ddcf955078a7846ad18fab3006b996c2fa45be318f5e0"),
        evidence_refs=(DomainRef("EV-TEST-HISTORICAL-FILLS"),),
    )


def test_historical_trade_traces_reconcile_without_inventing_decision_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trades.parquet"
    _write(path, _fills())
    traces = _historical_traces(path)
    assert len(traces) == 3
    assert [trace.outcome.classification for trace in traces] == [
        OutcomeClassification.PROFITABLE,
        OutcomeClassification.ORDINARY_STATISTICAL_LOSS,
        OutcomeClassification.ORDINARY_STATISTICAL_LOSS,
    ]
    assert [trace.cost_flipped for trace in traces] == [False, False, True]
    assert sum((trace.outcome.net_pnl for trace in traces), start=Decimal("0")) == Decimal("-1.3")
    assert all("signal identifier" in trace.reconstruction_limitations[0] for trace in traces)
    assert all(trace.execution_authority.value == "NONE" for trace in traces)


def test_historical_batch_ledger_is_idempotent_and_rejects_conflict_before_append(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trades.parquet"
    _write(path, _fills())
    traces = _historical_traces(path)
    ledger = HistoricalTradeTraceLedger(tmp_path / "historical.jsonl")
    digests = ledger.append_many(traces)
    first_ledger_digest = ledger.digest()
    assert ledger.append_many(traces) == digests
    assert ledger.digest() == first_ledger_digest
    assert len(ledger.records()) == 3

    conflict = replace(
        traces[1],
        reconstruction_limitations=("Conflicting content under the same identifier.",),
    )
    before = ledger.path.read_bytes()
    with pytest.raises(DecisionTraceLedgerError, match="different retained content"):
        ledger.append_many((traces[0], conflict))
    assert ledger.path.read_bytes() == before


def test_roundtrip_attribution_rejects_quantity_mismatch(tmp_path: Path) -> None:
    rows = _fills()
    rows[1]["qty"] = Decimal("2")
    path = tmp_path / "bad.parquet"
    _write(path, rows)
    with pytest.raises(BacktestAttributionError, match="quantities do not reconcile"):
        analyze_long_only_roundtrips(path, label="BAD")


def test_real_b2_loss_attribution_rejects_rescue_without_creating_v2() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_backtest_loss_attribution.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["aggregate"] == {
        "breakeven": 0,
        "cost_flipped_losses": 329,
        "fees": "2813.09721472",
        "gross_pnl": "-165.9356942000000000",
        "net_pnl": "-2979.0329089200000000",
        "ordinary_losses": 1165,
        "profitable": 242,
        "roundtrips": 1407,
    }
    assert report["diagnosis"]["classification"] == "STRATEGY_WEAKNESS"
    assert report["diagnosis"]["recommendation"] == "REJECT_WITHOUT_RESCUE"
    assert report["diagnosis"]["creates_strategy_version"] is False
    assert report["diagnosis"]["promotion_eligible"] is False
    assert report["learning_ledger"]["trace_count"] == 1407
    assert report["learning_ledger"]["unique_trace_digests"] == 1407
    assert report["learning_ledger"]["idempotent_replay"] is True
    assert report["learning_ledger"]["signal_history_reconstructed"] is False
    assert report["learning_ledger"]["risk_history_reconstructed"] is False
    assert report["orders_created"] == 0
