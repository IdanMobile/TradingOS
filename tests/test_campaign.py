import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tios.validation.campaign import (
    CAMPAIGN_DIR,
    CampaignError,
    TrialScore,
    run_campaign,
    score_trade_significance,
)
from tios.validation.splits import HoldoutSealError, split_temporal
from tios.validation.trial_budget import trial_count

FAMILY_ARGS = {
    "family": "FAM-TEST-MOMENTUM",
    "search_space": {"window": [2, 3, 5, 8, 13]},
    "primary_endpoint": "per_bar_sharpe",
    "cost_model": {"fee_rate_per_side": 0.001, "slippage_bps": 1},
    "chronology": "2021-01-01/2026-06-30",
    "thresholds": {"pbo_max": 0.5, "dsr_min": 0.95},
    "stop_rules": "no_rescue_on_fail",
}
GRID = [{"window": w} for w in (2, 3, 5, 8, 13)]


def _rows() -> tuple[float, ...]:
    # Deterministic, mildly trending series; enough rows for folds and a holdout.
    return tuple(float((index * 7) % 23) for index in range(1000))


def _evaluate(window: Sequence[float], parameters: dict[str, Any]) -> float:
    size = int(parameters["window"])
    if not window:
        return 0.0
    return sum(window[-size:]) / size / 100.0


def test_campaign_records_every_trial_to_the_ledger(tmp_path: Path) -> None:
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path, split=split, parameter_grid=GRID, evaluate=_evaluate, **FAMILY_ARGS
    )

    assert result.raw_trials == 5
    assert result.ledger_trials == 5
    assert trial_count(tmp_path, result.registration_ref) == 5


def test_campaign_leaves_the_holdout_sealed(tmp_path: Path) -> None:
    """A campaign produces evidence; the holdout is what it is judged against, later."""
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path, split=split, parameter_grid=GRID, evaluate=_evaluate, **FAMILY_ARGS
    )

    assert result.holdout_sealed
    assert not split.holdout_opened
    with pytest.raises(HoldoutSealError):
        _ = split.holdout


def test_selection_happens_before_validation_is_readable(tmp_path: Path) -> None:
    """The evaluate callable must never see validation data during the search."""
    seen: list[tuple[float, ...]] = []

    def spy(window: Sequence[float], parameters: dict[str, Any]) -> float:
        seen.append(tuple(window))
        return _evaluate(window, parameters)

    split = split_temporal(_rows())
    run_campaign(tmp_path, split=split, parameter_grid=GRID, evaluate=spy, **FAMILY_ARGS)

    # Compared by content, not length: a fold's training window can coincidentally match
    # the validation length while being a prefix of train, which a length check would
    # flag as a leak that isn't one.
    train, validation = tuple(split.train), tuple(split.validation)
    assert split.selection_frozen
    assert seen[-1] == validation, "the final call is the one permitted validation read"
    for window in seen[:-1]:
        assert window != validation
        assert window == train[: len(window)], "search windows must be prefixes of train"


def test_campaign_is_never_promotable(tmp_path: Path) -> None:
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path, split=split, parameter_grid=GRID, evaluate=_evaluate, **FAMILY_ARGS
    )

    assert result.promotable is False
    payload = result.as_dict()
    assert payload["promotion_eligible"] is False
    assert payload["execution_authority"] == "NONE"


def test_wider_search_lowers_the_result_rather_than_hiding(tmp_path: Path) -> None:
    """The core property: deflation reads the ledger, so searching more costs more."""
    narrow_split = split_temporal(_rows())
    narrow = run_campaign(
        tmp_path,
        split=narrow_split,
        parameter_grid=GRID[:2],
        evaluate=_evaluate,
        **{**FAMILY_ARGS, "family": "FAM-NARROW"},
    )

    wide_grid = [{"window": w} for w in range(2, 40)]
    wide_split = split_temporal(_rows())
    wide = run_campaign(
        tmp_path,
        split=wide_split,
        parameter_grid=wide_grid,
        evaluate=_evaluate,
        **{**FAMILY_ARGS, "family": "FAM-WIDE", "search_space": {"window": list(range(2, 40))}},
    )

    assert wide.ledger_trials > narrow.ledger_trials
    assert narrow.dsr is not None and wide.dsr is not None
    # More searching raises the noise threshold a result must clear.
    assert wide.dsr["expected_maximum_noise_sharpe"] > narrow.dsr["expected_maximum_noise_sharpe"]


