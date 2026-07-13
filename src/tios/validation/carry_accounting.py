"""Pure, deterministic accounting primitives for a two-leg funding-carry hypothesis.

The model uses quote-currency ``Decimal`` amounts, a long spot leg, and a short
linear perpetual leg. Perpetual margin is isolated: spot gains are not silently
transferred to protect it. A liquidation result is only a maintenance-margin
breach at the supplied observation or shock, not venue-specific liquidation or
proof that the intraperiod price path survived.

There is no I/O, venue adapter, strategy selection, or promotion decision here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

_BPS = Decimal("10000")


class MissingCarryDataError(ValueError):
    """Required point-in-time carry observations are absent."""


@dataclass(frozen=True, slots=True)
class CarryAllocation:
    total_capital: Decimal
    reserve_capital: Decimal
    deployable_capital: Decimal
    spot_notional: Decimal
    perp_notional: Decimal
    initial_margin: Decimal
    margin_buffer: Decimal
    perp_collateral: Decimal
    gross_notional: Decimal


@dataclass(frozen=True, slots=True)
class TwoLegPnl:
    spot_quantity: Decimal
    perp_quantity: Decimal
    spot_current_notional: Decimal
    perp_current_notional: Decimal
    spot_pnl: Decimal
    perp_pnl: Decimal
    basis_pnl: Decimal


@dataclass(frozen=True, slots=True)
class CarryTradingCost:
    spot_turnover: Decimal
    perp_turnover: Decimal
    total_turnover: Decimal
    spot_fee: Decimal
    perp_fee: Decimal
    total_fee: Decimal


@dataclass(frozen=True, slots=True)
class IsolatedMarginState:
    margin_equity: Decimal
    maintenance_requirement: Decimal
    maintenance_buffer: Decimal
    maintenance_breached: bool


@dataclass(frozen=True, slots=True)
class CarryAccounting:
    legs: TwoLegPnl
    costs: CarryTradingCost
    funding_notional: Decimal
    funding_cashflow: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    capital_after: Decimal
    isolated_margin: IsolatedMarginState


class CarryEventKind(StrEnum):
    OPEN = "OPEN"
    SETTLE = "SETTLE"
    REHEDGE = "REHEDGE"
    CLOSE = "CLOSE"


@dataclass(frozen=True, slots=True)
class CarryLifecycleEvent:
    observed_at: datetime
    kind: CarryEventKind
    spot_price: Decimal | None
    perp_price: Decimal | None
    settled_funding_rate: Decimal | None = None
    funding_mark_price: Decimal | None = None
    target_leg_notional: Decimal | None = None
    spot_fee_bps: Decimal = Decimal(0)
    perp_fee_bps: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class CarryLifecyclePoint:
    observed_at: datetime
    kind: CarryEventKind
    spot_quantity: Decimal
    perp_quantity: Decimal
    basis_pnl: Decimal
    funding_cashflow: Decimal
    fees: CarryTradingCost
    capital_after: Decimal
    isolated_margin: IsolatedMarginState


@dataclass(frozen=True, slots=True)
class CarryLifecycleResult:
    status: str
    initial_capital: Decimal
    final_capital: Decimal
    cumulative_basis_pnl: Decimal
    cumulative_funding: Decimal
    cumulative_fees: Decimal
    points: tuple[CarryLifecyclePoint, ...]


def _finite(name: str, value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _nonnegative(name: str, value: Decimal) -> Decimal:
    value = _finite(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive(name: str, value: Decimal) -> Decimal:
    value = _finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def allocate_equal_notional(
    *,
    total_capital: Decimal,
    reserve_fraction: Decimal,
    initial_margin_fraction: Decimal,
    margin_buffer_fraction: Decimal,
) -> CarryAllocation:
    """Size equal entry notionals from capital after an explicit reserve.

    One unit of leg notional consumes one unit of spot cash plus
    ``initial_margin_fraction + margin_buffer_fraction`` units of isolated
    perpetual collateral. The function uses all non-reserved capital.
    """

    total_capital = _positive("total_capital", total_capital)
    reserve_fraction = _nonnegative("reserve_fraction", reserve_fraction)
    if reserve_fraction >= 1:
        raise ValueError("reserve_fraction must be less than one")
    initial_margin_fraction = _positive("initial_margin_fraction", initial_margin_fraction)
    margin_buffer_fraction = _nonnegative("margin_buffer_fraction", margin_buffer_fraction)

    reserve = total_capital * reserve_fraction
    deployable = total_capital - reserve
    leg_notional = deployable / (Decimal(1) + initial_margin_fraction + margin_buffer_fraction)
    initial_margin = leg_notional * initial_margin_fraction
    margin_buffer = leg_notional * margin_buffer_fraction
    collateral = initial_margin + margin_buffer
    return CarryAllocation(
        total_capital=total_capital,
        reserve_capital=reserve,
        deployable_capital=deployable,
        spot_notional=leg_notional,
        perp_notional=leg_notional,
        initial_margin=initial_margin,
        margin_buffer=margin_buffer,
        perp_collateral=collateral,
        gross_notional=leg_notional * 2,
    )


def two_leg_basis_pnl(
    *,
    spot_notional: Decimal,
    perp_notional: Decimal,
    spot_entry_price: Decimal,
    spot_current_price: Decimal,
    perp_entry_price: Decimal,
    perp_current_price: Decimal,
) -> TwoLegPnl:
    """Mark fixed-quantity long-spot and short-linear-perpetual legs."""

    spot_notional = _nonnegative("spot_notional", spot_notional)
    perp_notional = _nonnegative("perp_notional", perp_notional)
    spot_entry_price = _positive("spot_entry_price", spot_entry_price)
    spot_current_price = _positive("spot_current_price", spot_current_price)
    perp_entry_price = _positive("perp_entry_price", perp_entry_price)
    perp_current_price = _positive("perp_current_price", perp_current_price)

    spot_quantity = spot_notional / spot_entry_price
    perp_quantity = perp_notional / perp_entry_price
    spot_pnl = spot_quantity * (spot_current_price - spot_entry_price)
    perp_pnl = perp_quantity * (perp_entry_price - perp_current_price)
    return TwoLegPnl(
        spot_quantity=spot_quantity,
        perp_quantity=perp_quantity,
        spot_current_notional=spot_quantity * spot_current_price,
        perp_current_notional=perp_quantity * perp_current_price,
        spot_pnl=spot_pnl,
        perp_pnl=perp_pnl,
        basis_pnl=spot_pnl + perp_pnl,
    )


def short_perp_funding_cashflow(
    *, short_notional_at_settlement: Decimal, settled_funding_rate: Decimal
) -> Decimal:
    """Return funding cash flow; a positive settled rate credits the short."""

    short_notional_at_settlement = _nonnegative(
        "short_notional_at_settlement", short_notional_at_settlement
    )
    settled_funding_rate = _finite("settled_funding_rate", settled_funding_rate)
    return short_notional_at_settlement * settled_funding_rate


def turnover_and_fees(
    *,
    previous_spot_notional: Decimal,
    previous_perp_notional: Decimal,
    target_spot_notional: Decimal,
    target_perp_notional: Decimal,
    spot_fee_bps: Decimal,
    perp_fee_bps: Decimal,
) -> CarryTradingCost:
    """Account for entry, exit, or rehedging turnover between notional targets."""

    previous_spot_notional = _nonnegative("previous_spot_notional", previous_spot_notional)
    previous_perp_notional = _nonnegative("previous_perp_notional", previous_perp_notional)
    target_spot_notional = _nonnegative("target_spot_notional", target_spot_notional)
    target_perp_notional = _nonnegative("target_perp_notional", target_perp_notional)
    spot_fee_bps = _nonnegative("spot_fee_bps", spot_fee_bps)
    perp_fee_bps = _nonnegative("perp_fee_bps", perp_fee_bps)

    spot_turnover = abs(target_spot_notional - previous_spot_notional)
    perp_turnover = abs(target_perp_notional - previous_perp_notional)
    spot_fee = spot_turnover * spot_fee_bps / _BPS
    perp_fee = perp_turnover * perp_fee_bps / _BPS
    return CarryTradingCost(
        spot_turnover=spot_turnover,
        perp_turnover=perp_turnover,
        total_turnover=spot_turnover + perp_turnover,
        spot_fee=spot_fee,
        perp_fee=perp_fee,
        total_fee=spot_fee + perp_fee,
    )


def account_carry_observation(
    *,
    allocation: CarryAllocation,
    spot_entry_price: Decimal | None,
    spot_current_price: Decimal | None,
    perp_entry_price: Decimal | None,
    perp_current_price: Decimal | None,
    funding_mark_price: Decimal | None,
    settled_funding_rate: Decimal | None,
    maintenance_margin_fraction: Decimal,
    costs: CarryTradingCost,
) -> CarryAccounting:
    """Account one complete observation or point shock, failing on absent data.

    Funding is calculated from the supplied settlement mark. Isolated margin
    equity receives short-perpetual funding and pays perpetual fees, while spot
    fees remain outside that isolated margin account.
    """

    observations = {
        "spot_entry_price": spot_entry_price,
        "spot_current_price": spot_current_price,
        "perp_entry_price": perp_entry_price,
        "perp_current_price": perp_current_price,
        "funding_mark_price": funding_mark_price,
        "settled_funding_rate": settled_funding_rate,
    }
    missing = [name for name, value in observations.items() if value is None]
    if missing:
        raise MissingCarryDataError("missing carry data: " + ", ".join(missing))

    assert spot_entry_price is not None
    assert spot_current_price is not None
    assert perp_entry_price is not None
    assert perp_current_price is not None
    assert funding_mark_price is not None
    assert settled_funding_rate is not None

    maintenance_margin_fraction = _nonnegative(
        "maintenance_margin_fraction", maintenance_margin_fraction
    )
    legs = two_leg_basis_pnl(
        spot_notional=allocation.spot_notional,
        perp_notional=allocation.perp_notional,
        spot_entry_price=spot_entry_price,
        spot_current_price=spot_current_price,
        perp_entry_price=perp_entry_price,
        perp_current_price=perp_current_price,
    )
    funding_notional = legs.perp_quantity * _positive("funding_mark_price", funding_mark_price)
    funding = short_perp_funding_cashflow(
        short_notional_at_settlement=funding_notional,
        settled_funding_rate=settled_funding_rate,
    )
    gross_pnl = legs.basis_pnl + funding
    net_pnl = gross_pnl - costs.total_fee
    margin_equity = allocation.perp_collateral + legs.perp_pnl + funding - costs.perp_fee
    maintenance = legs.perp_current_notional * maintenance_margin_fraction
    maintenance_buffer = margin_equity - maintenance
    return CarryAccounting(
        legs=legs,
        costs=costs,
        funding_notional=funding_notional,
        funding_cashflow=funding,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        capital_after=allocation.total_capital + net_pnl,
        isolated_margin=IsolatedMarginState(
            margin_equity=margin_equity,
            maintenance_requirement=maintenance,
            maintenance_buffer=maintenance_buffer,
            maintenance_breached=margin_equity <= maintenance,
        ),
    )


def run_carry_lifecycle(
    *,
    allocation: CarryAllocation,
    maintenance_margin_fraction: Decimal,
    events: tuple[CarryLifecycleEvent, ...],
) -> CarryLifecycleResult:
    """Reduce an explicit open/settle/rehedge/close sequence.

    Quantities are marked between observations. A rehedge resets both legs to one
    supplied equal notional at the current marks and charges each leg's turnover.
    Isolated collateral is fixed: collateral transfers and venue liquidation paths
    are deliberately outside this fixture.
    """

    if not events or events[0].kind is not CarryEventKind.OPEN:
        raise ValueError("carry lifecycle must start with OPEN")
    maintenance_margin_fraction = _nonnegative(
        "maintenance_margin_fraction", maintenance_margin_fraction
    )
    spot_qty = Decimal(0)
    perp_qty = Decimal(0)
    previous_spot: Decimal | None = None
    previous_perp: Decimal | None = None
    previous_time: datetime | None = None
    capital = allocation.total_capital
    margin_equity = allocation.perp_collateral
    cumulative_basis = Decimal(0)
    cumulative_funding = Decimal(0)
    cumulative_fees = Decimal(0)
    points: list[CarryLifecyclePoint] = []
    status = "OPEN"

    for index, event in enumerate(events):
        if index > 0 and events[index - 1].kind is CarryEventKind.CLOSE:
            raise ValueError("CLOSE must be the final lifecycle event")
        if event.observed_at.tzinfo is None or event.observed_at.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware")
        if previous_time is not None and event.observed_at <= previous_time:
            raise ValueError("event timestamps must be strictly increasing")
        if event.spot_price is None or event.perp_price is None:
            raise MissingCarryDataError("missing carry data: spot_price, perp_price")
        spot_price = _positive("spot_price", event.spot_price)
        perp_price = _positive("perp_price", event.perp_price)

        spot_pnl = Decimal(0) if previous_spot is None else spot_qty * (spot_price - previous_spot)
        perp_pnl = Decimal(0) if previous_perp is None else perp_qty * (previous_perp - perp_price)
        basis_pnl = spot_pnl + perp_pnl

        if event.kind is CarryEventKind.SETTLE:
            if event.settled_funding_rate is None or event.funding_mark_price is None:
                raise MissingCarryDataError(
                    "missing carry data: settled_funding_rate, funding_mark_price"
                )
            funding = short_perp_funding_cashflow(
                short_notional_at_settlement=perp_qty
                * _positive("funding_mark_price", event.funding_mark_price),
                settled_funding_rate=event.settled_funding_rate,
            )
            target = None
        else:
            if event.settled_funding_rate not in (None, Decimal(0)):
                raise ValueError("funding is permitted only on SETTLE events")
            funding = Decimal(0)
            target = event.target_leg_notional

        if event.kind is CarryEventKind.OPEN:
            if index != 0:
                raise ValueError("OPEN is permitted only as the first event")
            target = allocation.spot_notional
        elif event.kind is CarryEventKind.REHEDGE:
            if target is None or target <= 0:
                raise ValueError("REHEDGE requires a positive target_leg_notional")
        elif event.kind is CarryEventKind.CLOSE:
            target = Decimal(0)

        current_spot_notional = spot_qty * spot_price
        current_perp_notional = perp_qty * perp_price
        costs = turnover_and_fees(
            previous_spot_notional=current_spot_notional,
            previous_perp_notional=current_perp_notional,
            target_spot_notional=current_spot_notional if target is None else target,
            target_perp_notional=current_perp_notional if target is None else target,
            spot_fee_bps=event.spot_fee_bps,
            perp_fee_bps=event.perp_fee_bps,
        )
        capital += basis_pnl + funding - costs.total_fee
        margin_equity += perp_pnl + funding - costs.perp_fee
        cumulative_basis += basis_pnl
        cumulative_funding += funding
        cumulative_fees += costs.total_fee

        if target is not None:
            spot_qty = target / spot_price
            perp_qty = target / perp_price
        maintenance = perp_qty * perp_price * maintenance_margin_fraction
        margin_state = IsolatedMarginState(
            margin_equity=margin_equity,
            maintenance_requirement=maintenance,
            maintenance_buffer=margin_equity - maintenance,
            maintenance_breached=margin_equity <= maintenance,
        )
        points.append(
            CarryLifecyclePoint(
                observed_at=event.observed_at,
                kind=event.kind,
                spot_quantity=spot_qty,
                perp_quantity=perp_qty,
                basis_pnl=basis_pnl,
                funding_cashflow=funding,
                fees=costs,
                capital_after=capital,
                isolated_margin=margin_state,
            )
        )
        previous_spot, previous_perp, previous_time = spot_price, perp_price, event.observed_at
        if margin_state.maintenance_breached:
            status = "MARGIN_BREACH"
            break
        status = "CLOSED" if event.kind is CarryEventKind.CLOSE else "OPEN"

    return CarryLifecycleResult(
        status=status,
        initial_capital=allocation.total_capital,
        final_capital=capital,
        cumulative_basis_pnl=cumulative_basis,
        cumulative_funding=cumulative_funding,
        cumulative_fees=cumulative_fees,
        points=tuple(points),
    )
