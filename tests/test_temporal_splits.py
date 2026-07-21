from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tios.validation.splits import (
    HoldoutSealError,
    SplitError,
    holdout_accesses,
    split_temporal,
    walk_forward_folds,
)

ROWS = tuple(range(1000))


def test_split_is_chronological_and_contiguous() -> None:
    split = split_temporal(ROWS, train_fraction=0.6, validation_fraction=0.2)
    assert split.train[0] == 0
    assert split.train[-1] == 599
    split.freeze_selection()
    assert split.validation[0] == 600
    assert split.sizes() == {"train": 600, "validation": 200, "holdout": 200}


def test_gap_drops_boundary_bars() -> None:
    """Indicator windows straddling a boundary carry information across it."""
    split = split_temporal(ROWS, train_fraction=0.6, validation_fraction=0.2, gap_bars=10)
    split.freeze_selection()
    assert split.train[-1] == 599
    assert split.validation[0] == 610, "the ten bars after train must be dropped"


def test_validation_is_unavailable_until_selection_freezes() -> None:
    """Reading validation during selection turns it into a second training set."""
    split = split_temporal(ROWS)
    with pytest.raises(SplitError, match="unavailable until freeze_selection"):
        _ = split.validation

    split.freeze_selection()
    assert len(split.validation) == 200


def test_holdout_is_not_reachable_as_an_attribute() -> None:
    """The SUP-008 defect: reaching holdout data during selection."""
    split = split_temporal(ROWS)
    with pytest.raises(HoldoutSealError, match="not reachable as an attribute"):
        _ = split.holdout


def test_holdout_refuses_to_open_before_selection_is_frozen() -> None:
    split = split_temporal(ROWS)
    with pytest.raises(HoldoutSealError, match="selection must be frozen"):
        split.open_holdout(reason="final evaluation")


def test_holdout_refuses_to_open_inside_the_seal_window() -> None:
    """This project's live holdout is sealed until at least 2027-01-14."""
    sealed_until = datetime(2027, 1, 14, tzinfo=UTC)
    split = split_temporal(ROWS, sealed_until=sealed_until)
    split.freeze_selection()

    with pytest.raises(HoldoutSealError, match="sealed until"):
        split.open_holdout(reason="peek", now=datetime(2026, 7, 20, tzinfo=UTC))


def test_holdout_opens_after_the_seal_date() -> None:
    sealed_until = datetime(2027, 1, 14, tzinfo=UTC)
    split = split_temporal(ROWS, sealed_until=sealed_until)
    split.freeze_selection()

    data = split.open_holdout(reason="final evaluation", now=sealed_until + timedelta(days=1))

    assert len(data) == 200
    assert split.holdout_opened


def test_holdout_may_be_opened_only_once() -> None:
    """A holdout read twice is a holdout tuned against."""
    split = split_temporal(ROWS)
    split.freeze_selection()
    split.open_holdout(reason="final evaluation")

    with pytest.raises(HoldoutSealError, match="already been opened once"):
        split.open_holdout(reason="just checking again")


def test_opening_the_holdout_requires_a_reason() -> None:
    split = split_temporal(ROWS)
    split.freeze_selection()
    with pytest.raises(HoldoutSealError, match="requires a recorded reason"):
        split.open_holdout(reason="  ")


def test_holdout_access_is_recorded(tmp_path: Path) -> None:
    """An unrecorded read is indistinguishable from never having read it."""
    split = split_temporal(ROWS)
    split.freeze_selection()
    split.open_holdout(reason="final evaluation of FAM-X", root=tmp_path)

    accesses = holdout_accesses(tmp_path)
    assert len(accesses) == 1
    assert accesses[0]["reason"] == "final evaluation of FAM-X"
    assert accesses[0]["holdout_rows"] == 200


def test_no_accesses_recorded_when_holdout_never_opened(tmp_path: Path) -> None:
    split = split_temporal(ROWS)
    split.freeze_selection()
    assert holdout_accesses(tmp_path) == ()


def test_fractions_must_leave_a_holdout() -> None:
    with pytest.raises(SplitError, match="non-empty holdout"):
        split_temporal(ROWS, train_fraction=0.8, validation_fraction=0.2)


def test_empty_dataset_is_rejected() -> None:
    with pytest.raises(SplitError, match="empty dataset"):
        split_temporal([])


def test_dataset_too_small_for_the_gap_is_rejected() -> None:
    with pytest.raises(SplitError, match="too small"):
        split_temporal(tuple(range(10)), train_fraction=0.6, validation_fraction=0.2, gap_bars=50)


def test_selection_only_ever_sees_training_data() -> None:
    """End-to-end: a realistic search cannot touch validation or holdout."""
    split = split_temporal(ROWS, train_fraction=0.6, validation_fraction=0.2)

    # A parameter search over the training window.
    best = max(range(1, 20), key=lambda window: sum(split.train[-window:]))
    assert best

    # Everything else is still sealed at this point.
    with pytest.raises(SplitError):
        _ = split.validation
    with pytest.raises(HoldoutSealError):
        _ = split.holdout

    split.freeze_selection()
    assert len(split.validation) == 200


def test_walk_forward_folds_are_chronological_and_expanding() -> None:
    """Expanding windows keep early regimes; rolling windows discard them."""
    folds = walk_forward_folds(ROWS, fold_count=5)

    assert len(folds) == 5
    assert [fold.fold_id for fold in folds] == ["WF-1", "WF-2", "WF-3", "WF-4", "WF-5"]
    for fold in folds:
        assert fold.train[-1] < fold.test[0], "test block must follow training data"
    # Training sets grow monotonically.
    sizes = [len(fold.train) for fold in folds]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_walk_forward_gap_separates_train_from_test() -> None:
    folds = walk_forward_folds(ROWS, fold_count=4, gap_bars=15)
    for fold in folds:
        assert fold.test[0] - fold.train[-1] > 15


def test_walk_forward_rejects_too_few_folds() -> None:
    with pytest.raises(SplitError, match="at least two folds"):
        walk_forward_folds(ROWS, fold_count=1)


def test_walk_forward_rejects_an_empty_dataset() -> None:
    with pytest.raises(SplitError, match="empty dataset"):
        walk_forward_folds([])


def test_walk_forward_rejects_a_dataset_too_small_to_fold() -> None:
    with pytest.raises(SplitError, match="too small"):
        walk_forward_folds(tuple(range(3)), fold_count=10)


def test_walk_forward_refuses_when_the_gap_consumes_the_folds() -> None:
    with pytest.raises(SplitError, match="fewer than two usable folds"):
        walk_forward_folds(tuple(range(30)), fold_count=5, gap_bars=25)


def test_folds_never_reach_the_sealed_holdout() -> None:
    """Nested validation runs inside training data; the holdout stays untouched."""
    split = split_temporal(ROWS, train_fraction=0.6, validation_fraction=0.2)
    folds = walk_forward_folds(split.train, fold_count=3)

    highest_seen = max(max(fold.test) for fold in folds)
    assert highest_seen < 600, "folds must stay inside the training window"
    assert not split.holdout_opened
