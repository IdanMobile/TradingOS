import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.reference.calendar_utc import calendar_events, simulate_calendar_ledger


def test_reference_events_are_exactly_adjacent_and_position_aware() -> None:
    start = datetime(2026, 7, 12, 22, tzinfo=UTC)
    timestamps = tuple(start + timedelta(hours=index) for index in range(51))
    entries, exits = calendar_events(timestamps, 0)
    assert [timestamps[index] for index, value in enumerate(entries) if value] == [
        datetime(2026, 7, 13, tzinfo=UTC)
    ]
    assert [timestamps[index] for index, value in enumerate(exits) if value] == [
        datetime(2026, 7, 14, tzinfo=UTC)
    ]


def test_reference_ledger_has_hand_derived_costed_result() -> None:
    timestamps = (
        datetime(2026, 7, 12, 23, tzinfo=UTC),
        datetime(2026, 7, 13, 0, tzinfo=UTC),
        datetime(2026, 7, 13, 23, tzinfo=UTC),
        datetime(2026, 7, 14, 0, tzinfo=UTC),
    )
    result = simulate_calendar_ledger(
        timestamps=timestamps,
        opens=(Decimal("100"), Decimal("100"), Decimal("110"), Decimal("110")),
        closes=(Decimal("100"), Decimal("100"), Decimal("110"), Decimal("110")),
        selected_weekday=0,
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal("1"),
    )
    expected_quantity = Decimal("1000") / (Decimal("100.01") * Decimal("1.001"))
    expected_equity = expected_quantity * Decimal("109.989") * Decimal("0.999")
    assert result.ending_equity == expected_equity
    assert (result.buy_count, result.sell_count, result.completed_trades) == (1, 1, 1)
    assert result.ending_held is False


def test_reference_expires_pending_fill_across_gap() -> None:
    timestamps = (
        datetime(2026, 7, 12, 23, tzinfo=UTC),
        datetime(2026, 7, 13, 1, tzinfo=UTC),
    )
    entries, exits = calendar_events(timestamps, 0)
    assert not any(entries) and not any(exits)


def test_reference_exits_held_position_at_first_open_after_gap() -> None:
    timestamps = (
        datetime(2026, 7, 12, 23, tzinfo=UTC),
        datetime(2026, 7, 13, 0, tzinfo=UTC),
        datetime(2026, 7, 13, 2, tzinfo=UTC),
    )
    entries, exits = calendar_events(timestamps, 0)
    assert entries == (False, True, False)
    assert exits == (False, False, True)
