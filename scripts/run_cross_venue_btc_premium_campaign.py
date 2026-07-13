"""Run D-075 behind a hashed development-selection barrier."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import run_funding_pressure_campaign as shared  # noqa: E402

from engines.reference.cross_venue_premium import (  # noqa: E402
    premium_events,
    simulate_premium_ledger,
)
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402

CAMPAIGN = ROOT / "research/CROSS_VENUE_BTC_PREMIUM_G1_G11_CAMPAIGN_V1.yaml"
OUTPUT_ROOT = ROOT / "artifacts/validation/campaigns/CROSS-VENUE-BTC-PREMIUM-G1-G11-V1"
SCENARIOS = shared.SCENARIOS
DEVELOPMENT = {"development": ("2021-05-04 01:00:00+00:00", "2023-12-31 23:00:00+00:00")}
POST_SELECTION = {
    "validation_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "reserve_2025_2026h1": ("2025-01-01", "2026-06-30 23:00:00+00:00"),
    "full": ("2021-05-04 01:00:00+00:00", "2026-06-30 23:00:00+00:00"),
    "period_2021_may_dec": ("2021-05-04 01:00:00+00:00", "2021-12-31 23:00:00+00:00"),
    "year_2022": ("2022-01-01", "2022-12-31 23:00:00+00:00"),
    "year_2023": ("2023-01-01", "2023-12-31 23:00:00+00:00"),
    "year_2024": ("2024-01-01", "2024-12-31 23:00:00+00:00"),
    "year_2025": ("2025-01-01", "2025-12-31 23:00:00+00:00"),
    "year_2026_h1": ("2026-01-01", "2026-06-30 23:00:00+00:00"),
}
WORKERS = {
    "vectorbt": (
        ROOT / "engines/vectorbt/.venv/bin/python",
        ROOT / "engines/vectorbt/cross_venue_premium_returns.py",
    ),
    "freqtrade": (
        ROOT / "engines/freqtrade/.venv/bin/python",
        ROOT / "engines/freqtrade/cross_venue_premium_signals.py",
    ),
    "nautilus": (
        ROOT / "engines/nautilus/.venv/bin/python",
        ROOT / "engines/nautilus/cross_venue_premium_events.py",
    ),
}


def trial_name(interpretation: str, baseline_hours: int, threshold: float) -> str:
    return (
        f"interpretation={interpretation}|baseline_hours={baseline_hours}|threshold={threshold:.1f}"
    )


def _trial_key(trial: Mapping[str, Any]) -> tuple[str, int, float]:
    return trial["interpretation"], trial["baseline_hours"], trial["threshold"]


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
        raise RuntimeError("canonical cross-venue premium spec is not valid")
    spec = parse_spec(spec_payload)
    for item in roster:
        params = {key: item[key] for key in ("interpretation", "baseline_hours", "threshold")}
        if create_version(spec, params).sv_id != item["strategy_version_id"]:
            raise RuntimeError("StrategyVersion identity drift")
    verification = json.loads(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_cross_venue_premium_data.py")],
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
    package = json.loads((ROOT / campaign["dataset"]["package_path"]).read_text())
    table = pq.read_table(ROOT / package["normalized"]["path"])
    columns = {
        name: tuple(table.column(name).to_pylist())
        for name in (
            "timestamp_open_utc",
            "source_close_utc",
            "binance_btcusdt_open",
            "binance_btcusdt_close",
            "log_premium",
        )
    }
    spot = (
        columns["timestamp_open_utc"],
        columns["binance_btcusdt_open"],
        columns["binance_btcusdt_close"],
    )
    source = (
        columns["timestamp_open_utc"],
        columns["source_close_utc"],
        columns["log_premium"],
    )
    return spot, source


def _reference_phase(
    spot: tuple[Any, ...],
    source: tuple[Any, ...],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
    *,
    delay_bars: int = 0,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    payload: dict[str, Any] = {}
    primary_returns: dict[str, list[float]] = {}
    source_opens, source_closes, premiums = source
    for segment, bounds in segments.items():
        opened, opens, closes = shared._segment_spot(spot, bounds)
        payload[segment] = {}
        event_cache = {}
        for trial in trials:
            name = trial_name(trial["interpretation"], trial["baseline_hours"], trial["threshold"])
            kwargs = {
                "spot_opens": opened,
                "source_opens": source_opens,
                "source_closes": source_closes,
                "premiums": premiums,
                "interpretation": trial["interpretation"],
                "baseline_hours": trial["baseline_hours"],
                "threshold": Decimal(str(trial["threshold"])),
                "delay_bars": delay_bars,
            }
            entries, exits = premium_events(**kwargs)
            event_cache[name] = (kwargs, entries, exits)
        for scenario, fee, slippage in SCENARIOS:
            payload[segment][scenario] = {}
            for name, (kwargs, entries, exits) in event_cache.items():
                ledger = simulate_premium_ledger(
                    **kwargs,
                    opens=opens,
                    closes=closes,
                    fee_rate_per_side=fee,
                    slippage_bps_per_side=slippage,
                    precomputed_events=(entries, exits),
                )
                returns = [float(value) for value in ledger.returns]
                payload[segment][scenario][name] = shared._metrics(
                    returns,
                    ledger.ending_equity,
                    ledger.buy_count,
                    ledger.sell_count,
                    shared._event_hash(entries, exits),
                )
                if segment == "development" and scenario == "F1/S1":
                    primary_returns[name] = returns
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
    source: tuple[Any, ...],
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    selected = barrier.require()["selected_trial"]
    return _reference_phase(spot, source, [selected], POST_SELECTION)


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
        if dev["sell_count"] >= 100
        and validation["sell_count"] >= 30
        and reserve["sell_count"] >= 20
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
    temp = Path(tempfile.mkdtemp(prefix=".cross-venue-premium-", dir=OUTPUT_ROOT.parent))
    try:
        spot, source = _load_inputs(campaign)
        phase_one, development_returns = _reference_phase(spot, source, roster, DEVELOPMENT)
        workers_one = _run_workers(temp, "phase_one", campaign, roster, DEVELOPMENT)
        parity_one = shared._parity(phase_one, workers_one)
        dev = phase_one["development"]["F1/S1"]
        selected = min(
            roster,
            key=lambda item: (
                -dev[trial_name(item["interpretation"], item["baseline_hours"], item["threshold"])][
                    "sharpe_per_bar"
                ],
                _trial_key(item),
            ),
        )
        selected_name = trial_name(
            selected["interpretation"], selected["baseline_hours"], selected["threshold"]
        )
        g10 = shared._g10(development_returns, selected_name)
        selection_path = shared._write_hashed_json(
            temp,
            "selection",
            {
                "schema": "tios-cross-venue-btc-premium-selection-v1",
                "selected_trial": selected,
                "selected_trial_name": selected_name,
                "selection_source": "development/F1-S1/sharpe_per_bar",
                "development_metric": dev[selected_name]["sharpe_per_bar"],
                "g10": g10,
            },
        )
        barrier = shared.SelectionBarrier(selection_path, shared.sha256(selection_path))
        phase_two, _ = _post_selection_reference(barrier, spot, source)
        workers_two = _run_workers(temp, "phase_two", campaign, [selected], POST_SELECTION, barrier)
        parity_two = shared._parity(phase_two, workers_two)
        parity = {
            "status": "PASS" if parity_one["status"] == parity_two["status"] == "PASS" else "FAIL",
            "phase_one": parity_one,
            "phase_two": parity_two,
        }
        delayed_payload, _ = _reference_phase(
            spot, source, [selected], {"full": POST_SELECTION["full"]}, delay_bars=1
        )
        evaluation = _evaluate(
            phase_one,
            phase_two,
            selected_name,
            parity,
            g10,
            delayed_payload["full"]["F1/S1"][selected_name],
            shared._benchmark(spot),
        )
        output = temp / "final"
        output.mkdir()
        shutil.copy2(CAMPAIGN, output / f"preregistration_{context['campaign_hash']}.yaml")
        shutil.copy2(selection_path, output / selection_path.name)
        artifacts = {
            "phase_one_reference": shared._write_hashed_json(
                output, "phase_one_reference", phase_one
            ).name,
            "phase_two_reference": shared._write_hashed_json(
                output, "phase_two_reference", phase_two
            ).name,
            "phase_one_workers": shared._write_hashed_json(
                output, "phase_one_workers", workers_one
            ).name,
            "phase_two_workers": shared._write_hashed_json(
                output, "phase_two_workers", workers_two
            ).name,
        }
        report = {
            "schema": "tios-cross-venue-btc-premium-campaign-result-v1",
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
            "artifacts": artifacts,
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
