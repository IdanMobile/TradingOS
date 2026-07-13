"""Run the frozen CFTC-positioning campaign behind a select-before-reserve barrier."""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import run_funding_pressure_campaign as shared  # noqa: E402

from engines.reference.cftc_positioning import (  # noqa: E402
    positioning_events,
    simulate_positioning_ledger,
)
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402

CAMPAIGN = ROOT / "research/CFTC_BTC_POSITIONING_SPOT_G1_G11_CAMPAIGN_V1.yaml"
OUTPUT_ROOT = ROOT / "artifacts/validation/campaigns/CFTC-BTC-POSITIONING-SPOT-G1-G11-V1"
SCENARIOS = shared.SCENARIOS
DEVELOPMENT = {"development": ("2018-04-01", "2022-12-31 23:00:00+00:00")}
POST_SELECTION = {
    "validation_2023_2024": ("2023-01-01", "2024-12-31 23:00:00+00:00"),
    "reserve_2025_2026h1": ("2025-01-01", "2026-06-30 23:00:00+00:00"),
    "full": ("2018-04-01", "2026-06-30 23:00:00+00:00"),
    "period_2018_2020": ("2018-04-01", "2020-12-31 23:00:00+00:00"),
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
        ROOT / "engines/vectorbt/cftc_positioning_returns.py",
    ),
    "freqtrade": (
        ROOT / "engines/freqtrade/.venv/bin/python",
        ROOT / "engines/freqtrade/cftc_positioning_signals.py",
    ),
    "nautilus": (
        ROOT / "engines/nautilus/.venv/bin/python",
        ROOT / "engines/nautilus/cftc_positioning_events.py",
    ),
}


def trial_name(interpretation: str, baseline_weeks: int, threshold: float) -> str:
    return (
        f"interpretation={interpretation}|baseline_weeks={baseline_weeks}|threshold={threshold:.1f}"
    )


