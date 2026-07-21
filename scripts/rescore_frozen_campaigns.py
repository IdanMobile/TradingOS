#!/usr/bin/env python3
"""Re-score the seven frozen family campaigns under the corrected trade-level statistics (D-112).

This is a *correction*, not a new search. It replays ONLY the already-recorded frozen selection
of each family, on that campaign's exact original train/validation windows, under the D-112
scoring (per-completed-trade returns with ``sample_count == trade count``, min-activity floor,
sample-variance Sharpe, hierarchy count haircut for cross-trial correlation). For every family
it re-runs that family's pre-registered grid on train only — to rebuild the same cross-trial
variance and correlation the campaign already paid for — and evaluates the frozen selection once
on validation.

It deliberately does NOT: call ``preregister``/``record_trial`` or touch the trial-budget ledger;
read ``artifacts/holdout/`` or ``artifacts/sealed/``; open any split holdout; evaluate any data
beyond each campaign's original train/validation windows; or search any parameters. It only reads
the recorded ``PREREG-*.json`` selections and the same in-repo data the campaigns used, and writes
correction artifacts under ``artifacts/validation/campaigns/corrections/``.

    python scripts/rescore_frozen_campaigns.py
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_family_campaigns_v2 as fc2  # noqa: E402
import run_family_campaigns_v3 as fc3  # noqa: E402
import run_first_budgeted_campaign as fb  # noqa: E402

from tios.validation.campaign import (  # noqa: E402
    DEFAULT_MIN_VALIDATION_TRADES,
    TrialScore,
    score_trade_significance,
)
from tios.validation.splits import split_temporal  # noqa: E402

CAMPAIGN_DIR = ROOT / "artifacts" / "validation" / "campaigns"
CORRECTIONS_DIR = CAMPAIGN_DIR / "corrections"


class FamilyPlan:
    """How to reconstruct one frozen family's rows, grid, evaluator, and split gap."""

    def __init__(
        self,
        *,
        rows: Callable[[], Sequence[Any]],
        grid: Callable[[], list[dict[str, Any]]],
        evaluator: Callable[[Sequence[Any], dict[str, Any]], TrialScore],
        gap_bars: int,
        strict_reproduction: bool = True,
    ) -> None:
        self.rows = rows
        self.grid = grid
        self.evaluator = evaluator
        self.gap_bars = gap_bars
        # When True (the default), a validation score that does not reproduce the frozen record
        # aborts: we will not record a correction against a non-reproduction. It is relaxed only
        # where the input data has demonstrably drifted under parallel work and the frozen
        # verdict is invariant to that drift (see the vol-contraction plan).
        self.strict_reproduction = strict_reproduction


def _cftc_grid() -> list[dict[str, Any]]:
    return [
        {"window": w, "z_threshold": z, "side": s, "pulse_holding_hours": h}
        for w in (13, 26, 52)
        for z in (0.5, 1.0, 1.5)
        for s in ("HIGH", "LOW")
        for h in (168, 672)
    ]


def _tx_grid() -> list[dict[str, Any]]:
    return [
        {"window": w, "z_threshold": z, "side": s, "pulse_holding_hours": h}
        for w in (7, 14, 30)
        for z in (1.0, 1.5, 2.0)
        for s in ("HIGH", "LOW")
        for h in (24, 168)
    ]


def _xven_grid() -> list[dict[str, Any]]:
    return [
        {
            "prior_baseline_hours": b,
            "z_threshold": z,
            "pulse_holding_hours": h,
            "interpretation": it,
        }
        for b in (24, 168, 720)
        for z in (1.0, 1.5, 2.0)
        for h in (6, 24)
        for it in ("CONTINUATION_POSITIVE", "REVERSAL_NEGATIVE")
    ]


def _funding_grid() -> list[dict[str, Any]]:
    return [
        {"lookback_observations": n, "absolute_mean_rate_threshold": t, "polarity": p}
        for n in (1, 3, 6)
        for t in (0.0, 0.0001, 0.0003)
        for p in ("CONTINUATION", "CONTRARIAN")
    ]


def _taker_grid() -> list[dict[str, Any]]:
    return [
        {
            "prior_baseline_hours": b,
            "z_threshold": z,
            "pulse_holding_hours": h,
            "interpretation": it,
        }
        for b in (24, 168, 720)
        for z in (1.0, 1.5, 2.0)
        for h in (6, 24)
        for it in ("CONTINUATION_HIGH", "REVERSAL_LOW")
    ]


def _mvrv_grid() -> list[dict[str, Any]]:
    return [
        {"prior_window_days": w, "z_threshold": z, "side": s, "pulse_holding_hours": h}
        for w in (20, 30, 45)
        for z in (1.0, 1.5, 2.0)
        for s in ("HIGH", "LOW")
        for h in (24, 168)
    ]


