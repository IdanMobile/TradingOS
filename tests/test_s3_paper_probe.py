"""End-to-end check for the synthetic S3 paper lane.

Runs the lane on a tiny hand-built breakout series so a regression in the
fill -> ledger -> position -> portfolio wiring (or the NOT_ELIGIBLE / no-venue
guards) fails here. No frozen dataset, no network, no engines, nothing tradeable.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.run_s3_paper_probe as probe  # noqa: E402
from tios.trading_domain import PositionStatus  # noqa: E402


def _candles(closes: list[float]) -> dict[str, list[Decimal]]:
    s = [Decimal(str(c)) for c in closes]
    return {"open": s, "high": s, "low": s, "close": s, "volume": s}


def test_paper_lane_enters_on_breakout_and_conserves_cash() -> None:
    cand = probe.Candidate("TEST-DONCHIAN", "SYNTH", 3, "ETH-USDT.BINANCE_SPOT", 60)
    # Flat, breakout up (enter), then sustained breakdown (exit, stays flat to the end).
    closes = [100, 100, 100, 100, 130, 131, 132, 133, 90, 80, 70, 60, 50]
    run = probe.run_paper_lane(cand, candles=_candles(closes))
    assert run.trade_count >= 2, "a breakout then breakdown must produce a buy and a sell"
    # Ledger has the initial-capital entry plus a settlement+fee pair per fill.
    assert len(run.ledger.entries) == 1 + 2 * run.trade_count
    # The round trip closes out; no open lot dangles at the end of this series.
    assert run.final_position.status is PositionStatus.CLOSED
    # Fees are strictly positive and equity stays finite and positive.
    assert run.fee_total > 0
    assert run.final_equity > 0


def test_report_keeps_candidate_inert_and_reports_divergence() -> None:
    cand = probe.Candidate("TEST-DONCHIAN", "SYNTH", 3, "ETH-USDT.BINANCE_SPOT", 60)
    closes = [100, 100, 100, 100, 130, 131, 132, 133, 90, 80, 70, 60, 50]

    # Patch the loaders so build_report uses the synthetic series (no frozen data).
    original_load = probe.seed.load_candles
    original_datasets = probe.seed.DATASETS
    probe.seed.DATASETS = {**original_datasets, "SYNTH": "SYNTH"}
    probe.seed.load_candles = lambda _path: _candles(closes)  # type: ignore[assignment]
    try:
        report = probe.build_report(cand)
    finally:
        probe.seed.load_candles = original_load
        probe.seed.DATASETS = original_datasets

    assert report["approval_status"] == "NOT_ELIGIBLE"
    assert report["execution_authority"] == "NONE"
    assert report["venue_connection"] == "NONE"
    assert report["paper_orders"] == "DISABLED" and report["live_orders"] == "DISABLED"
    assert report["paper_lane_proposal"]["mode"] == "SYNTHETIC_LOCAL_SIMULATOR"
    metrics = {o["metric"] for o in report["divergence_report"]["observations"]}
    assert metrics == {"TRADE_COUNT", "FEE_TOTAL"}
