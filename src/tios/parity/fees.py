"""Fee recomputation audit (T-006-01/T-006-07; SKILL_ENGINE_PARITY_AUDITOR).

Recomputes expected fee per trade from the scenario's per-side rate and flags
any trade whose engine-reported fee deviates beyond tolerance. Works on
NormalizedResult only (parity never touches raw engine output).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tios.core_types.engine import NormalizedResult, Trade


@dataclass(frozen=True)
class FeeMismatch:
    trade_index: int
    expected_fee: Decimal
    reported_fee: Decimal
    deviation: Decimal


def expected_fee(trade: Trade, fee_rate_per_side: Decimal) -> Decimal:
    return trade.price * trade.qty * fee_rate_per_side


def audit_fees(
    result: NormalizedResult, tolerance: Decimal = Decimal("0.00000001")
) -> list[FeeMismatch]:
    rate = result.scenario.fee_rate_per_side
    mismatches = []
    for i, t in enumerate(result.trades):
        exp = expected_fee(t, rate)
        dev = abs(exp - t.fee)
        if dev > tolerance:
            mismatches.append(FeeMismatch(i, exp, t.fee, dev))
    return mismatches
