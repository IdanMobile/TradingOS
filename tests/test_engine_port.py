"""T-006-01 acceptance: normalization goldens on synthetic engine output +
fee recomputation utility works (and can fail)."""

from datetime import UTC, datetime
from decimal import Decimal

from tios.core_types.engine import (
    MANDATORY_GRID,
    EquityPoint,
    FeeSlippageScenario,
    NormalizedResult,
    Side,
    Trade,
)
from tios.parity.fees import audit_fees, expected_fee

F1S1 = MANDATORY_GRID[1]


def trade(price: str, qty: str, fee: str) -> Trade:
    return Trade(
        ts_signal=None,
        ts_order=None,
        ts_fill=datetime(2025, 1, 1, tzinfo=UTC),
        side=Side.BUY,
        price=Decimal(price),
        qty=Decimal(qty),
        fee=Decimal(fee),
    )


def result(trades: tuple[Trade, ...], scenario: FeeSlippageScenario = F1S1) -> NormalizedResult:
    return NormalizedResult(
        engine="synthetic",
        sv_id="SV-test",
        dataset_id="DS-CRYPTO-SPOT-BAKEOFF-V1",
        scenario=scenario,
        trades=trades,
        equity_curve=(EquityPoint(datetime(2025, 1, 1, tzinfo=UTC), Decimal("1000")),),
        metrics={"total_return": Decimal("0")},
    )


def test_mandatory_grid_matches_spec() -> None:
    ids = [s.scenario_id for s in MANDATORY_GRID]
    assert ids == ["F0/S0", "F1/S1", "F1/S2", "F1/S3", "F2/S2", "F2/S3"]
    assert MANDATORY_GRID[0].diagnostic_only  # F0/S0 never economic evidence
    assert all(not s.diagnostic_only for s in MANDATORY_GRID[1:])
    assert MANDATORY_GRID[1].fee_rate_per_side == Decimal("0.001")  # F1 = 0.10%/side
    assert MANDATORY_GRID[4].fee_rate_per_side == Decimal("0.0015")  # F2 = 1.5×F1


def test_fee_golden_exact_decimal() -> None:
    # golden: 0.10% of 96340.60 * 0.5 = 48.17030 exactly (decimal, no float drift)
    t = trade("96340.60", "0.5", "48.17030")
    assert expected_fee(t, F1S1.fee_rate_per_side) == Decimal("48.1703000")
    assert audit_fees(result((t,))) == []


def test_fee_audit_flags_wrong_fee() -> None:
    t = trade("100", "1", "0.09")  # engine reported 0.09, correct is 0.10
    mismatches = audit_fees(result((t,)))
    assert len(mismatches) == 1
    assert mismatches[0].expected_fee == Decimal("0.100")
    assert mismatches[0].deviation == Decimal("0.010")


def test_fee_audit_zero_fee_diagnostic_scenario() -> None:
    t = trade("100", "1", "0")
    assert audit_fees(result((t,), scenario=MANDATORY_GRID[0])) == []
