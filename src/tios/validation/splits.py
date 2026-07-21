"""Temporal splits that make holdout leakage structurally impossible.

SUP-008 found that best parameters were selected on the full dataset before thirds and
holdout were reported. The holdout influenced selection, so the reported out-of-sample
performance was not out of sample. Nothing in the code prevented it — the discipline
existed only as an intention, and intentions do not survive a deadline.

This module makes the intention structural. A `TemporalSplit` hands out training data
freely, releases validation only after selection is explicitly frozen, and refuses holdout
access entirely until the seal date passes. Every holdout read is recorded and may happen
exactly once, because a holdout read twice is a holdout tuned against.

Two properties that are easy to get wrong and expensive to get wrong:

*Splits are chronological, never random.* Shuffling time series leaks the future into the
past through overlapping indicator windows and autocorrelation, and a random split will
look excellent right up until it is traded.

*A gap separates each segment.* Indicators with lookback windows straddle a boundary and
carry information across it. The gap must be at least the longest lookback in the family.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ACCESS_LOG = Path("artifacts") / "validation" / "holdout_access.jsonl"


class SplitError(RuntimeError):
    """Raised when a split is misconfigured or accessed out of order."""


class HoldoutSealError(SplitError):
    """Raised on any attempt to reach sealed holdout data."""


@dataclass
class TemporalSplit[T]:
    """A chronological train/validation/holdout split with an enforced access order.

    The holdout is stored but unreachable through any ordinary attribute: reaching it
    requires `open_holdout`, which checks the seal date, records the access, and permits
    exactly one read for the lifetime of the split.
    """

    _train: Sequence[T]
    _validation: Sequence[T]
    _holdout: Sequence[T]
    sealed_until: datetime | None = None
    gap_bars: int = 0
    _selection_frozen: bool = field(default=False, repr=False)
    _holdout_opened: bool = field(default=False, repr=False)

    @property
    def train(self) -> Sequence[T]:
        """Always available. Parameter search happens here and only here."""
        return self._train

    @property
    def validation(self) -> Sequence[T]:
        """Available only after selection is frozen.

        Reading validation while selection is still open is how a "validation" set quietly
        becomes a second training set.
        """
        if not self._selection_frozen:
            raise SplitError(
                "validation data is unavailable until freeze_selection() is called; "
                "selecting against validation makes it a training set"
            )
        return self._validation

    @property
    def holdout(self) -> Sequence[T]:
        raise HoldoutSealError(
            "holdout is not reachable as an attribute; use open_holdout(reason=...) "
            "which enforces the seal date and records the one permitted access"
        )

    def freeze_selection(self) -> None:
        """Declare parameter selection complete. Irreversible for this split."""
        self._selection_frozen = True

    @property
    def selection_frozen(self) -> bool:
        return self._selection_frozen

    def open_holdout(
        self,
        *,
        reason: str,
        root: Path | None = None,
        now: datetime | None = None,
    ) -> Sequence[T]:
        """Break the seal once, with a recorded reason.

        Refuses before the seal date, refuses while selection is unfrozen, and refuses a
        second read. The recording is not bookkeeping: an unrecorded holdout read is
        indistinguishable from never having read it, which is precisely how SUP-008
        happened.
        """
        moment = now or datetime.now(tz=UTC)

        if not reason.strip():
            raise HoldoutSealError("opening the holdout requires a recorded reason")
        if not self._selection_frozen:
            raise HoldoutSealError(
                "selection must be frozen before the holdout may be opened; "
                "otherwise the holdout can still influence parameter choice"
            )
        if self.sealed_until is not None and moment < self.sealed_until:
            raise HoldoutSealError(
                f"holdout is sealed until {self.sealed_until.isoformat()}; "
                f"current time {moment.isoformat()} is inside the seal window"
            )
        if self._holdout_opened:
            raise HoldoutSealError(
                "the holdout has already been opened once; a second read means the "
                "result was tuned against it and the evidence is no longer out of sample"
            )

        self._holdout_opened = True
        if root is not None:
            _record_access(root, reason=reason, opened_at=moment, rows=len(self._holdout))
        return self._holdout

    @property
    def holdout_opened(self) -> bool:
        return self._holdout_opened

    def sizes(self) -> dict[str, int]:
        return {
            "train": len(self._train),
            "validation": len(self._validation),
            "holdout": len(self._holdout),
        }


def split_temporal[T](
    rows: Sequence[T],
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    gap_bars: int = 0,
    sealed_until: datetime | None = None,
) -> TemporalSplit[T]:
    """Split chronologically ordered rows into train/validation/holdout.

    `rows` must already be in chronological order; this function does not sort, because
    sorting silently would hide a caller passing shuffled data — the exact defect the
    split exists to prevent.

    `gap_bars` are dropped at each boundary. Set it to at least the longest indicator
    lookback in the family, or windows straddling the boundary carry information across it.
    """
    if not rows:
        raise SplitError("cannot split an empty dataset")
    if train_fraction <= 0 or validation_fraction < 0:
        raise SplitError("train_fraction must be positive and validation_fraction non-negative")
    if train_fraction + validation_fraction >= 1:
        raise SplitError(
            "train and validation fractions must leave a non-empty holdout; "
            f"got {train_fraction} + {validation_fraction}"
        )
    if gap_bars < 0:
        raise SplitError("gap_bars must be non-negative")

    total = len(rows)
    train_end = int(total * train_fraction)
    validation_end = train_end + int(total * validation_fraction)

    train = rows[:train_end]
    validation = rows[train_end + gap_bars : validation_end]
    holdout = rows[validation_end + gap_bars :]

    if not train or not holdout:
        raise SplitError(
            f"split produced an empty segment (train={len(train)}, holdout={len(holdout)}); "
            "the dataset is too small for these fractions and gap"
        )

    return TemporalSplit(
        _train=train,
        _validation=validation,
        _holdout=holdout,
        sealed_until=sealed_until,
        gap_bars=gap_bars,
    )


@dataclass(frozen=True)
class WalkForwardFold[T]:
    """One expanding-window fold: select on the past, evaluate on the next block."""

    fold_id: str
    train: Sequence[T]
    test: Sequence[T]

    def sizes(self) -> dict[str, int]:
        return {"train": len(self.train), "test": len(self.test)}


def walk_forward_folds[T](
    rows: Sequence[T],
    *,
    fold_count: int = 5,
    gap_bars: int = 0,
    min_train: int = 1,
) -> tuple[WalkForwardFold[T], ...]:
    """Chronological expanding-window folds for nested temporal validation.

    SUP-009 requires nested temporal validation so that a family's result is not a single
    lucky split. Each fold trains on everything before its test block and evaluates on the
    block itself, with a gap between them.

    Expanding rather than rolling: a rolling window discards early history, and for regime
    behaviour the early history is exactly what distinguishes a strategy that survived a
    regime change from one that never met it.

    Note this yields *pseudo* out-of-sample evidence. Every fold's data already existed when
    the family was designed, so it cannot substitute for the sealed prospective holdout —
    it only detects a strategy that fails to hold up across time within known history.
    """
    if not rows:
        raise SplitError("cannot fold an empty dataset")
    if fold_count < 2:
        raise SplitError("nested validation requires at least two folds")
    if gap_bars < 0 or min_train < 1:
        raise SplitError("gap_bars must be non-negative and min_train at least 1")

    total = len(rows)
    block = total // (fold_count + 1)
    if block < 1:
        raise SplitError(
            f"dataset of {total} rows is too small for {fold_count} folds; "
            "each fold needs at least one row"
        )

    folds: list[WalkForwardFold[T]] = []
    for index in range(fold_count):
        train_end = block * (index + 1)
        test_start = train_end + gap_bars
        test_end = min(test_start + block, total)

        train = rows[:train_end]
        test = rows[test_start:test_end]
        if len(train) < min_train or not test:
            continue
        folds.append(WalkForwardFold(f"WF-{index + 1}", train, test))

    if len(folds) < 2:
        raise SplitError(
            "fewer than two usable folds after applying the gap and minimum training size; "
            "the dataset is too short for this configuration"
        )
    return tuple(folds)


def _record_access(root: Path, *, reason: str, opened_at: datetime, rows: int) -> None:
    target = root / ACCESS_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "reason": reason,
                    "opened_at": opened_at.isoformat(),
                    "holdout_rows": rows,
                },
                sort_keys=True,
            )
            + "\n"
        )


def holdout_accesses(root: Path) -> tuple[dict[str, Any], ...]:
    """Every recorded holdout read. More than one for a family is a red flag."""
    target = root / ACCESS_LOG
    if not target.is_file():
        return ()
    return tuple(
        json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()
    )