def test_empty_grid_is_rejected(tmp_path: Path) -> None:
    split = split_temporal(_rows())
    with pytest.raises(CampaignError, match="at least one parameter set"):
        run_campaign(tmp_path, split=split, parameter_grid=[], evaluate=_evaluate, **FAMILY_ARGS)


def test_campaign_writes_an_evidence_artifact(tmp_path: Path) -> None:
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path, split=split, parameter_grid=GRID, evaluate=_evaluate, **FAMILY_ARGS
    )

    artifact = tmp_path / CAMPAIGN_DIR / f"{result.registration_ref}.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text())
    assert payload["family"] == "FAM-TEST-MOMENTUM"
    assert payload["ledger_trials"] == 5
    assert payload["holdout_sealed"] is True


def test_sealed_split_keeps_the_campaign_away_from_future_data(tmp_path: Path) -> None:
    """Mirrors the live configuration: holdout sealed until at least 2027-01-14."""
    split = split_temporal(_rows(), sealed_until=datetime(2027, 1, 14, tzinfo=UTC))
    result = run_campaign(
        tmp_path, split=split, parameter_grid=GRID, evaluate=_evaluate, **FAMILY_ARGS
    )

    assert result.holdout_sealed
    with pytest.raises(HoldoutSealError, match="sealed until"):
        split.open_holdout(reason="early peek", now=datetime(2026, 12, 1, tzinfo=UTC))


def test_spawning_a_family_raises_the_bar_for_every_family(tmp_path: Path) -> None:
    """The property that lets an orchestrator admit families without a human saying stop.

    A candidate deflated against only its own family looks equally strong no matter how
    many other families were tried. Deflating hierarchy-wide means each additional family
    raises the noise threshold every result must clear — self-correcting by construction.
    """
    first = run_campaign(
        tmp_path,
        split=split_temporal(_rows()),
        parameter_grid=GRID,
        evaluate=_evaluate,
        **{**FAMILY_ARGS, "family": "FAM-A"},
    )
    assert first.admitted_families == 1
    assert first.dsr is not None
    bar_after_one = first.dsr["expected_maximum_noise_sharpe"]

    # Nine more families get admitted, each searching the same modest grid.
    for index in range(9):
        run_campaign(
            tmp_path,
            split=split_temporal(_rows()),
            parameter_grid=GRID,
            evaluate=_evaluate,
            **{
                **FAMILY_ARGS,
                "family": f"FAM-{index}",
                "chronology": f"2021-01-01/2026-06-{index + 1:02d}",
            },
        )

    last = run_campaign(
        tmp_path,
        split=split_temporal(_rows()),
        parameter_grid=GRID,
        evaluate=_evaluate,
        **{**FAMILY_ARGS, "family": "FAM-LAST", "chronology": "2020-01-01/2026-06-30"},
    )

    assert last.admitted_families >= 10
    assert last.ledger_trials == 5, "each family still searched only five parameter sets"
    assert last.hierarchy_trials > last.ledger_trials * 5
    assert last.dsr is not None
    # Same per-family search width, far higher bar — the outer search is now counted.
    assert last.dsr["expected_maximum_noise_sharpe"] > bar_after_one


def test_hierarchy_counts_are_reported_not_just_applied(tmp_path: Path) -> None:
    """An invisible correction is one a reader cannot audit."""
    result = run_campaign(
        tmp_path,
        split=split_temporal(_rows()),
        parameter_grid=GRID,
        evaluate=_evaluate,
        **FAMILY_ARGS,
    )
    payload = result.as_dict()
    assert payload["hierarchy_trials"] == result.hierarchy_trials
    assert payload["admitted_families"] == result.admitted_families
    assert "hierarchy-wide" in payload["interpretation"]


# --- D-112: trade-level significance invariants -------------------------------------------


def _trades(count: int, spread: float = 0.01) -> tuple[float, ...]:
    """A deterministic trade series with non-zero variance so a Sharpe is defined."""
    return tuple(spread * (((index % 5) - 2) + 0.1) for index in range(count))


