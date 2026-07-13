import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engines.reference.cftc_positioning import (  # noqa: E402
    positioning_events,
    simulate_positioning_ledger,
)
from tios.strategy.cftc_positioning import (  # noqa: E402
    PositioningObservation,
    project_positioning_pulses,
)


def test_reference_matches_canonical_and_accounts_for_costs() -> None:
    start = datetime(2025, 1, 7, tzinfo=UTC)
    report_dates = tuple(start + timedelta(days=7 * index) for index in range(14))
    available_at = tuple(value + timedelta(days=8) for value in report_dates)
    values = tuple(Decimal(value) for value in (("-0.1", "0.1") * 6 + ("-0.1", "0.8")))
    spot_opens = tuple(available_at[-1] + timedelta(hours=index) for index in range(170))
    kwargs = {
        "spot_opens": spot_opens,
        "report_dates": report_dates,
        "available_at": available_at,
        "values": values,
        "interpretation": "ALIGNED_HIGH",
        "baseline_weeks": 13,
        "threshold": Decimal("0.5"),
    }
    entries, exits = positioning_events(**kwargs)
    canonical = project_positioning_pulses(
        tuple(
            PositioningObservation(report, available, value)
            for report, available, value in zip(report_dates, available_at, values, strict=True)
        ),
        spot_opens,
        interpretation="ALIGNED_HIGH",
        baseline_weeks=13,
        threshold=Decimal("0.5"),
    )
    assert [spot_opens[i] for i, value in enumerate(entries) if value] == [canonical[0].open_time]
    assert [spot_opens[i] for i, value in enumerate(exits) if value] == [canonical[1].open_time]
    result = simulate_positioning_ledger(
        **kwargs,
        opens=tuple(Decimal("100") for _ in spot_opens),
        closes=tuple(Decimal("100") for _ in spot_opens),
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal("1"),
    )
    assert result.buy_count == result.sell_count == result.completed_trades == 1
    assert result.ending_equity < Decimal("1000")
