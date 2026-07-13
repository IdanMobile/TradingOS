"""Prospective forced-order snapshot signal stays causal and fail-closed."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.strategy.liquidation_stress import (
    BASELINE_WINDOWS,
    LiquidationStressError,
    LiquidationStressState,
    aggregate_window,
    classify_window,
    parse_force_order_message,
)

START = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)


def message(*, side: str, contracts: str, event_offset_ms: int = 1000) -> str:
    timestamp = int(START.timestamp() * 1000) + event_offset_ms
    return json.dumps(
        {
            "e": "forceOrder",
            "E": timestamp,
            "o": {
                "s": "BTCUSD_PERP",
                "ps": "BTCUSD",
                "S": side,
                "z": contracts,
                "ap": "100000.0",
                "T": timestamp - 1,
            },
            "st": 2,
        }
    )


def snapshot(side: str, contracts: str, *, event_offset_ms: int = 1000):
    return parse_force_order_message(
        message(side=side, contracts=contracts, event_offset_ms=event_offset_ms),
        received_at=START + timedelta(seconds=2),
        expected_symbol="BTCUSD_PERP",
        expected_pair="BTCUSD",
        contract_size_usd=Decimal(100),
    )


def test_snapshot_notional_dedup_and_prospective_states() -> None:
    sell = snapshot("SELL", "100")
    buy = snapshot("BUY", "10", event_offset_ms=1500)
    window = aggregate_window((sell, sell, buy), start=START, complete=True)
    assert window.event_count == 2
    assert window.gross_notional_usd == Decimal(11000)
    assert window.sell_notional_usd == Decimal(10000)
    assert classify_window(window, prior_complete_gross_notional=()) is (
        LiquidationStressState.WARMUP_BLOCK
    )
    baseline = (Decimal(100),) * BASELINE_WINDOWS
    assert classify_window(window, prior_complete_gross_notional=baseline) is (
        LiquidationStressState.LONG_LIQUIDATION_STRESS
    )
    incomplete = aggregate_window((sell,), start=START, complete=False)
    assert classify_window(incomplete, prior_complete_gross_notional=baseline) is (
        LiquidationStressState.SOURCE_WINDOW_INCOMPLETE
    )


def test_snapshot_rejects_identity_and_noncausal_time() -> None:
    with pytest.raises(LiquidationStressError, match="identity changed"):
        parse_force_order_message(
            message(side="SELL", contracts="1"),
            received_at=START + timedelta(seconds=2),
            expected_symbol="ETHUSD_PERP",
            expected_pair="ETHUSD",
            contract_size_usd=Decimal(10),
        )
    with pytest.raises(LiquidationStressError, match="not causal"):
        parse_force_order_message(
            message(side="SELL", contracts="1"),
            received_at=START,
            expected_symbol="BTCUSD_PERP",
            expected_pair="BTCUSD",
            contract_size_usd=Decimal(100),
        )
