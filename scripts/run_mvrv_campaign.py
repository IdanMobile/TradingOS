"""Run the frozen MVRV-dislocation campaign behind a select-before-reserve barrier."""

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

from engines.reference.mvrv_dislocation import (  # noqa: E402
    mvrv_events,
    simulate_mvrv_ledger,
)
from tios.strategy.spec import parse_spec  # noqa: E402
from tios.strategy.validator import validate  # noqa: E402
from tios.strategy.version import create_version  # noqa: E402

CAMPAIGN = ROOT / "research/BTC_MVRV_SPOT_G1_G11_CAMPAIGN_V1.yaml"
OUTPUT_ROOT = ROOT / "artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1"
SCENARIOS = shared.SCENARIOS
DEVELOPMENT = shared.DEVELOPMENT
POST_SELECTION = shared.POST_SELECTION
WORKERS = {
    "vectorbt": (
        ROOT / "engines/vectorbt/.venv/bin/python",
        ROOT / "engines/vectorbt/mvrv_dislocation_returns.py",
    ),
    "freqtrade": (
        ROOT / "engines/freqtrade/.venv/bin/python",
        ROOT / "engines/freqtrade/mvrv_dislocation_signals.py",
    ),
    "nautilus": (
        ROOT / "engines/nautilus/.venv/bin/python",
        ROOT / "engines/nautilus/mvrv_dislocation_events.py",
    ),
}


def trial_name(side: str, window: int, holding_days: int) -> str:
    return f"side={side}|window={window}|holding_days={holding_days}"


def _trial_key(trial: Mapping[str, Any]) -> tuple[str, int, int]:
    return trial["side"], trial["window"], trial["holding_days"]


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
        raise RuntimeError("canonical MVRV-dislocation spec is not valid")
    spec = parse_spec(spec_payload)
    for item in roster:
        params = {key: item[key] for key in ("side", "window", "holding_days")}
        if create_version(spec, params).sv_id != item["strategy_version_id"]:
            raise RuntimeError("StrategyVersion identity drift")
    verification = json.loads(
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_btc_mvrv_data.py")],
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
    table = pq.read_table(
        ROOT / campaign["dataset"]["spot_path"],
        columns=["timestamp_open_utc", "open", "close"],
    )
    spot = tuple(tuple(table.column(name).to_pylist()) for name in table.column_names)
    payload = json.loads((ROOT / campaign["dataset"]["mvrv_path"]).read_text())
    source_days = tuple(
        datetime.fromisoformat(item["time"].replace("Z", "+00:00")) for item in payload["data"]
    )
    values = tuple(Decimal(item["CapMVRVCur"]) for item in payload["data"])
    return spot, (source_days, values)


def _reference_phase(
    spot: tuple[Any, ...],
    mvrv: tuple[Any, ...],
    trials: list[dict[str, Any]],
    segments: Mapping[str, tuple[str, str]],
    *,
    delay_bars: int = 0,
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    payload: dict[str, Any] = {}
    primary_returns: dict[str, list[float]] = {}
    source_days, feature_values = mvrv
    for segment, bounds in segments.items():
        opened, opens, closes = shared._segment_spot(spot, bounds)
        payload[segment] = {}
        for scenario, fee, slippage in SCENARIOS:
            payload[segment][scenario] = {}
            for trial in trials:
                name = trial_name(trial["side"], trial["window"], trial["holding_days"])
                kwargs = {
                    "spot_opens": opened,
                    "source_days": source_days,
                    "values": feature_values,
                    "side": trial["side"],
                    "window": trial["window"],
                    "holding_days": trial["holding_days"],
                    "signal_start": opened[0],
                    "delay_bars": delay_bars,
                }
                entries, exits = mvrv_events(**kwargs)
                ledger = simulate_mvrv_ledger(
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
                "spot_path": campaign["dataset"]["spot_path"],
                "mvrv_path": campaign["dataset"]["mvrv_path"],
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
    mvrv: tuple[Any, ...],
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    selected = barrier.require()["selected_trial"]
    return _reference_phase(spot, mvrv, [selected], POST_SELECTION)


def run() -> Path:
    context = preflight()
    campaign = context["campaign"]
    roster = campaign["trial_roster"]
    temp = Path(tempfile.mkdtemp(prefix=".mvrv-dislocation-", dir=OUTPUT_ROOT.parent))
    try:
        spot, mvrv = _load_inputs(campaign)
        phase_one, development_returns = _reference_phase(spot, mvrv, roster, DEVELOPMENT)
        workers_one = _run_workers(temp, "phase_one", campaign, roster, DEVELOPMENT)
        parity_one = shared._parity(phase_one, workers_one)
        dev = phase_one["development"]["F1/S1"]
        selected = min(
            roster,
            key=lambda item: (
                -dev[trial_name(item["side"], item["window"], item["holding_days"])][
                    "sharpe_per_bar"
                ],
                _trial_key(item),
            ),
        )
        selected_name = trial_name(selected["side"], selected["window"], selected["holding_days"])
        g10 = shared._g10(development_returns, selected_name)
        selection_path = shared._write_hashed_json(
            temp,
            "selection",
            {
                "schema": "tios-mvrv-dislocation-selection-v1",
                "selected_trial": selected,
                "selected_trial_name": selected_name,
                "selection_source": "development/F1-S1/sharpe_per_bar",
                "development_metric": dev[selected_name]["sharpe_per_bar"],
                "g10": g10,
            },
        )
        barrier = shared.SelectionBarrier(selection_path, shared.sha256(selection_path))
        phase_two, _ = _post_selection_reference(barrier, spot, mvrv)
        workers_two = _run_workers(temp, "phase_two", campaign, [selected], POST_SELECTION, barrier)
        parity_two = shared._parity(phase_two, workers_two)
        parity = {
            "status": "PASS" if parity_one["status"] == parity_two["status"] == "PASS" else "FAIL",
            "phase_one": parity_one,
            "phase_two": parity_two,
        }
        delayed_payload, _ = _reference_phase(
            spot, mvrv, [selected], {"full": POST_SELECTION["full"]}, delay_bars=1
        )
        delayed = delayed_payload["full"]["F1/S1"][selected_name]
        evaluation = shared._evaluate(
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
            "schema": "tios-mvrv-dislocation-campaign-result-v1",
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
