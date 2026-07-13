"""Check the universe search screens each strategy over multiple datasets (no files)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

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


def test_all_strategies_are_loaded() -> None:
    assert len(uni.ALL_STRATEGIES) == 37  # 32 public (incl. 4 patterns) + 5 signal
    assert len({s.strategy_id for s in uni.ALL_STRATEGIES}) == 37


def test_best_context_ranking_does_not_use_holdout() -> None:
    def always_long(candles):
        n = len(candles["open"])
        return [True] * n, [False] * n

    def never_trade(candles):
        n = len(candles["open"])
        return [False] * n, [False] * n

    strong_train = [100 + i for i in range(30)]
    weak_train = [100 + i / 10 for i in range(30)]
    validation = [130 + i / 10 for i in range(30)]
    crash_holdout = [133 - i for i in range(30)]
    rocket_holdout = [133 + 10 * i for i in range(30)]
    strategy = SimpleNamespace(
        strategy_id="TEST",
        variants={"always-long": always_long, "never-trade": never_trade},
    )

    result = uni.evaluate(
        strategy,
        [
            _dataset("STRONG_TRAIN_1h", strong_train + validation + crash_holdout),
            _dataset("STRONG_HOLDOUT_1h", weak_train + validation + rocket_holdout),
        ],
    )

    assert result["best_context"]["dataset"] == "STRONG_TRAIN_1h"
    assert result["best_context"]["selection_partition"] == "train"
    assert result["best_context"]["holdout_used_for_selection"] is False


def test_report_is_method_blocked_without_global_candidate(monkeypatch) -> None:
    monkeypatch.setattr(uni, "_datasets", lambda: [])
    monkeypatch.setattr(uni, "ALL_STRATEGIES", ())
    report = uni.build_report()
    assert report["winner_selected"] is False
    assert report["search_lineage_complete"] is False
    assert report["promotion_status"] == "METHOD_BLOCKED"
    assert report["screen"]["best_context_ranking_partition"] == "train"
    assert report["screen"]["global_candidate_frozen"] is False
    assert report["screen"]["promotion_eligible"] is False