def _trial_key(trial: Mapping[str, Any]) -> tuple[str, int, float]:
    return trial["interpretation"], trial["baseline_weeks"], trial["threshold"]


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
        "closed_family_context_access": "PROHIBITED",
    }
    if campaign["safety"] != expected_safety:
        raise RuntimeError("campaign safety boundary changed")
    mismatches = [
        item["path"]
        for item in campaign["pinned_files"]
        if not (ROOT / item["path"]).is_file()
        or shared.sha256(ROOT / item["path"]) != item["sha256"]
    ]
    if mismatches:
        raise RuntimeError(f"pinned file mismatch: {', '.join(mismatches)}")
    roster = campaign["trial_roster"]
    if len(roster) != 12 or len({_trial_key(item) for item in roster}) != 12:
        raise RuntimeError("trial roster must contain exactly 12 unique trials")
    spec_payload = yaml.safe_load((ROOT / campaign["canonical_spec"]["path"]).read_text())
    if validate(spec_payload).verdict != "VALID":
        raise RuntimeError("canonical CFTC-positioning spec is not valid")
    spec = parse_spec(spec_payload)
    for item in roster:
        params = {key: item[key] for key in ("interpretation", "baseline_weeks", "threshold")}
        if create_version(spec, params).sv_id != item["strategy_version_id"]:
            raise RuntimeError("StrategyVersion identity drift")
    verification = json.loads(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_cftc_btc_positioning_data.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    if verification["status"] != "PASS" or verification["network_allowed"] is not False:
        raise RuntimeError("offline data verification failed")
    commit, dirty = shared._git_state()
    if require_clean and dirty:
        raise RuntimeError("campaign must start from a clean Git commit")
    if OUTPUT_ROOT.exists():
        raise RuntimeError("campaign output already exists")
    return {
        "campaign": campaign,
        "campaign_hash": shared.sha256(CAMPAIGN),
        "commit": commit,
        "dirty": dirty,
        "data_verification": verification,
    }


def _load_inputs(campaign: Mapping[str, Any]) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    package_path = campaign["dataset"]["package_path"]
    package = json.loads((ROOT / package_path).read_text())
    early: list[tuple[datetime, Decimal, Decimal]] = []
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    for archive in package["spot_execution"]["early_archives"]:
        encoded = (ROOT / archive["base64_path"]).read_bytes()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as zipped:
            rows = csv.reader(io.TextIOWrapper(zipped.open(zipped.namelist()[0])))
            early.extend(
                (epoch + timedelta(milliseconds=int(row[0])), Decimal(row[1]), Decimal(row[4]))
                for row in rows
            )
    table = pq.read_table(
        ROOT / package["spot_execution"]["existing_normalized_path"],
        columns=["timestamp_open_utc", "open", "close"],
    )
    existing = zip(
        table.column("timestamp_open_utc").to_pylist(),
        table.column("open").to_pylist(),
        table.column("close").to_pylist(),
        strict=True,
    )
    combined = sorted([*early, *existing], key=lambda row: row[0])
    spot = tuple(tuple(row[index] for row in combined) for index in range(3))

    feature = package["cftc_feature"]
    source = feature["sources"][0]
    cftc_rows = list(
        csv.DictReader(
            io.StringIO(base64.b64decode((ROOT / source["base64_path"]).read_bytes()).decode())
        )
    )
    exceptions = json.loads((ROOT / feature["publication_exceptions_path"]).read_text())[
        "exceptions"
    ]
    report_dates: list[datetime] = []
    available_at: list[datetime] = []
    values: list[Decimal] = []
    for row in cftc_rows:
        report = datetime.fromisoformat(row["report_date_as_yyyy_mm_dd"]).replace(tzinfo=UTC)
        available = report + timedelta(days=8)
        if published := exceptions.get(report.date().isoformat()):
            available = max(
                available,
                datetime.fromisoformat(published).replace(tzinfo=UTC) + timedelta(days=1),
            )
        report_dates.append(report)
        available_at.append(available)
        values.append(
            (
                Decimal(row["noncomm_positions_long_all"])
                - Decimal(row["noncomm_positions_short_all"])
            )
            / Decimal(row["open_interest_all"])
        )
    positioning = (tuple(report_dates), tuple(available_at), tuple(values))
    return spot, positioning


def _reference_phase(
    spot: tuple[Any, ...],
    positioning: tuple[Any, ...],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
    *,
    delay_bars: int = 0,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    payload: dict[str, Any] = {}
    primary_returns: dict[str, list[float]] = {}
    report_dates, available_at, feature_values = positioning
    for segment, bounds in segments.items():
        opened, opens, closes = shared._segment_spot(spot, bounds)
        payload[segment] = {}
        for scenario, fee, slippage in SCENARIOS:
            payload[segment][scenario] = {}
            for trial in trials:
                name = trial_name(
                    trial["interpretation"], trial["baseline_weeks"], trial["threshold"]
                )
                kwargs = {
                    "spot_opens": opened,
                    "report_dates": report_dates,
                    "available_at": available_at,
                    "values": feature_values,
                    "interpretation": trial["interpretation"],
                    "baseline_weeks": trial["baseline_weeks"],
                    "threshold": Decimal(str(trial["threshold"])),
                    "delay_bars": delay_bars,
                }
                entries, exits = positioning_events(**kwargs)
                ledger = simulate_positioning_ledger(
                    **kwargs,
                    opens=opens,
                    closes=closes,
                    fee_rate_per_side=fee,
                    slippage_bps_per_side=slippage,
                )
                return_values = [float(value) for value in ledger.returns]
                payload[segment][scenario][name] = shared._metrics(
                    return_values,
                    ledger.ending_equity,
                    ledger.buy_count,
                    ledger.sell_count,
                    shared._event_hash(entries, exits),
                )
                if segment == "development" and scenario == "F1/S1":
                    primary_returns[name] = return_values
    return payload, primary_returns


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
                "package_path": campaign["dataset"]["package_path"],
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
    barrier: shared.SelectionBarrier | None = None,
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


def _post_selection_reference(
    barrier: shared.SelectionBarrier,
    spot: tuple[Any, ...],
    positioning: tuple[Any, ...],
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    selected = barrier.require()["selected_trial"]
    return _reference_phase(spot, positioning, [selected], POST_SELECTION)


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
    validation = phase_two["validation_2023_2024"]["F1/S1"][selected_name]
    reserve = phase_two["reserve_2025_2026h1"]["F1/S1"][selected_name]
    full = phase_two["full"]["F1/S1"][selected_name]
    stress = phase_two["full"]["F2/S3"][selected_name]
    periods = [
        phase_two[key]["F1/S1"][selected_name]["total_return"]
        for key in POST_SELECTION
        if key.startswith("year_") or key.startswith("period_")
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
        if sum(value > 0 for value in periods) >= 5 and full["max_drawdown"] >= -0.25
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
        "validation_2023_2024": validation,
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
    temp = Path(tempfile.mkdtemp(prefix=".cftc-positioning-", dir=OUTPUT_ROOT.parent))
    try:
        spot, positioning = _load_inputs(campaign)
        phase_one, development_returns = _reference_phase(spot, positioning, roster, DEVELOPMENT)
        workers_one = _run_workers(temp, "phase_one", campaign, roster, DEVELOPMENT)
        parity_one = shared._parity(phase_one, workers_one)
        dev = phase_one["development"]["F1/S1"]
        selected = min(
            roster,
            key=lambda item: (
                -dev[trial_name(item["interpretation"], item["baseline_weeks"], item["threshold"])][
                    "sharpe_per_bar"
                ],
                _trial_key(item),
            ),
        )
        selected_name = trial_name(
            selected["interpretation"], selected["baseline_weeks"], selected["threshold"]
        )
        g10 = shared._g10(development_returns, selected_name)
        selection_path = shared._write_hashed_json(
            temp,
            "selection",
            {
                "schema": "tios-cftc-positioning-selection-v1",
                "selected_trial": selected,
                "selected_trial_name": selected_name,
                "selection_source": "development/F1-S1/sharpe_per_bar",
                "development_metric": dev[selected_name]["sharpe_per_bar"],
                "g10": g10,
            },
        )
        barrier = shared.SelectionBarrier(selection_path, shared.sha256(selection_path))
        phase_two, _ = _post_selection_reference(barrier, spot, positioning)
        workers_two = _run_workers(temp, "phase_two", campaign, [selected], POST_SELECTION, barrier)
        parity_two = shared._parity(phase_two, workers_two)
        parity = {
            "status": "PASS" if parity_one["status"] == parity_two["status"] == "PASS" else "FAIL",
            "phase_one": parity_one,
            "phase_two": parity_two,
        }
        delayed_payload, _ = _reference_phase(
            spot, positioning, [selected], {"full": POST_SELECTION["full"]}, delay_bars=1
        )
        delayed = delayed_payload["full"]["F1/S1"][selected_name]
        evaluation = _evaluate(
            phase_one,
            phase_two,
            selected_name,
            parity,
            g10,
            delayed,
            shared._benchmark(spot),
        )
        output = temp / "final"
        output.mkdir()
        shutil.copy2(CAMPAIGN, output / f"preregistration_{context['campaign_hash']}.yaml")
        shutil.copy2(selection_path, output / selection_path.name)
        phase_one_path = shared._write_hashed_json(output, "phase_one_reference", phase_one)
        phase_two_path = shared._write_hashed_json(output, "phase_two_reference", phase_two)
        workers_one_path = shared._write_hashed_json(output, "phase_one_workers", workers_one)
        workers_two_path = shared._write_hashed_json(output, "phase_two_workers", workers_two)
        report = {
            "schema": "tios-cftc-positioning-campaign-result-v1",
            "campaign_id": campaign["campaign_id"],
            "run_commit": context["commit"],
            "preregistration_sha256": context["campaign_hash"],
            "completed_at_utc": datetime.now(tz=UTC).isoformat(),
            "execution_authority": "NONE",
            "promotion_eligible": False,
            "sealed_v2_holdout_accessed": False,
            "closed_family_context_accessed": False,
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
        result_path = shared._write_hashed_json(output, "campaign_result", report)
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
