"""Independent reference checks for Spot taker-imbalance accounting."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engines.reference.taker_imbalance import simulate_taker_ledger, taker_events  # noqa: E402
from tios.strategy.taker_imbalance import (  # noqa: E402
    TakerObservation,
    project_taker_pulses,
)


def test_reference_events_and_cost_accounting() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    source_opens = tuple(start + timedelta(hours=index) for index in range(25))
    source_closes = tuple(value + timedelta(minutes=59) for value in source_opens)
    quote = (Decimal(100),) * 25
    bought = tuple(Decimal(45) if index % 2 == 0 else Decimal(55) for index in range(24)) + (
        Decimal(75),
    )
    spot_opens = tuple(start + timedelta(hours=index) for index in range(32))
    entries, exits = taker_events(
        spot_opens=spot_opens,
        source_opens=source_opens,
        source_closes=source_closes,
        quote_volume=quote,
        taker_buy_quote=bought,
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    assert entries[25] and exits[31]
    canonical = project_taker_pulses(
        tuple(
            TakerObservation(opened, closed, total, bought)
            for opened, closed, total, bought in zip(
                source_opens, source_closes, quote, bought, strict=True
            )
        ),
        spot_opens,
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    assert [spot_opens[index] for index, flag in enumerate(entries) if flag] == [
        canonical[0].open_time
    ]
    assert [spot_opens[index] for index, flag in enumerate(exits) if flag] == [
        canonical[1].open_time
    ]
    result = simulate_taker_ledger(
        spot_opens=spot_opens,
        opens=(Decimal(100),) * 32,
        closes=(Decimal(100),) * 32,
        source_opens=source_opens,
        source_closes=source_closes,
        quote_volume=quote,
        taker_buy_quote=bought,
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal(0),
    )
    assert result.buy_count == result.sell_count == 1
    assert result.ending_equity == Decimal(1000) / Decimal("1.001") * Decimal("0.999")
