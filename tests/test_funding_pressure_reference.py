import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engines.reference.funding_pressure import funding_events, simulate_funding_ledger  # noqa: E402


def _hours(count: int) -> tuple[datetime, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(start + timedelta(hours=index) for index in range(count))


def test_reference_observation_after_hour_fills_at_next_hour_only() -> None:
    spot = _hours(4)
    entries, exits = funding_events(
        spot_opens=spot,
        calc_times=(spot[0] + timedelta(milliseconds=2),),
        rates=(Decimal("0.001"),),
        polarity="CONTINUATION",
        lookback=1,
        threshold=Decimal(0),
    )
    assert entries == (False, True, False, False)
    assert exits == (False, False, False, False)


def test_reference_delay_perturbation_moves_fill_one_bar_later() -> None:
    spot = _hours(4)
    entries, _ = funding_events(
        spot_opens=spot,
        calc_times=(spot[0] + timedelta(milliseconds=2),),
        rates=(Decimal("0.001"),),
        polarity="CONTINUATION",
        lookback=1,
        threshold=Decimal(0),
        delay_bars=1,
    )
    assert entries == (False, False, True, False)


def test_reference_gap_exit_wins_and_pending_gap_action_expires() -> None:
    spot = (_hours(2)[0], _hours(2)[1], _hours(4)[3])
    calc = (
        spot[0] + timedelta(milliseconds=2),
        spot[1] + timedelta(milliseconds=2),
    )
    entries, exits = funding_events(
        spot_opens=spot,
        calc_times=calc,
        rates=(Decimal("0.001"), Decimal("0.001")),
        polarity="CONTINUATION",
        lookback=1,
        threshold=Decimal(0),
    )
    assert entries == (False, True, False)
    assert exits == (False, False, True)


def test_reference_ledger_applies_adverse_costs_on_both_sides() -> None:
    spot = _hours(4)
    result = simulate_funding_ledger(
        spot_opens=spot,
        opens=(Decimal("100"),) * 4,
        closes=(Decimal("100"),) * 4,
        calc_times=(spot[0] + timedelta(milliseconds=2), spot[1] + timedelta(milliseconds=2)),
        rates=(Decimal("0.001"), Decimal("-0.001")),
        polarity="CONTINUATION",
        lookback=1,
        threshold=Decimal(0),
        fee_rate_per_side=Decimal("0.001"),
        slippage_bps_per_side=Decimal("1"),
    )
    assert result.buy_count == result.sell_count == result.completed_trades == 1
    assert result.ending_equity < Decimal("1000")
    assert result.ending_held is False
