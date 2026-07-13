"""Known-answer fixtures for pure two-leg carry accounting (offline only)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.validation.carry_accounting import (
    CarryEventKind,
    CarryLifecycleEvent,
    MissingCarryDataError,
    account_carry_observation,
    allocate_equal_notional,
    run_carry_lifecycle,
    short_perp_funding_cashflow,
    turnover_and_fees,
    two_leg_basis_pnl,
)

D = Decimal


def _allocation():
    return allocate_equal_notional(
        total_capital=D("1500"),
        reserve_fraction=D("0.2"),
        initial_margin_fraction=D("0.25"),
        margin_buffer_fraction=D("0.25"),
    )


def _no_costs():
    return turnover_and_fees(
        previous_spot_notional=D("800"),
        previous_perp_notional=D("800"),
        target_spot_notional=D("800"),
        target_perp_notional=D("800"),
        spot_fee_bps=D("10"),
        perp_fee_bps=D("20"),
    )


def test_capital_sizes_equal_notionals_and_explicit_margin_buffer() -> None:
    allocation = _allocation()
    assert allocation.reserve_capital == D("300")
    assert allocation.deployable_capital == D("1200")
    assert allocation.spot_notional == allocation.perp_notional == D("800")
    assert allocation.initial_margin == allocation.margin_buffer == D("200")
    assert allocation.perp_collateral == D("400")
    assert allocation.gross_notional == D("1600")
    assert allocation.spot_notional + allocation.perp_collateral == D("1200")


def test_funding_and_basis_pnl_are_signed_for_long_spot_short_perp() -> None:
    assert short_perp_funding_cashflow(
        short_notional_at_settlement=D("800"), settled_funding_rate=D("0.001")
    ) == D("0.800")
    assert short_perp_funding_cashflow(
        short_notional_at_settlement=D("800"), settled_funding_rate=D("-0.001")
    ) == D("-0.800")

    legs = two_leg_basis_pnl(
        spot_notional=D("800"),
        perp_notional=D("800"),
        spot_entry_price=D("100"),
        spot_current_price=D("110"),
        perp_entry_price=D("100"),
        perp_current_price=D("112"),
    )
    assert legs.spot_quantity == legs.perp_quantity == D("8")
    assert legs.spot_pnl == D("80")
    assert legs.perp_pnl == D("-96")
    assert legs.basis_pnl == D("-16")


def test_rehedging_turnover_charges_each_leg_without_double_counting() -> None:
    costs = turnover_and_fees(
        previous_spot_notional=D("800"),
        previous_perp_notional=D("800"),
        target_spot_notional=D("900"),
        target_perp_notional=D("850"),
        spot_fee_bps=D("10"),
        perp_fee_bps=D("20"),
    )
    assert costs.spot_turnover == D("100")
    assert costs.perp_turnover == D("50")
    assert costs.total_turnover == D("150")
    assert costs.spot_fee == costs.perp_fee == D("0.1")
    assert costs.total_fee == D("0.2")


def test_complete_observation_accounts_capital_and_isolated_margin() -> None:
    costs = turnover_and_fees(
        previous_spot_notional=D("800"),
        previous_perp_notional=D("800"),
        target_spot_notional=D("900"),
        target_perp_notional=D("850"),
        spot_fee_bps=D("10"),
        perp_fee_bps=D("20"),
    )
    result = account_carry_observation(
        allocation=_allocation(),
        spot_entry_price=D("100"),
        spot_current_price=D("110"),
        perp_entry_price=D("100"),
        perp_current_price=D("112"),
        funding_mark_price=D("112"),
        settled_funding_rate=D("0.001"),
        maintenance_margin_fraction=D("0.1"),
        costs=costs,
    )
    assert result.funding_notional == D("896")
    assert result.funding_cashflow == D("0.896")
    assert result.net_pnl == D("-15.304")  # -16 basis + .896 funding - .2 fees
    assert result.capital_after == D("1484.696")
    assert result.isolated_margin.margin_equity == D("304.796")
    assert result.isolated_margin.maintenance_requirement == D("89.6")
    assert result.isolated_margin.maintenance_buffer == D("215.196")
    assert result.isolated_margin.maintenance_breached is False


def test_basis_shock_can_breach_isolated_maintenance_despite_spot_gain() -> None:
    result = account_carry_observation(
        allocation=_allocation(),
        spot_entry_price=D("100"),
        spot_current_price=D("120"),
        perp_entry_price=D("100"),
        perp_current_price=D("160"),
        funding_mark_price=D("160"),
        settled_funding_rate=D("0"),
        maintenance_margin_fraction=D("0.1"),
        costs=_no_costs(),
    )
    assert result.legs.spot_pnl == D("160")
    assert result.legs.perp_pnl == D("-480")
    assert result.legs.basis_pnl == D("-320")
    assert result.isolated_margin.margin_equity == D("-80")
    assert result.isolated_margin.maintenance_requirement == D("128")
    assert result.isolated_margin.maintenance_breached is True


def test_missing_observation_fails_closed_instead_of_assuming_zero() -> None:
    with pytest.raises(
        MissingCarryDataError,
        match="missing carry data: funding_mark_price, settled_funding_rate",
    ):
        account_carry_observation(
            allocation=_allocation(),
            spot_entry_price=D("100"),
            spot_current_price=D("100"),
            perp_entry_price=D("100"),
            perp_current_price=D("100"),
            funding_mark_price=None,
            settled_funding_rate=None,
            maintenance_margin_fraction=D("0.1"),
            costs=_no_costs(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (("total_capital", D("0")), ("reserve_fraction", D("1"))),
)
def test_invalid_capital_inputs_are_rejected(field: str, value: Decimal) -> None:
    inputs = {
        "total_capital": D("1500"),
        "reserve_fraction": D("0.2"),
        "initial_margin_fraction": D("0.25"),
        "margin_buffer_fraction": D("0.25"),
    }
    inputs[field] = value
    with pytest.raises(ValueError):
        allocate_equal_notional(**inputs)


def _event(
    hours: int,
    kind: CarryEventKind,
    spot: str,
    perp: str,
    **kwargs,
) -> CarryLifecycleEvent:
    return CarryLifecycleEvent(
        observed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=hours),
        kind=kind,
        spot_price=D(spot),
        perp_price=D(perp),
        **kwargs,
    )


def test_lifecycle_open_settle_rehedge_close_conserves_capital() -> None:
    events = (
        _event(0, CarryEventKind.OPEN, "100", "100", spot_fee_bps=D("10"), perp_fee_bps=D("10")),
        _event(
            8,
            CarryEventKind.SETTLE,
            "105",
            "106",
            settled_funding_rate=D("0.001"),
            funding_mark_price=D("106"),
        ),
        _event(
            16,
            CarryEventKind.REHEDGE,
            "104",
            "105",
            target_leg_notional=D("800"),
            spot_fee_bps=D("10"),
            perp_fee_bps=D("10"),
        ),
        _event(24, CarryEventKind.CLOSE, "106", "106", spot_fee_bps=D("10"), perp_fee_bps=D("10")),
    )
    result = run_carry_lifecycle(
        allocation=_allocation(), maintenance_margin_fraction=D("0.1"), events=events
    )

    assert result.status == "CLOSED"
    assert len(result.points) == 4
    assert result.points[2].fees.total_turnover > 0  # explicit equal-notional rehedge
    assert result.points[-1].spot_quantity == result.points[-1].perp_quantity == 0
    assert result.final_capital == (
        result.initial_capital
        + result.cumulative_basis_pnl
        + result.cumulative_funding
        - result.cumulative_fees
    )


def test_lifecycle_rejects_missing_or_nonmonotonic_observations() -> None:
    open_event = _event(0, CarryEventKind.OPEN, "100", "100")
    missing = CarryLifecycleEvent(
        observed_at=datetime(2026, 1, 1, 8, tzinfo=UTC),
        kind=CarryEventKind.SETTLE,
        spot_price=D("100"),
        perp_price=D("100"),
    )
    with pytest.raises(MissingCarryDataError, match="settled_funding_rate"):
        run_carry_lifecycle(
            allocation=_allocation(),
            maintenance_margin_fraction=D("0.1"),
            events=(open_event, missing),
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        run_carry_lifecycle(
            allocation=_allocation(),
            maintenance_margin_fraction=D("0.1"),
            events=(open_event, _event(0, CarryEventKind.CLOSE, "100", "100")),
        )
    with pytest.raises(ValueError, match="CLOSE must be the final"):
        run_carry_lifecycle(
            allocation=_allocation(),
            maintenance_margin_fraction=D("0.1"),
            events=(
                open_event,
                _event(8, CarryEventKind.CLOSE, "100", "100"),
                _event(
                    16,
                    CarryEventKind.SETTLE,
                    "100",
                    "100",
                    settled_funding_rate=D("0"),
                    funding_mark_price=D("100"),
                ),
            ),
        )


def test_lifecycle_margin_breach_is_terminal_and_not_closed() -> None:
    events = (
        _event(0, CarryEventKind.OPEN, "100", "100"),
        _event(
            8,
            CarryEventKind.SETTLE,
            "120",
            "160",
            settled_funding_rate=D("0"),
            funding_mark_price=D("160"),
        ),
        _event(16, CarryEventKind.CLOSE, "120", "160"),
    )
    result = run_carry_lifecycle(
        allocation=_allocation(), maintenance_margin_fraction=D("0.1"), events=events
    )

    assert result.status == "MARGIN_BREACH"
    assert len(result.points) == 2
    assert result.points[-1].isolated_margin.maintenance_breached is True
