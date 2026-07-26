"""Check the universe search screens each strategy over multiple datasets (no files)."""

from __future__ import annotations

import fcntl
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def _redirect_lock(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """Point the module's lock/report at tmp_path. No real search is ever run from these tests."""
    out = tmp_path / "universe_search"
    out.mkdir()
    lock, report = out / ".research_run.lock", out / "REPORT.json"
    monkeypatch.setattr(uni, "OUT", out)
    monkeypatch.setattr(uni, "RUN_LOCK", lock)
    monkeypatch.setattr(uni, "REPORT", report)
    return lock, report


def test_second_search_exits_3_and_writes_nothing(monkeypatch, tmp_path: Path) -> None:
    # D-119 Finding B: two concurrent searches would clobber the same output JSON. flock is held per
    # OPEN FILE DESCRIPTION, so a second open() of the same path conflicts even in this process —
    # which is exactly what a second `uv run scripts/run_universe_search.py` does.
    lock, report = _redirect_lock(monkeypatch, tmp_path)
    report.write_text('{"live": "holder-run"}\n', encoding="utf-8")
    before = report.read_bytes()
    # A search must never start; if the guard leaks, build_report is where it would.
    monkeypatch.setattr(uni, "build_report", lambda: pytest.fail("a second search started"))

    holder = lock.open("a+", encoding="utf-8")
    try:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        holder.write("holder")
        holder.flush()
        assert uni.main() == 3
    finally:
        holder.close()
    # The live holder's record and report survive untouched — no truncation, no partial write.
    assert report.read_bytes() == before
    assert lock.read_text(encoding="utf-8") == "holder"


def test_uncontended_lock_records_the_pid_and_releases(monkeypatch, tmp_path: Path) -> None:
    lock, _ = _redirect_lock(monkeypatch, tmp_path)
    with uni.exclusive_search_lock() as acquired:
        assert acquired is True
        assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()
    # Released on exit: the next start acquires immediately rather than wedging.
    with uni.exclusive_search_lock() as again:
        assert again is True

    # ...and released after an exception too, so a crashed search never wedges the next one.
    with pytest.raises(RuntimeError), uni.exclusive_search_lock() as third:
        assert third is True
        raise RuntimeError("search blew up")
    with uni.exclusive_search_lock() as fourth:
        assert fourth is True
