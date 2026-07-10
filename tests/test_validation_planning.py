from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tios.validation.planning import (
    chronological_split,
    compare_to_baselines,
    mandatory_grid_ids,
    parameter_neighborhood,
    walk_forward_windows,
)


def test_chronological_split_leaves_untouched_holdout() -> None:
    split = chronological_split(datetime(2021, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
    assert (
        split.development_end < split.validation_start < split.validation_end < split.holdout_start
    )


def test_walk_forward_windows_are_ordered_and_bounded() -> None:
    windows = walk_forward_windows(
        datetime(2021, 1, 1, tzinfo=UTC), datetime(2021, 2, 1, tzinfo=UTC), 10, 5, 5
    )
    assert windows
    assert all(w["train_end"] == w["test_start"] for w in windows)
    assert all(w["test_start"] < w["test_end"] for w in windows)


def test_planners_cover_grid_neighborhood_and_baselines() -> None:
    assert mandatory_grid_ids() == ("F0/S0", "F1/S1", "F1/S2", "F1/S3", "F2/S2", "F2/S3")
    assert len(parameter_neighborhood({"window": Decimal("5")})) == 3
    comparison = compare_to_baselines(
        Decimal("2"), {"cash": Decimal("0"), "buy_hold": Decimal("1")}
    )
    assert comparison["beats_all"]


def test_invalid_split_is_rejected() -> None:
    with pytest.raises(ValueError, match="holdout"):
        chronological_split(
            datetime(2021, 1, 1, tzinfo=UTC),
            datetime(2021, 1, 2, tzinfo=UTC),
            Decimal("0.8"),
            Decimal("0.2"),
        )
