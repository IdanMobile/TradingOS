"""Run the frozen seven-trial UTC-weekday campaign without network or order authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from engines.reference.calendar_utc import simulate_calendar_ledger  # noqa: E402
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    implied_independent_trials,
    probability_of_backtest_overfitting_from_return_statistics,
    sharpe_variance_from_trials,
)

CAMPAIGN = ROOT / "research/CALENDAR_UTC_G1_G11_CAMPAIGN_V1.yaml"
OUTPUT_ROOT = ROOT / "artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1"
ENGINE_PYTHON = ROOT / "engines/vectorbt/.venv/bin/python"
WEEKDAYS = tuple(range(7))
SCENARIOS = (
    ("F0/S0", Decimal("0"), Decimal("0")),
    ("F1/S1", Decimal("0.001"), Decimal("1")),
    ("F1/S2", Decimal("0.001"), Decimal("5")),
    ("F1/S3", Decimal("0.001"), Decimal("10")),
    ("F2/S2", Decimal("0.0015"), Decimal("5")),
    ("F2/S3", Decimal("0.0015"), Decimal("10")),
)
SEGMENTS = {
    "development": ("2021-01-01", "2023-12-31 23:00:00+00:00"),
    "validation_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "reserved_2025_2026h1": ("2025-01-01", "2026-06-30 23:00:00+00:00"),
    "full": ("2021-01-01", "2026-06-30 23:00:00+00:00"),
    "year_2021": ("2021-01-01", "2021-12-31 23:00:00+00:00"),
    "year_2022": ("2022-01-01", "2022-12-31 23:00:00+00:00"),
    "year_2023": ("2023-01-01", "2023-12-31 23:00:00+00:00"),
    "year_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "year_2025": ("2025-01-01", "2025-12-31 23:00:00+00:00"),
    "year_2026_h1": ("2026-01-01", "2026-06-30 23:00:00+00:00"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _write_hashed_json(directory: Path, stem: str, payload: Mapping[str, object]) -> Path:
    encoded = _json_bytes(payload)
    path = directory / f"{stem}_{hashlib.sha256(encoded).hexdigest()}.json"
    path.write_bytes(encoded)
    return path


def _git_state() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def _pinned_files(campaign: Mapping[str, Any]) -> list[tuple[str, str]]:
    return [(item["path"], item["sha256"]) for item in campaign["pinned_files"]]


def preflight(*, require_clean: bool = True) -> dict[str, Any]:
    campaign = yaml.safe_load(CAMPAIGN.read_text(encoding="utf-8"))
    if campaign["status"] != "PREREGISTERED_NOT_RUN":
        raise RuntimeError("campaign is not preregistered and unrun")
    safety = campaign["safety"]
    expected = {
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "orders": "DISABLED",
        "network": "PROHIBITED",
        "credentials_required": False,
        "sealed_v2_holdout_access": "PROHIBITED",
    }
    if safety != expected:
        raise RuntimeError("campaign safety boundary changed")
    mismatches = [
        path
        for path, expected_hash in _pinned_files(campaign)
        if not (ROOT / path).is_file() or sha256(ROOT / path) != expected_hash
    ]
    if mismatches:
        raise RuntimeError(f"pinned file mismatch: {', '.join(mismatches)}")
    roster = campaign["trial_roster"]
    if [item["selected_weekday"] for item in roster] != list(WEEKDAYS):
        raise RuntimeError("trial roster must contain weekdays 0 through 6 exactly once")
    if campaign["method"]["raw_statistical_trial_count"] != 7:
        raise RuntimeError("raw statistical trial count must remain seven")
    if campaign["method"]["segments"] != {key: list(value) for key, value in SEGMENTS.items()}:
        raise RuntimeError("campaign segments differ from runner constants")
    spec_payload = yaml.safe_load((ROOT / campaign["canonical_spec"]["path"]).read_text())
    if validate(spec_payload).verdict != "VALID":
        raise RuntimeError("canonical strategy spec is not valid")
    spec = parse_spec(spec_payload)
    identities = {
        item["selected_weekday"]: create_version(
            spec, {"selected_weekday": item["selected_weekday"], "timezone": "UTC"}
        ).sv_id
        for item in roster
    }
    if any(item["strategy_version_id"] != identities[item["selected_weekday"]] for item in roster):
        raise RuntimeError("StrategyVersion identity drift")
    verification = json.loads(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_calendar_utc_data.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    if verification["status"] != "PASS" or verification["network_allowed"] is not False:
        raise RuntimeError("offline data verification failed")
    commit, dirty = _git_state()
    if require_clean and dirty:
        raise RuntimeError("campaign must start from a clean Git commit")
    if OUTPUT_ROOT.exists():
        raise RuntimeError("campaign output already exists")
    return {
        "campaign": campaign,
        "campaign_hash": sha256(CAMPAIGN),
        "commit": commit,
        "dirty": dirty,
        "data_verification": verification,
    }


def _load_rows(path: Path) -> tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]]:
    table = pq.read_table(path, columns=["timestamp_open_utc", "open", "close"])
    timestamps = tuple(table.column("timestamp_open_utc").to_pylist())
    opens = tuple(table.column("open").to_pylist())
    closes = tuple(table.column("close").to_pylist())
    if any(
        timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0
        for timestamp in timestamps
    ):
        raise RuntimeError("dataset timestamps must be UTC")
    return timestamps, opens, closes


def _segment_rows(
    rows: tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]],
    start: str,
    end: str,
) -> tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]]:
    lower = (
        datetime.fromisoformat(start).replace(tzinfo=UTC)
        if "+" not in start
        else datetime.fromisoformat(start)
    )
    upper = (
        datetime.fromisoformat(end).replace(tzinfo=UTC)
        if "+" not in end
        else datetime.fromisoformat(end)
    )
    selected = [index for index, timestamp in enumerate(rows[0]) if lower <= timestamp <= upper]
    if not selected:
        raise RuntimeError("empty campaign segment")
    return tuple(tuple(column[index] for index in selected) for column in rows)  # type: ignore[return-value]


def _return_hash(values: list[float]) -> str:
    import struct

    return hashlib.sha256(
        b"".join(struct.pack("<d", round(value, 12)) for value in values)
    ).hexdigest()


def _metrics(values: list[float], ending_equity: Decimal, buys: int, sells: int) -> dict[str, Any]:
    average = mean(values)
    variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
    deviation = math.sqrt(variance)
    equity = peak = 1.0
    drawdown = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1.0)
    return {
        "total_return": float(ending_equity / Decimal("1000") - 1),
        "sharpe_per_bar": average / deviation if deviation > 0 else 0.0,
        "max_drawdown": drawdown,
        "buy_count": buys,
        "sell_count": sells,
        "return_hash_12dp": _return_hash(values),
    }


def _reference_results(
    rows: tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]],
) -> tuple[dict[str, Any], dict[int, list[float]]]:
    payload: dict[str, Any] = {}
    development_primary: dict[int, list[float]] = {}
    for segment, bounds in SEGMENTS.items():
        timestamps, opens, closes = _segment_rows(rows, *bounds)
        payload[segment] = {}
        for scenario, fee, slippage in SCENARIOS:
            payload[segment][scenario] = {}
            for weekday in WEEKDAYS:
                result = simulate_calendar_ledger(
                    timestamps=timestamps,
                    opens=opens,
                    closes=closes,
                    selected_weekday=weekday,
                    fee_rate_per_side=fee,
                    slippage_bps_per_side=slippage,
                )
                values = [float(value) for value in result.returns]
                payload[segment][scenario][f"weekday={weekday}"] = _metrics(
                    values, result.ending_equity, result.buy_count, result.sell_count
                )
                if segment == "development" and scenario == "F1/S1":
                    development_primary[weekday] = values
    return payload, development_primary


def _vector_results(dataset: Path, directory: Path) -> dict[str, Any]:
    request = directory / "vector_request.json"
    output = directory / "vector_output.json"
    request.write_text(json.dumps({"segments": SEGMENTS}, sort_keys=True) + "\n")
    subprocess.run(
        [
            str(ENGINE_PYTHON),
            str(ROOT / "engines/vectorbt/calendar_utc_returns.py"),
            "--dataset",
            str(dataset),
            "--request",
            str(request),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(output.read_text())


def _parity(reference: Mapping[str, Any], vector: Mapping[str, Any]) -> dict[str, Any]:
    maximum = 0.0
    mismatches: list[str] = []
    for segment, scenarios in reference.items():
        for scenario, trials in scenarios.items():
            for trial, expected in trials.items():
                actual = vector["segments"][segment][scenario][trial]
                for key in ("total_return", "sharpe_per_bar", "max_drawdown"):
                    difference = abs(expected[key] - actual[key])
                    maximum = max(maximum, difference)
                    if difference > 1e-10:
                        mismatches.append(f"{segment}/{scenario}/{trial}/{key}")
                for key in ("buy_count", "sell_count"):
                    if expected[key] != actual[key]:
                        mismatches.append(f"{segment}/{scenario}/{trial}/{key}")
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "numeric_tolerance": 1e-10,
        "maximum_absolute_metric_difference": maximum,
        "mismatches": mismatches,
    }


def _g10(development: Mapping[int, list[float]], selected: int) -> dict[str, Any]:
    slice_count = 16
    statistics = []
    sharpes = []
    for weekday in WEEKDAYS:
        values = development[weekday]
        length = len(values) // slice_count
        used = values[: length * slice_count]
        statistics.append(
            [
                [length, sum(part), sum(value * value for value in part)]
                for index in range(slice_count)
                for part in [used[index * length : (index + 1) * length]]
            ]
        )
        sharpes.append(_metrics(values, Decimal("1000"), 0, 0)["sharpe_per_bar"])
    pbo = probability_of_backtest_overfitting_from_return_statistics(statistics)
    correlations = []
    for left, right in combinations(WEEKDAYS, 2):
        a, b = development[left], development[right]
        ma, mb = mean(a), mean(b)
        covariance = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / (len(a) - 1)
        da = math.sqrt(sum((x - ma) ** 2 for x in a) / (len(a) - 1))
        db = math.sqrt(sum((y - mb) ** 2 for y in b) / (len(b) - 1))
        correlations.append(covariance / (da * db))
    average_correlation = max(0.0, mean(correlations))
    effective = implied_independent_trials(7, average_correlation)
    selected_values = development[selected]
    selected_average = mean(selected_values)
    selected_deviation = math.sqrt(
        sum((value - selected_average) ** 2 for value in selected_values)
        / (len(selected_values) - 1)
    )
    selected_sharpe = selected_average / selected_deviation
    skewness = mean(
        ((value - selected_average) / selected_deviation) ** 3 for value in selected_values
    )
    kurtosis = mean(
        ((value - selected_average) / selected_deviation) ** 4 for value in selected_values
    )
    dsr = deflated_sharpe_ratio(
        selected_sharpe,
        sharpe_variance_from_trials(sharpes),
        effective,
        len(selected_values),
        skewness,
        kurtosis,
    )
    return {
        "pbo": pbo["pbo"],
        "pbo_split_count": pbo["split_count"],
        "raw_statistical_trials": 7,
        "qualitative_family_candidates_retained": 3,
        "average_trial_return_correlation_clipped_at_zero": average_correlation,
        "effective_trials": effective,
        "selected_sharpe_per_bar": selected_sharpe,
        **dsr,
    }


def _benchmark(
    rows: tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]],
) -> dict[str, float]:
    timestamps, opens, closes = _segment_rows(rows, *SEGMENTS["full"])
    del timestamps
    fee, slip = Decimal("0.001"), Decimal("0.0001")
    quantity = Decimal("1000") / (opens[0] * (1 + slip) * (1 + fee))
    equity = [float(quantity * close / Decimal("1000")) for close in closes]
    returns = [equity[0] - 1] + [
        equity[index] / equity[index - 1] - 1 for index in range(1, len(equity))
    ]
    return _metrics(returns, quantity * closes[-1], 1, 0)  # type: ignore[return-value]


def _clock_perturbations(
    rows: tuple[tuple[datetime, ...], tuple[Decimal, ...], tuple[Decimal, ...]],
    selected: int,
) -> dict[str, dict[str, Any]]:
    timestamps, opens, closes = _segment_rows(rows, *SEGMENTS["full"])
    result = {}
    for offset in (-1, 1):
        ledger = simulate_calendar_ledger(
            timestamps=timestamps,
            opens=opens,
            closes=closes,
            selected_weekday=selected,
            fee_rate_per_side=Decimal("0.001"),
            slippage_bps_per_side=Decimal("1"),
            hour_offset=offset,
        )
        values = [float(value) for value in ledger.returns]
        result[f"offset_{offset:+d}h"] = _metrics(
            values, ledger.ending_equity, ledger.buy_count, ledger.sell_count
        )
    return result


def _evaluate(
    reference: Mapping[str, Any],
    development: Mapping[int, list[float]],
    parity: Mapping[str, Any],
    benchmark: Mapping[str, float],
    clock_perturbations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    dev = reference["development"]["F1/S1"]
    selected = max(
        WEEKDAYS, key=lambda weekday: (dev[f"weekday={weekday}"]["sharpe_per_bar"], -weekday)
    )
    trial = f"weekday={selected}"
    validation = reference["validation_2024"]["F1/S1"][trial]
    reserved = reference["reserved_2025_2026h1"]["F1/S1"][trial]
    full = reference["full"]["F1/S1"][trial]
    stress = reference["full"]["F2/S3"][trial]
    yearly = [
        reference[key]["F1/S1"][trial]["total_return"]
        for key in SEGMENTS
        if key.startswith("year_")
    ]
    g10 = _g10(development, selected)
    gates = {
        "G1_DATA_PROVENANCE": "PASS",
        "G2_CANONICAL_IDENTITY": "PASS",
        "G3_CAUSAL_GOLDENS": "PASS",
        "G4_INDEPENDENT_REPRODUCTION": parity["status"],
        "G5_AFTER_COST_ECONOMICS": "PASS"
        if full["total_return"] > 0 and stress["total_return"] > 0
        else "FAIL",
        "G6_CHRONOLOGICAL_OOS": "PASS"
        if validation["total_return"] > 0 and reserved["total_return"] > 0
        else "FAIL",
        "G7_SAMPLE_AND_CLOCK_ROBUSTNESS": "PASS"
        if dev[trial]["sell_count"] >= 140
        and validation["sell_count"] >= 45
        and reserved["sell_count"] >= 70
        and all(item["total_return"] > 0 for item in clock_perturbations.values())
        else "FAIL",
        "G8_REGIME_AND_TAIL": "PASS"
        if sum(value > 0 for value in yearly) >= 4 and full["max_drawdown"] >= -0.25
        else "FAIL",
        "G9_BENCHMARK_AND_OPPORTUNITY": "PASS"
        if full["sharpe_per_bar"] > benchmark["sharpe_per_bar"]
        and full["max_drawdown"] > benchmark["max_drawdown"]
        else "FAIL",
        "G10_MULTIPLE_TESTING": "PASS" if g10["pbo"] <= 0.5 and g10["dsr"] >= 0.95 else "FAIL",
        "G11_INDEPENDENT_RISK_SUPERVISOR": "NOT_RUN",
    }
    return {
        "selected_weekday": selected,
        "selected_trial": trial,
        "gates": gates,
        "numeric_verdict": "PASS"
        if all(value == "PASS" for key, value in gates.items() if not key.startswith("G11"))
        else "FAIL",
        "promotion_eligible": False,
        "g10": g10,
        "development": dev[trial],
        "validation_2024": validation,
        "reserved_2025_2026h1": reserved,
        "full_primary": full,
        "full_stress": stress,
        "yearly_primary_returns": yearly,
        "buy_and_hold_primary": benchmark,
        "clock_perturbations_primary": clock_perturbations,
    }


def run() -> Path:
    context = preflight()
    campaign = context["campaign"]
    dataset = ROOT / campaign["dataset"]["path"]
    temp = Path(tempfile.mkdtemp(prefix=".calendar-utc-", dir=OUTPUT_ROOT.parent))
    try:
        rows = _load_rows(dataset)
        reference, development = _reference_results(rows)
        vector = _vector_results(dataset, temp)
        parity = _parity(reference, vector)
        selected = max(
            WEEKDAYS,
            key=lambda weekday: (
                reference["development"]["F1/S1"][f"weekday={weekday}"]["sharpe_per_bar"],
                -weekday,
            ),
        )
        evaluation = _evaluate(
            reference,
            development,
            parity,
            _benchmark(rows),
            _clock_perturbations(rows, selected),
        )
        output = temp / "final"
        output.mkdir()
        shutil.copy2(CAMPAIGN, output / f"preregistration_{context['campaign_hash']}.yaml")
        reference_path = _write_hashed_json(output, "reference_results", {"segments": reference})
        vector_path = _write_hashed_json(output, "vectorbt_results", vector)
        report = {
            "schema": "tios-calendar-utc-campaign-result-v1",
            "campaign_id": campaign["campaign_id"],
            "run_commit": context["commit"],
            "preregistration_sha256": context["campaign_hash"],
            "completed_at_utc": datetime.now(tz=UTC).isoformat(),
            "execution_authority": "NONE",
            "promotion_eligible": False,
            "sealed_v2_holdout_accessed": False,
            "parity": parity,
            "evaluation": evaluation,
            "artifacts": {
                "reference_results": reference_path.name,
                "vectorbt_results": vector_path.name,
            },
        }
        result_path = _write_hashed_json(output, "campaign_result", report)
        if OUTPUT_ROOT.exists():
            raise RuntimeError("campaign output appeared during run")
        output.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT / result_path.name
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(preflight(require_clean=False), default=str, sort_keys=True))
        return 0
    print(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
