"""Fast, strict conversion of Arrow UTC timestamps to Python datetimes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyarrow as pa


class ArrowTimestampError(ValueError):
    """An Arrow timestamp column cannot be interpreted as exact UTC time."""


def utc_datetimes(column: pa.Array | pa.ChunkedArray) -> list[datetime]:
    """Convert UTC timestamps without PyArrow's per-value timezone lookup overhead.

    Arrow stores timestamps as epoch integers. Converting those integers directly is
    semantically equivalent to ``to_pylist()`` for UTC while avoiding repeated zoneinfo
    imports observed on large columns.
    """

    value_type = column.type
    if not pa.types.is_timestamp(value_type):
        raise ArrowTimestampError("column must have an Arrow timestamp type")
    if value_type.tz not in {"UTC", "+00:00"}:
        raise ArrowTimestampError("timestamp column must declare UTC timezone")
    values = column.cast(pa.int64()).to_pylist()
    factors = {"s": 1_000_000, "ms": 1_000, "us": 1}
    if value_type.unit in factors:
        factor = factors[value_type.unit]
        microseconds = [None if value is None else value * factor for value in values]
    elif value_type.unit == "ns":
        if any(value is not None and value % 1_000 for value in values):
            raise ArrowTimestampError("nanosecond values must align to whole microseconds")
        microseconds = [None if value is None else value // 1_000 for value in values]
    else:  # pragma: no cover - Arrow currently restricts timestamp units to these four
        raise ArrowTimestampError(f"unsupported timestamp unit: {value_type.unit}")
    if any(value is None for value in microseconds):
        raise ArrowTimestampError("timestamp column cannot contain nulls")
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return [epoch + timedelta(microseconds=value) for value in microseconds if value is not None]