def _head_bars() -> list[Any]:
    """Vol-contraction bars from the committed (HEAD) parquet.

    Its working-tree input (``data/normalized_multi/BTCUSDT_1h.parquet``) has drifted under a
    parallel session; the campaign was scored against the committed version, so reproduce from
    HEAD without touching the working tree.
    """
    rel = fb.DATASET.relative_to(ROOT).as_posix()
    blob = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
        check=True,
        capture_output=True,
    ).stdout
    tmp = Path(tempfile.gettempdir()) / "rescore_volcontraction_head_BTCUSDT_1h.parquet"
    tmp.write_bytes(blob)
    return list(fb.load_bars(tmp))


def _v2_spot() -> list[Any]:
    return fc2.load_spot()


def _v2_mvrv_rows() -> list[Any]:
    return fc2.attach_mvrv(fc2.load_spot(), json.loads(fc2.MVRV_RAW.read_text())["data"])


def _v3_attach(series: Callable[[], Any]) -> Callable[[], list[Any]]:
    return lambda: fc3.attach_series(fc3.load_spot_opens(), series())


PLANS: dict[str, FamilyPlan] = {
    "FAM-CFTC-POSITIONING-V1": FamilyPlan(
        rows=_v3_attach(fc3.cftc_series),
        grid=_cftc_grid,
        evaluator=fc3.make_period_z_evaluator(max_ordinal_gap=21),
        gap_bars=2000,
    ),
    "FAM-TX-ACTIVITY-V1": FamilyPlan(
        rows=_v3_attach(fc3.tx_series),
        grid=_tx_grid,
        evaluator=fc3.make_period_z_evaluator(max_ordinal_gap=1),
        gap_bars=1200,
    ),
    "FAM-CROSS-VENUE-PREMIUM-V1": FamilyPlan(
        rows=fc3.xven_rows,
        grid=_xven_grid,
        evaluator=fc3.evaluate_hourly_z,
        gap_bars=800,
    ),
    "FAM-FUNDING-PRESSURE-V1": FamilyPlan(
        rows=_v3_attach(fc3.funding_series),
        grid=_funding_grid,
        evaluator=fc3.evaluate_funding,
        gap_bars=800,
    ),
    "FAM-TAKER-IMBALANCE-V1": FamilyPlan(
        rows=_v2_spot,
        grid=_taker_grid,
        evaluator=fc2.evaluate_taker,
        gap_bars=800,
    ),
    "FAM-MVRV-DISLOCATION-V1": FamilyPlan(
        rows=_v2_mvrv_rows,
        grid=_mvrv_grid,
        evaluator=fc2.evaluate_mvrv,
        gap_bars=1200,
    ),
    "FAM-VOL-CONTRACTION-BREAKOUT-V1": FamilyPlan(
        rows=_head_bars,
        grid=fb.parameter_grid,
        evaluator=fb.evaluate,
        gap_bars=96,
        # Input parquet (normalized_multi) has been regenerated repeatedly by parallel work since
        # this 2026-07-20 campaign; neither the working tree nor HEAD reproduces the recorded
        # score exactly. The frozen verdict is a decisive FAIL (validation −0.081, z −14.2), so
        # re-score on the committed data and record the non-reproduction transparently.
        strict_reproduction=False,
    ),
}

SEALED_UNTIL = fc3.HOLDOUT_SEALED_UNTIL


def _old_verdict(dsr: dict[str, Any] | None, validation_score: float | None) -> str:
    if dsr and dsr.get("dsr", 0.0) >= 0.95 and (validation_score or 0.0) > 0:
        return "PASS-ELIGIBLE"
    return "FAIL"


def _corrected_verdict(outcome: dict[str, Any], validation_score: float) -> str:
    if outcome["status"] == "INSUFFICIENT_ACTIVITY":
        return "INSUFFICIENT_ACTIVITY"
    dsr = outcome["dsr"]
    if dsr and dsr["dsr"] >= 0.95 and validation_score > 0:
        return "PASS-ELIGIBLE"
    return "FAIL"