def _bars(trades: tuple[float, ...], width: int = 40) -> tuple[float, ...]:
    """Trade PnL aligned to bar index (0.0 elsewhere), same width across trials."""
    bar = [0.0] * width
    for index, value in enumerate(trades[:width]):
        bar[index] = value
    return tuple(bar)


def _trade_evaluate(trades: int):
    """A TrialScore-returning evaluator that realises a fixed number of completed trades."""

    def evaluate(window: Sequence[float], parameters: dict[str, Any]) -> TrialScore:
        series = _trades(trades)
        return TrialScore(
            score=float(parameters["window"]) / 100.0,
            trade_returns=series,
            bar_returns=_bars(series),
        )

    return evaluate


def test_sample_count_must_equal_the_scored_series_length() -> None:
    """The F1 defect in one assertion: 3 completed trades scored as if 7630 bars.

    The old path fed ``sample_count = len(validation)`` while the Sharpe was computed over only
    in-position bars. The invariant now fails closed when the two diverge.
    """
    with pytest.raises(CampaignError, match="sample_count must equal"):
        score_trade_significance(
            observed_trade_returns=(0.01, 0.02, 0.03),
            trial_trade_returns=[(0.01, 0.02), (0.03, 0.01)],
            trial_bar_returns=[(0.01, 0.0), (0.0, 0.03)],
            hierarchy_trials=10,
            sample_count=7630,  # diverges from len(observed) == 3
            min_validation_trades=2,
        )


def test_zero_or_one_trade_is_insufficient_and_never_claims_a_dsr() -> None:
    for observed in [(), (0.05,)]:
        outcome = score_trade_significance(
            observed_trade_returns=observed,
            trial_trade_returns=[_trades(12), _trades(12, spread=0.02)],
            trial_bar_returns=[_bars(_trades(12)), _bars(_trades(12, spread=0.02))],
            hierarchy_trials=50,
            sample_count=len(observed),
            min_validation_trades=10,
        )
        assert outcome["status"] == "INSUFFICIENT_ACTIVITY"
        assert outcome["dsr"] is None
        assert outcome["observed_sharpe"] is None


def test_run_campaign_records_insufficient_activity_for_a_one_trade_validation(
    tmp_path: Path,
) -> None:
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path,
        split=split,
        parameter_grid=GRID,
        evaluate=_trade_evaluate(trades=1),
        **FAMILY_ARGS,
    )
    assert result.insufficient_activity is True
    assert result.dsr is None
    assert result.validation_trades == 1
    assert any("INSUFFICIENT_ACTIVITY" in blocker for blocker in result.blockers)
    assert result.as_dict()["insufficient_activity"] is True


def test_run_campaign_claims_a_dsr_only_with_enough_trades(tmp_path: Path) -> None:
    split = split_temporal(_rows())
    result = run_campaign(
        tmp_path,
        split=split,
        parameter_grid=GRID,
        evaluate=_trade_evaluate(trades=20),
        **FAMILY_ARGS,
    )
    assert result.insufficient_activity is False
    assert result.dsr is not None
    # The invariant surfaced on the result: the DSR's sample was the trade count.
    assert result.validation_trades == 20


def test_correlation_haircut_shrinks_the_effective_trial_count() -> None:
    """Correlated trials imply fewer independent bets than the raw hierarchy count."""
    observed = _trades(15)
    # Eight trials sharing the same active-bar pattern (scaled) are near-perfectly correlated.
    trial_trades = [_trades(15, spread=0.01 * (1 + index)) for index in range(8)]
    trial_bars = [_bars(_trades(15, spread=0.01 * (1 + index))) for index in range(8)]
    outcome = score_trade_significance(
        observed_trade_returns=observed,
        trial_trade_returns=trial_trades,
        trial_bar_returns=trial_bars,
        hierarchy_trials=100,
        sample_count=len(observed),
        min_validation_trades=10,
    )
    assert outcome["dsr"] is not None
    assert outcome["average_correlation"] > 0.5
    assert outcome["effective_trials"] < 100  # the raw hierarchy count is haircut down
