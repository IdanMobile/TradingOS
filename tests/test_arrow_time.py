from datetime import UTC, datetime

import pyarrow as pa
import pytest

from tios.dataset.arrow_time import ArrowTimestampError, utc_datetimes


def test_utc_datetimes_preserves_values_across_arrow_units() -> None:
    expected = [
        datetime(2021, 1, 1, tzinfo=UTC),
        datetime(2026, 7, 21, 12, 34, 56, 123456, tzinfo=UTC),
    ]
    for unit in ("s", "ms", "us", "ns"):
        rounded = expected
        if unit == "s":
            rounded = [value.replace(microsecond=0) for value in expected]
        elif unit == "ms":
            rounded = [
                value.replace(microsecond=value.microsecond // 1000 * 1000) for value in expected
            ]
        column = pa.array(rounded, type=pa.timestamp(unit, tz="UTC"))
        assert utc_datetimes(column) == rounded


def test_utc_datetimes_rejects_naive_non_utc_null_and_submicrosecond_values() -> None:
    with pytest.raises(ArrowTimestampError, match="declare UTC"):
        utc_datetimes(pa.array([datetime(2026, 1, 1)], type=pa.timestamp("us")))
    with pytest.raises(ArrowTimestampError, match="cannot contain nulls"):
        utc_datetimes(pa.array([None], type=pa.timestamp("us", tz="UTC")))
    with pytest.raises(ArrowTimestampError, match="whole microseconds"):
        utc_datetimes(pa.array([1], type=pa.timestamp("ns", tz="UTC")))