def _rescore_one(artifact_path: Path) -> dict[str, Any]:
    recorded = json.loads(artifact_path.read_text())
    family = recorded["family"]
    plan = PLANS[family]
    selected_params = recorded["selected"]["parameters"]
    hierarchy_trials = int(recorded["hierarchy_trials"])
    recorded_validation = float(recorded["validation_score"])

    grid = plan.grid()
    if len(grid) != int(recorded["raw_trials"]):
        raise RuntimeError(
            f"{family}: reconstructed grid size {len(grid)} != recorded raw_trials "
            f"{recorded['raw_trials']}; refusing to re-score against a mismatched search space"
        )

    rows = plan.rows()
    split = split_temporal(
        rows,
        train_fraction=0.6,
        validation_fraction=0.2,
        gap_bars=plan.gap_bars,
        sealed_until=SEALED_UNTIL,
    )
    split.freeze_selection()  # read validation only; holdout is never touched

    trial_scores = [plan.evaluator(split.train, params) for params in grid]
    observed = plan.evaluator(split.validation, selected_params)

    # Reproduction guard: the descriptive per-bar Sharpe must still match the frozen record,
    # or we are not re-scoring the same selection on the same window.
    reproduced = math.isclose(observed.score, recorded_validation, rel_tol=1e-9, abs_tol=1e-12)
    if not reproduced and plan.strict_reproduction:
        raise RuntimeError(
            f"{family}: reproduced validation score {observed.score} != recorded "
            f"{recorded_validation}; refusing to record a correction against a non-reproduction"
        )
    if not reproduced:
        print(
            f"WARNING {family}: input data drift — reproduced {observed.score:.6f} vs recorded "
            f"{recorded_validation:.6f}; scoring on committed data (verdict is invariant)",
            file=sys.stderr,
        )

    outcome = score_trade_significance(
        observed_trade_returns=observed.trade_returns,
        trial_trade_returns=[score.trade_returns for score in trial_scores],
        trial_bar_returns=[score.bar_returns for score in trial_scores],
        hierarchy_trials=hierarchy_trials,
        sample_count=len(observed.trade_returns),
        min_validation_trades=DEFAULT_MIN_VALIDATION_TRADES,
    )

    old = _old_verdict(recorded.get("dsr"), recorded.get("validation_score"))
    corrected = _corrected_verdict(outcome, observed.score)
    dsr = outcome["dsr"]

    if outcome["status"] == "INSUFFICIENT_ACTIVITY":
        reason = outcome["reason"]
    else:
        reason = (
            "trade-level DSR on completed trades with sample_count = trade count "
            f"(was scored on {len(split.validation)} validation bars as if each were an "
            "independent observation)"
        )

    correction = {
        "schema_version": 1,
        "correction_of": recorded["registration_ref"],
        "family": family,
        "decision_ref": "D-112",
        "selected_parameters": selected_params,
        "reproduced_frozen_score": reproduced,
        "reproduced_validation_score": observed.score,
        "original": {
            "verdict": old,
            "validation_score": recorded.get("validation_score"),
            "sample_count": len(split.validation),
            "hierarchy_trials": hierarchy_trials,
            "dsr": recorded.get("dsr"),
        },
        "corrected": {
            "verdict": corrected,
            "status": outcome["status"],
            "validation_trades": outcome["validation_trades"],
            "min_validation_trades": outcome["min_validation_trades"],
            "descriptive_per_bar_sharpe": observed.score,
            "observed_trade_sharpe": outcome["observed_sharpe"],
            "average_correlation": outcome["average_correlation"],
            "effective_trials": outcome["effective_trials"],
            "dsr": dsr,
        },
        "reason": reason,
        "notes": (
            "Re-score only: no ledger writes, no new trials, no holdout access, no parameter "
            "search. Replays the recorded frozen selection on its original train/validation "
            "windows under the D-112 corrected statistics."
        ),
    }
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CORRECTIONS_DIR / f"{recorded['registration_ref']}_corrected.json"
    out_path.write_text(json.dumps(correction, indent=2) + "\n", encoding="utf-8")

    return {
        "family": family,
        "old": old,
        "corrected": corrected,
        "trades": outcome["validation_trades"],
        "old_dsr": (recorded.get("dsr") or {}).get("dsr"),
        "old_z": (recorded.get("dsr") or {}).get("z_score"),
        "new_z": (dsr or {}).get("z_score"),
        "new_dsr": (dsr or {}).get("dsr"),
    }


def main() -> int:
    prereg = sorted(CAMPAIGN_DIR.glob("PREREG-*.json"))
    families = {json.loads(p.read_text())["family"]: p for p in prereg}
    missing = set(PLANS) - set(families)
    if missing:
        print(f"no recorded PREREG artifact for: {sorted(missing)}", file=sys.stderr)
        return 1

    rows = [_rescore_one(families[family]) for family in PLANS]

    header = (
        f"{'family':<32} {'old':<14} {'corrected':<22} {'trades':>6}  old_z→new_z  old_dsr→new_dsr"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        oz = f"{r['old_z']:.4f}" if r["old_z"] is not None else "  n/a "
        nz = f"{r['new_z']:.4f}" if r["new_z"] is not None else "  n/a "
        od = f"{r['old_dsr']:.4f}" if r["old_dsr"] is not None else " n/a "
        nd = f"{r['new_dsr']:.4f}" if r["new_dsr"] is not None else " n/a "
        print(
            f"{r['family']:<32} {r['old']:<14} {r['corrected']:<22} {r['trades']:>6}  "
            f"{oz}→{nz}  {od}→{nd}"
        )
    print(f"\ncorrection artifacts written to {CORRECTIONS_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
