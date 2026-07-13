"""Independent reference checks for D-075 event and cost accounting."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engines.reference.cross_venue_premium import (  # noqa: E402
    premium_events,
    simulate_premium_ledger,
)
from tios.strategy.cross_venue_premium import (  # noqa: E402
    PremiumObservation,
    project_premium_pulses,
)


def test_reference_events_match_canonical_and_charge_both_sides() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    source_opens = tuple(start + timedelta(hours=index) for index in range(169))
    source_closes = tuple(value + timedelta(minutes=59) for value in source_opens)
    premiums = tuple(
        Decimal("-0.001") if index % 2 == 0 else Decimal("0.001") for index in range(168)
    ) + (Decimal("0.01"),)
    spot_opens = tuple(start + timedelta(hours=index) for index in range(176))
    entries, exits = premium_events(
        spot_opens=spot_opens,
        source_opens=source_opens,
        source_closes=source_closes,
        premiums=premiums,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    canonical = project_premium_pulses(
        tuple(
            PremiumObservation(opened, closed, value)
            for opened, closed, value in zip(source_opens, source_closes, premiums, strict=True)
        ),
        spot_opens,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    assert [spot_opens[index] for index, flag in enumerate(entries) if flag] == [
        canonical[0].open_time
    ]
    assert [spot_opens[index] for index, flag in enumerate(exits) if flag] == [
        canonical[1].open_time
    ]
    result = simulate_premium_ledger(
        spot_opens=spot_opens,
        opens=(Decimal(100),) * len(spot_opens),
        closes=(Decimal(100),) * len(spot_opens),
        source_opens=source_opens,
        source_closes=source_closes,
        premiums=premiums,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal(0),
    )
    assert result.buy_count == result.sell_count == 1
    assert result.ending_equity == Decimal(1000) / Decimal("1.001") * Decimal("0.999")
