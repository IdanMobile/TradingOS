"""T-005-03 acceptance: all four baseline specs are VALID, and the hand-computed
golden signals in fixtures/micro/ match an independent recomputation from bars.csv.

The recomputation here deliberately uses plain Python (math/statistics), not any
engine or the producer's code paths — it is the second derivation of the goldens.
"""

import csv
import math
from pathlib import Path

import pytest

from tios.strategy.validator import validate_yaml

ROOT = Path(__file__).resolve().parent.parent
BASELINES = ROOT / "fixtures" / "strategies" / "baselines"
MICRO = ROOT / "fixtures" / "micro"


def load_bars() -> list[dict[str, float]]:
    with (MICRO / "bars.csv").open() as f:
        return [
            {k: float(v) for k, v in row.items() if k not in ("timestamp_open_utc",)}
            for row in csv.DictReader(f)
        ]


def load_golden(name: str) -> list[tuple[bool, bool]]:
    with (MICRO / f"expected_signals_{name}.csv").open() as f:
        return [(row["entry"] == "true", row["exit"] == "true") for row in csv.DictReader(f)]


BARS = load_bars()
CLOSES = [b["close"] for b in BARS]
HIGHS = [b["high"] for b in BARS]


def sma(values: list[float], window: int, i: int) -> float | None:
    if i + 1 < window:
        return None
    return sum(values[i + 1 - window : i + 1]) / window


@pytest.mark.parametrize(
    "path", sorted(BASELINES.glob("*.yaml")), ids=lambda p: p.stem.split("_")[0]
)
def test_baseline_specs_are_valid(path: Path) -> None:
    report = validate_yaml(path.read_text())
    assert report.verdict == "VALID", (path.name, report.errors)


def test_b1_golden() -> None:
    golden = load_golden("B1")
    computed = [(i == 0, False) for i in range(len(BARS))]
    assert computed == golden


def test_b2_golden() -> None:
    golden = load_golden("B2")
    computed = []
    for i in range(len(BARS)):
        fast, slow = sma(CLOSES, 3, i), sma(CLOSES, 5, i)
        if fast is None or slow is None:
            computed.append((False, False))
        else:
            computed.append((fast > slow, fast < slow))
    assert computed == golden


def test_b3_golden() -> None:
    golden = load_golden("B3")
    computed = []
    for i in range(len(BARS)):
        mid = sma(CLOSES, 3, i)
        if mid is None:
            computed.append((False, False))
            continue
        window = CLOSES[i - 2 : i + 1]
        s = math.sqrt(sum((c - mid) ** 2 for c in window) / 3)  # population std, ddof=0
        lower = mid - 1 * s
        computed.append((CLOSES[i] < lower, CLOSES[i] >= mid))
    assert computed == golden


def test_b4_golden() -> None:
    golden = load_golden("B4")
    computed = []
    for i in range(len(BARS)):
        entry = False
        if i >= 5:
            hh_prev5 = max(HIGHS[i - 5 : i])  # previous 5 bars, excluding current
            entry = CLOSES[i] > hh_prev5
        mid = sma(CLOSES, 3, i)
        exit_ = mid is not None and CLOSES[i] < mid
        computed.append((entry, exit_))
    assert computed == golden
