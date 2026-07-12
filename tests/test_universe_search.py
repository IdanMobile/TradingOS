"""Check the universe search screens each strategy over multiple datasets (no files)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.run_universe_search as uni  # noqa: E402


def _dataset(name: str, closes: list[float]) -> tuple[str, dict[str, list[Decimal]]]:
    s = [Decimal(str(c)) for c in closes]
    return name, {"open": s, "high": s, "low": s, "close": s, "volume": s,
                  "quote_volume": s, "taker_buy": s}  # fmt: skip


def test_evaluate_returns_structure_and_flags_screen() -> None:
    # A clean uptrend on one dataset; a trend strategy should produce a best_context.
    up = _dataset("UP_1h", [100 + i for i in range(400)])
    flat = _dataset("FLAT_1h", [100] * 400)
    strat = next(s for s in uni.ALL_STRATEGIES if s.strategy_id == "EXT-GOLDEN-CROSS")
    result = uni.evaluate(strat, [up, flat])
    assert result["strategy_id"] == "EXT-GOLDEN-CROSS"
    assert result["best_context"] is not None
    assert isinstance(result["screen_pass_contexts"], list)
    # Every reported pass-context must genuinely carry the screen_pass flag.
    assert all(c["screen_pass"] for c in result["screen_pass_contexts"])


def test_all_25_strategies_are_loaded() -> None:
    assert len(uni.ALL_STRATEGIES) == 25  # 20 public + 5 signal
    assert len({s.strategy_id for s in uni.ALL_STRATEGIES}) == 25
