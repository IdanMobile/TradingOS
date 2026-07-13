import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engines.reference.transaction_activity import (  # noqa: E402
    activity_events,
    simulate_activity_ledger,
)
from tios.strategy.transaction_activity import (  # noqa: E402
    ActivityObservation,
    project_activity_pulses,
)


def test_reference_matches_canonical_events_and_ledger_costs() -> None:
    source_days = tuple(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(5))
    counts = (100, 110, 90, 400, 500)
    spot_opens = tuple(datetime(2026, 1, 6, tzinfo=UTC) + timedelta(hours=i) for i in range(50))
    entries, exits = activity_events(
        spot_opens=spot_opens,
        source_days=source_days,
        counts=counts,
        side="HIGH",
        window=3,
        holding_days=1,
    )
    canonical = project_activity_pulses(
        tuple(
            ActivityObservation(day, count) for day, count in zip(source_days, counts, strict=True)
        ),
        spot_opens,
        side="HIGH",
        window=3,
        holding_days=1,
    )
    assert [spot_opens[i] for i, value in enumerate(entries) if value] == [canonical[0].open_time]
    assert [spot_opens[i] for i, value in enumerate(exits) if value] == [canonical[1].open_time]
    result = simulate_activity_ledger(
        spot_opens=spot_opens,
        opens=tuple(Decimal("100") for _ in spot_opens),
        closes=tuple(Decimal("100") for _ in spot_opens),
        source_days=source_days,
        counts=counts,
        side="HIGH",
        window=3,
        holding_days=1,
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal("1"),
    )
    assert result.buy_count == result.sell_count == result.completed_trades == 1
    assert result.ending_equity < Decimal("1000")
