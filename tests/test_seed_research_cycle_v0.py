import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_seed_research_cycle_v0 import (  # noqa: E402
    FEES,
    INITIAL_CASH,
    rolling_mean,
    simulate_next_open,
)


def test_rolling_mean_waits_for_full_window() -> None:
    values = [Decimal("1"), Decimal("2"), Decimal("3")]
    assert rolling_mean(values, 2) == [None, Decimal("1.5"), Decimal("2.5")]


def test_next_open_simulation_uses_fees_and_closes_at_final_open() -> None:
    opens = [Decimal("10"), Decimal("10"), Decimal("20")]
    equity, trades = simulate_next_open(opens, [True, False, False], [False, False, False])
    expected_quantity = INITIAL_CASH * (Decimal("1") - FEES) / Decimal("10")
    expected_equity = expected_quantity * Decimal("20") * (Decimal("1") - FEES)
    assert equity == expected_equity
    assert trades == 1
