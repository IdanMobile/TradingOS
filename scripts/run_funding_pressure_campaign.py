"""Run the frozen funding-pressure campaign with a hard select-before-reserve barrier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
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

from engines.reference.funding_pressure import (  # noqa: E402
    funding_events,
    simulate_funding_ledger,
)
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    implied_independent_trials,
    probability_of_backtest_overfitting_from_return_statistics,
    sharpe_variance_from_trials,
)

CAMPAIGN = ROOT / "research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V1.yaml"
OUTPUT_ROOT = ROOT / "artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V1"
SCENARIOS = (
    ("F0/S0", Decimal("0"), Decimal("0")),
    ("F1/S1", Decimal("0.001"), Decimal("1")),
    ("F1/S2", Decimal("0.001"), Decimal("5")),
    ("F1/S3", Decimal("0.001"), Decimal("10")),
    ("F2/S2", Decimal("0.0015"), Decimal("5")),
    ("F2/S3", Decimal("0.0015"), Decimal("10")),
)
DEVELOPMENT = {"development": ("2021-01-01", "2023-12-31 23:00:00+00:00")}
POST_SELECTION = {
    "validation_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "reserve_2025_2026h1": ("2025-01-01", "2026-06-30 23:00:00+00:00"),
    "full": ("2021-01-01", "2026-06-30 23:00:00+00:00"),
    "year_2021": ("2021-01-01", "2021-12-31 23:00:00+00:00"),
    "year_2022": ("2022-01-01", "2022-12-31 23:00:00+00:00"),
    "year_2023": ("2023-01-01", "2023-12-31 23:00:00+00:00"),
    "year_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "year_2025": ("2025-01-01", "2025-12-31 23:00:00+00:00"),
    "year_2026_h1": ("2026-01-01", "2026-06-30 23:00:00+00:00"),
}
WORKERS = {
    "vectorbt": (
        ROOT / "engines/vectorbt/.venv/bin/python",
        ROOT / "engines/vectorbt/funding_pressure_returns.py",
    ),
    "freqtrade": (
        ROOT / "engines/freqtrade/.venv/bin/python",
        ROOT / "engines/freqtrade/funding_pressure_signals.py",
    ),
    "nautilus": (
        ROOT / "engines/nautilus/.venv/bin/python",
        ROOT / "engines/nautilus/funding_pressure_events.py",
    ),
}


def trial_name(polarity: str, lookback: int, threshold: float) -> str:
    return f"polarity={polarity}|lookback={lookback}|threshold={threshold:.4f}"


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


def _trial_key(trial: Mapping[str, Any]) -> tuple[str, int, float]:
    return trial["polarity"], trial["lookback"], float(trial["threshold"])


def preflight(*, require_clean: bool = True) -> dict[str, Any]:
    campaign = yaml.safe_load(CAMPAIGN.read_text(encoding="utf-8"))
    if campaign["status"] != "PREREGISTERED_NOT_RUN":
        raise RuntimeError("campaign is not preregistered and unrun")
    expected_safety = {
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "orders": "DISABLED",
        "network": "PROHIBITED",
        "credentials_required": False,
        "sealed_v2_holdout_access": "PROHIBITED",
        "rejected_calendar_reserve_access": "PROHIBITED",
    }
    if campaign["safety"] != expected_safety:
        raise RuntimeError("campaign safety boundary changed")
    mismatches = [
        item["path"]
        for item in campaign["pinned_files"]
        if not (ROOT / item["path"]).is_file() or sha256(ROOT / item["path"]) != item["sha256"]
    ]
    if mismatches:
        raise RuntimeError(f"pinned file mismatch: {', '.join(mismatches)}")
    roster = campaign["trial_roster"]
    if len(roster) != 12 or len({_trial_key(item) for item in roster}) != 12:
        raise RuntimeError("trial roster must contain exactly 12 unique trials")
    spec_payload = yaml.safe_load((ROOT / campaign["canonical_spec"]["path"]).read_text())
    if validate(spec_payload).verdict != "VALID":
        raise RuntimeError("canonical funding-pressure spec is not valid")
    spec = parse_spec(spec_payload)
    for item in roster:
        params = {
            "polarity": item["polarity"],
            "lookback": item["lookback"],
            "threshold": float(item["threshold"]),
        }
        if create_version(spec, params).sv_id != item["strategy_version_id"]:
            raise RuntimeError("StrategyVersion identity drift")
    verification = json.loads(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_funding_pressure_data.py")],
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


def _load_inputs(campaign: Mapping[str, Any]) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    table = pq.read_table(
        ROOT / campaign["dataset"]["spot_path"],
        columns=["timestamp_open_utc", "open", "close"],
    )
    spot = tuple(tuple(table.column(name).to_pylist()) for name in table.column_names)
    calc_times: list[datetime] = []
    rates: list[Decimal] = []
    funding_root = ROOT / campaign["dataset"]["funding_root"]
    for path in sorted(funding_root.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            reader = csv.DictReader(
                io.TextIOWrapper(archive.open(archive.namelist()[0]), encoding="utf-8")
            )
            for row in reader:
                calc_times.append(datetime.fromtimestamp(int(row["calc_time"]) / 1000, UTC))
                rates.append(Decimal(row["last_funding_rate"]))
    return spot, (tuple(calc_times), tuple(rates))


def _bounds(value: str) -> datetime:
    return (
        datetime.fromisoformat(value).replace(tzinfo=UTC)
        if "+" not in value
        else datetime.fromisoformat(value)
    )


def _segment_spot(spot: tuple[Any, ...], bounds: tuple[str, str]) -> tuple[Any, ...]:
    lower, upper = map(_bounds, bounds)
    selected = [index for index, value in enumerate(spot[0]) if lower <= value <= upper]
    if not selected:
        raise RuntimeError("empty campaign segment")
    return tuple(tuple(column[index] for index in selected) for column in spot)


def _return_hash(values: list[float]) -> str:
    return hashlib.sha256(
        b"".join(struct.pack("<d", round(value, 12)) for value in values)
    ).hexdigest()


def _event_hash(entries: tuple[bool, ...], exits: tuple[bool, ...]) -> str:
    return hashlib.sha256(
        bytes(int(entry) + 2 * int(exit_) for entry, exit_ in zip(entries, exits, strict=True))
    ).hexdigest()


def _metrics(
    values: list[float], ending_equity: Decimal, buys: int, sells: int, event_hash: str
) -> dict[str, Any]:
    average = mean(values)
    deviation = math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))
    equity = peak = 1.0
    drawdown = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    return {
        "total_return": float(ending_equity / Decimal("1000") - 1),
        "sharpe_per_bar": average / deviation if deviation else 0.0,
        "max_drawdown": drawdown,
        "buy_count": buys,
        "sell_count": sells,
        "event_hash": event_hash,
        "return_hash_12dp": _return_hash(values),
    }


def _reference_phase(
    spot: tuple[Any, ...],
    funding: tuple[Any, ...],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
    *,
    delay_bars: int = 0,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    payload: dict[str, Any] = {}
    primary_returns: dict[str, list[float]] = {}
    calc_times, rates = funding
    for segment, bounds in segments.items():
        opened, opens, closes = _segment_spot(spot, bounds)
        payload[segment] = {}
        for scenario, fee, slippage in SCENARIOS:
            payload[segment][scenario] = {}
            for trial in trials:
                name = trial_name(trial["polarity"], trial["lookback"], trial["threshold"])
                kwargs = {
                    "spot_opens": opened,
                    "calc_times": calc_times,
                    "rates": rates,
                    "polarity": trial["polarity"],
                    "lookback": trial["lookback"],
                    "threshold": Decimal(str(trial["threshold"])),
                    "signal_start": opened[0],
                    "delay_bars": delay_bars,
                }
                entries, exits = funding_events(**kwargs)
                ledger = simulate_funding_ledger(
                    **kwargs,
                    opens=opens,
                    closes=closes,
                    fee_rate_per_side=fee,
                    slippage_bps_per_side=slippage,
                )
                values = [float(value) for value in ledger.returns]
                payload[segment][scenario][name] = _metrics(
                    values,
                    ledger.ending_equity,
                    ledger.buy_count,
                    ledger.sell_count,
                    _event_hash(entries, exits),
                )
                if segment == "development" and scenario == "F1/S1":
                    primary_returns[name] = values
    return payload, primary_returns


@dataclass(frozen=True)
class SelectionBarrier:
    path: Path | None = None
    digest: str | None = None

    def require(self) -> dict[str, Any]:
        if self.path is None or self.digest is None or not self.path.is_file():
            raise RuntimeError("selection artifact required before validation/reserve evaluation")
        if sha256(self.path) != self.digest:
            raise RuntimeError("selection artifact hash mismatch")
        return json.loads(self.path.read_text(encoding="utf-8"))


def _post_selection_reference(
    barrier: SelectionBarrier,
    spot: tuple[Any, ...],
    funding: tuple[Any, ...],
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    selected = barrier.require()["selected_trial"]
    return _reference_phase(spot, funding, [selected], POST_SELECTION)


def _worker_request(
    directory: Path,
    stem: str,
    campaign: Mapping[str, Any],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
) -> Path:
    request = directory / f"{stem}_request.json"
    request.write_text(
        json.dumps(
            {
                "spot_path": campaign["dataset"]["spot_path"],
                "funding_root": campaign["dataset"]["funding_root"],
                "trials": trials,
                "segments": segments,
                "scenarios": [
                    {"name": name, "fee": float(fee), "slippage_bps": float(slip)}
                    for name, fee, slip in SCENARIOS
                ],
            },
            sort_keys=True,
        )
        + "\n"
    )
    return request


def _run_workers(
    directory: Path,
    stem: str,
    campaign: Mapping[str, Any],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
    barrier: SelectionBarrier | None = None,
) -> dict[str, Any]:
    if barrier is not None:
        barrier.require()
    request = _worker_request(directory, stem, campaign, trials, segments)
    results = {}
    for name, (python, script) in WORKERS.items():
        output = directory / f"{stem}_{name}.json"
        subprocess.run(
            [str(python), str(script), "--request", str(request), "--output", str(output)],
            cwd=ROOT,
            check=True,
        )
        results[name] = json.loads(output.read_text(encoding="utf-8"))
    return results


def _parity(reference: Mapping[str, Any], workers: Mapping[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    maximum = 0.0
    vector = workers["vectorbt"]["segments"]
    for segment, scenarios in reference.items():
        for scenario, trials in scenarios.items():
            for trial, expected in trials.items():
                actual = vector[segment][scenario][trial]
                for key in ("total_return", "sharpe_per_bar", "max_drawdown"):
                    difference = abs(expected[key] - actual[key])
                    maximum = max(maximum, difference)
                    if difference > 1e-10:
                        mismatches.append(f"vectorbt/{segment}/{scenario}/{trial}/{key}")
                for engine in ("vectorbt", "freqtrade", "nautilus"):
                    row = (
                        workers[engine]["segments"][segment][scenario][trial]
                        if engine == "vectorbt"
                        else workers[engine]["segments"][segment][trial]
                    )
                    for key in ("event_hash", "buy_count", "sell_count"):
                        if row[key] != expected[key]:
                            mismatches.append(f"{engine}/{segment}/{trial}/{key}")
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "numeric_tolerance": 1e-10,
        "maximum_absolute_metric_difference": maximum,
        "mismatches": mismatches,
        "versions": {name: value["version"] for name, value in workers.items()},
    }


def _g10(development: Mapping[str, list[float]], selected: str) -> dict[str, Any]:
    names = sorted(development)
    slice_count = 16
    statistics = []
    sharpes = []
    deviations = {}
    for name in names:
        values = development[name]
        length = len(values) // slice_count
        used = values[: length * slice_count]
        statistics.append(
            [
                [length, sum(part), sum(value * value for value in part)]
                for index in range(slice_count)
                for part in [used[index * length : (index + 1) * length]]
            ]
        )
        average = mean(values)
        deviation = math.sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))
        deviations[name] = deviation
        sharpes.append(average / deviation if deviation else 0.0)
    pbo = probability_of_backtest_overfitting_from_return_statistics(statistics)
    if any(not deviations[name] for name in names):
        return {"status": "METHOD_BLOCKED", "pbo": pbo["pbo"], "dsr": 0.0}
    correlations = []
    for left, right in combinations(names, 2):
        a, b = development[left], development[right]
        ma, mb = mean(a), mean(b)
        covariance = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / (len(a) - 1)
        correlations.append(covariance / (deviations[left] * deviations[right]))
    average_correlation = max(0.0, mean(correlations))
    effective = implied_independent_trials(len(names), average_correlation)
    values = development[selected]
    average = mean(values)
    deviation = deviations[selected]
    sharpe = average / deviation
    skewness = mean(((value - average) / deviation) ** 3 for value in values)
    kurtosis = mean(((value - average) / deviation) ** 4 for value in values)
    dsr = deflated_sharpe_ratio(
        sharpe,
        sharpe_variance_from_trials(sharpes),
        effective,
        len(values),
        skewness,
        kurtosis,
    )
    return {
        "status": "PASS" if pbo["pbo"] <= 0.5 and dsr["dsr"] >= 0.95 else "FAIL",
        "pbo": pbo["pbo"],
        "pbo_split_count": pbo["split_count"],
        "dsr": dsr["dsr"],
        "raw_statistical_trials": len(names),
        "average_trial_return_correlation_clipped_at_zero": average_correlation,
        "effective_trials": effective,
    }


def _benchmark(spot: tuple[Any, ...]) -> dict[str, Any]:
    _, opens, closes = _segment_spot(spot, POST_SELECTION["full"])
    fee, slip = Decimal("0.001"), Decimal("0.0001")
    quantity = Decimal("1000") / (opens[0] * (1 + slip) * (1 + fee))
    equity = [float(quantity * close / Decimal("1000")) for close in closes]
    returns = [equity[0] - 1] + [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    return _metrics(returns, quantity * closes[-1], 1, 0, "BUY_AND_HOLD")


def _evaluate(
    phase_one: Mapping[str, Any],
    phase_two: Mapping[str, Any],
    selected_name: str,
    parity: Mapping[str, Any],
    g10: Mapping[str, Any],
    delayed: Mapping[str, Any],
    benchmark: Mapping[str, Any],
) -> dict[str, Any]:
    dev = phase_one["development"]["F1/S1"][selected_name]
    validation = phase_two["validation_2024"]["F1/S1"][selected_name]
    reserve = phase_two["reserve_2025_2026h1"]["F1/S1"][selected_name]
    full = phase_two["full"]["F1/S1"][selected_name]
    stress = phase_two["full"]["F2/S3"][selected_name]
    periods = [
        phase_two[key]["F1/S1"][selected_name]["total_return"]
        for key in POST_SELECTION
        if key.startswith("year_")
    ]
    gates = {
        "G1_DATA_PROVENANCE": "PASS",
        "G2_CANONICAL_IDENTITY": "PASS",
        "G3_CAUSAL_GOLDENS": "PASS",
        "G4_INDEPENDENT_REPRODUCTION": parity["status"],
        "G5_AFTER_COST_ECONOMICS": "PASS"
        if min(
            full["total_return"],
            validation["total_return"],
            reserve["total_return"],
            stress["total_return"],
        )
        > 0
        else "FAIL",
        "G6_CHRONOLOGICAL_OOS": "PASS"
        if validation["total_return"] > 0 and reserve["total_return"] > 0
        else "FAIL",
        "G7_SAMPLE_AND_CLOCK_ROBUSTNESS": "PASS"
        if dev["sell_count"] >= 30
        and validation["sell_count"] >= 8
        and reserve["sell_count"] >= 12
        and delayed["total_return"] > 0
        else "FAIL",
        "G8_REGIME_AND_TAIL": "PASS"
        if sum(value > 0 for value in periods) >= 4 and full["max_drawdown"] >= -0.25
        else "FAIL",
        "G9_BENCHMARK_AND_OPPORTUNITY": "PASS"
        if full["sharpe_per_bar"] > benchmark["sharpe_per_bar"]
        and full["max_drawdown"] > benchmark["max_drawdown"]
        else "FAIL",
        "G10_MULTIPLE_TESTING": g10["status"],
        "G11_INDEPENDENT_RISK_SUPERVISOR": "NOT_RUN",
    }
    return {
        "selected_trial": selected_name,
        "gates": gates,
        "numeric_verdict": "PASS"
        if all(value == "PASS" for key, value in gates.items() if not key.startswith("G11"))
        else "FAIL",
        "promotion_eligible": False,
        "development": dev,
        "validation_2024": validation,
        "reserve_2025_2026h1": reserve,
        "full_primary": full,
        "full_stress": stress,
        "period_primary_returns": periods,
        "one_bar_delayed_primary": delayed,
        "buy_and_hold_primary": benchmark,
        "g10": g10,
    }


def run() -> Path:
    context = preflight()
    campaign = context["campaign"]
    roster = campaign["trial_roster"]
    temp = Path(tempfile.mkdtemp(prefix=".funding-pressure-", dir=OUTPUT_ROOT.parent))
    try:
        spot, funding = _load_inputs(campaign)
        phase_one, development_returns = _reference_phase(spot, funding, roster, DEVELOPMENT)
        workers_one = _run_workers(temp, "phase_one", campaign, roster, DEVELOPMENT)
        parity_one = _parity(phase_one, workers_one)
        dev = phase_one["development"]["F1/S1"]
        selected = min(
            roster,
            key=lambda item: (
                -dev[trial_name(item["polarity"], item["lookback"], item["threshold"])][
                    "sharpe_per_bar"
                ],
                _trial_key(item),
            ),
        )
        selected_name = trial_name(
            selected["polarity"], selected["lookback"], selected["threshold"]
        )
        g10 = _g10(development_returns, selected_name)
        selection_path = _write_hashed_json(
            temp,
            "selection",
            {
                "schema": "tios-funding-pressure-selection-v1",
                "selected_trial": selected,
                "selected_trial_name": selected_name,
                "selection_source": "development/F1-S1/sharpe_per_bar",
                "development_metric": dev[selected_name]["sharpe_per_bar"],
                "g10": g10,
            },
        )
        barrier = SelectionBarrier(selection_path, sha256(selection_path))
        phase_two, _ = _post_selection_reference(barrier, spot, funding)
        workers_two = _run_workers(temp, "phase_two", campaign, [selected], POST_SELECTION, barrier)
        parity_two = _parity(phase_two, workers_two)
        parity = {
            "status": "PASS" if parity_one["status"] == parity_two["status"] == "PASS" else "FAIL",
            "phase_one": parity_one,
            "phase_two": parity_two,
        }
        delayed_payload, _ = _reference_phase(
            spot, funding, [selected], {"full": POST_SELECTION["full"]}, delay_bars=1
        )
        delayed = delayed_payload["full"]["F1/S1"][selected_name]
        evaluation = _evaluate(
            phase_one,
            phase_two,
            selected_name,
            parity,
            g10,
            delayed,
            _benchmark(spot),
        )
        output = temp / "final"
        output.mkdir()
        shutil.copy2(CAMPAIGN, output / f"preregistration_{context['campaign_hash']}.yaml")
        shutil.copy2(selection_path, output / selection_path.name)
        phase_one_path = _write_hashed_json(output, "phase_one_reference", phase_one)
        phase_two_path = _write_hashed_json(output, "phase_two_reference", phase_two)
        workers_one_path = _write_hashed_json(output, "phase_one_workers", workers_one)
        workers_two_path = _write_hashed_json(output, "phase_two_workers", workers_two)
        report = {
            "schema": "tios-funding-pressure-campaign-result-v1",
            "campaign_id": campaign["campaign_id"],
            "run_commit": context["commit"],
            "preregistration_sha256": context["campaign_hash"],
            "completed_at_utc": datetime.now(tz=UTC).isoformat(),
            "execution_authority": "NONE",
            "promotion_eligible": False,
            "sealed_v2_holdout_accessed": False,
            "rejected_calendar_reserve_accessed": False,
            "selection_barrier": {
                "status": "PASS",
                "selection_artifact": selection_path.name,
                "selection_sha256": barrier.digest,
                "reserve_evaluated_only_after_selection": True,
            },
            "parity": parity,
            "evaluation": evaluation,
            "artifacts": {
                "phase_one_reference": phase_one_path.name,
                "phase_two_reference": phase_two_path.name,
                "phase_one_workers": workers_one_path.name,
                "phase_two_workers": workers_two_path.name,
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
