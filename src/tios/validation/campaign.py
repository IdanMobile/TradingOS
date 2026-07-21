"""End-to-end campaign runner: pre-register, search on train only, account every trial.

This is the piece that makes the substrate usable rather than merely present. It wires
together pre-registration (`trial_budget`), leak-proof splits (`splits`), immutable strategy
identity (`registry`), and multiple-testing statistics (`multiple_testing`) into one path
that a family cannot accidentally step outside of.

The ordering is the whole point, and it is enforced rather than documented:

1. Pre-register the search space. Unregistered searches cannot be scored at all.
2. Search on training data only. Validation is unreachable until selection is frozen.
3. Record every trial to the ledger as it is evaluated — not a summary afterwards, because
   a count reconstructed after the fact is exactly the self-report SUP-008 found wanting.
4. Freeze selection, then evaluate the frozen choice once on validation.
5. Deflate against the *ledger* trial count, not the surviving population.
6. Leave the holdout sealed. It is not part of a campaign; it is what a campaign is
   eventually judged against, once, much later.

What this runner deliberately does not do is choose a family. Family selection is a recorded
supervisor decision in this project (D-052, D-053), and D-054 requires a distinct-family cycle
before another StrategyVersion may seek validation. A runner that picked its own family would
route around the one governance step that gives a negative result meaning.

Significance is computed on a series consistent with its own count (D-112). An evaluator that
returns a :class:`TrialScore` exposes the per-completed-trade returns it realised; the DSR that
decides the verdict is built on those trade returns with ``sample_count == len(trade returns)``,
never the whole validation-bar count. A per-bar Sharpe over only in-position bars, scored as if
every validation bar were an independent observation, inflates ``z`` by ``1/sqrt(in-position
fraction)`` — the F1 defect that made FAM-CFTC-POSITIONING-V1 look like a PASS on a single
completed trade. A pre-registered ``min_validation_trades`` floor fails closed to
``INSUFFICIENT_ACTIVITY`` (distinct from FAIL) rather than claiming a DSR on too little activity.

PBO is *not* computed on this path. A CSCV/PBO estimate needs per-trial per-slice return
statistics this runner does not retain, and a declared-but-unenforced ``pbo_max`` threshold is
worse than an honestly absent one (D-112, F3a). Campaign specs on this path therefore must not
advertise a PBO control; ``thresholds`` should carry only the controls this runner enforces
(``dsr_min`` and ``min_validation_trades``).

A bare ``float`` return remains accepted for legacy/opaque-score callers, but it cannot claim
trade-level significance: it falls back to a whole-window ``sample_count`` and the raw hierarchy
count. Real families return :class:`TrialScore`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from math import sqrt
from pathlib import Path
from typing import Any

from tios.validation.multiple_testing import (
    deflated_sharpe_ratio,
    implied_independent_trials,
    sharpe_variance_from_trials,
)
from tios.validation.splits import TemporalSplit
from tios.validation.trial_budget import (
    family_count,
    global_trial_count,
    preregister,
    record_trial,
    trial_count,
    verify_declared_trials,
)

SCHEMA_VERSION = 1
CAMPAIGN_DIR = Path("artifacts") / "validation" / "campaigns"
DEFAULT_MIN_VALIDATION_TRADES = 10


class CampaignError(RuntimeError):
    """Raised when a campaign would violate its own pre-registration."""


@dataclass(frozen=True)
class TrialScore:
    """One evaluation's honest output.

    ``score`` is a descriptive ranking statistic (the per-bar Sharpe families already use to
    pick a candidate on train). ``trade_returns`` is the significance series: one realised
    return per completed, non-overlapping trade — the series the DSR is actually built on, with
    ``sample_count == len(trade_returns)``. ``bar_returns`` is that same PnL aligned to every
    decision bar (0.0 when flat or marking), used only to estimate the cross-trial correlation
    that haircuts the hierarchy trial count.
    """

    score: float
    trade_returns: tuple[float, ...]
    bar_returns: tuple[float, ...] = ()


@dataclass(frozen=True)
class TrialResult:
    trial_key: str
    parameters: dict[str, Any]
    train_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "trial_key": self.trial_key,
            "parameters": self.parameters,
            "train_score": self.train_score,
        }


@dataclass(frozen=True)
class CampaignResult:
    registration_ref: str
    family: str
    raw_trials: int
    ledger_trials: int
    hierarchy_trials: int
    admitted_families: int
    selected: TrialResult | None
    validation_score: float | None
    dsr: dict[str, float] | None
    blockers: tuple[str, ...]
    holdout_sealed: bool = True
    validation_trades: int | None = None
    insufficient_activity: bool = False
    effective_trials: float | None = None
    average_correlation: float | None = None
    min_validation_trades: int = DEFAULT_MIN_VALIDATION_TRADES

    @property
    def promotable(self) -> bool:
        """Always False here. A campaign produces evidence, never a promotion."""
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "registration_ref": self.registration_ref,
            "family": self.family,
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "raw_trials": self.raw_trials,
            "ledger_trials": self.ledger_trials,
            "hierarchy_trials": self.hierarchy_trials,
            "admitted_families": self.admitted_families,
            "selected": self.selected.as_dict() if self.selected else None,
            "validation_score": self.validation_score,
            "validation_trades": self.validation_trades,
            "min_validation_trades": self.min_validation_trades,
            "insufficient_activity": self.insufficient_activity,
            "effective_trials": self.effective_trials,
            "average_correlation": self.average_correlation,
            "dsr": self.dsr,
            "blockers": list(self.blockers),
            "holdout_sealed": self.holdout_sealed,
            "promotion_eligible": False,
            "execution_authority": "NONE",
            "interpretation": (
                "Campaign evidence only. Significance is trade-level: the DSR is built on the "
                f"selected variant's {self.validation_trades} completed validation trades, not "
                "the whole validation-bar count. Deflation uses the hierarchy-wide trial count "
                f"({self.hierarchy_trials} trials across {self.admitted_families} admitted "
                "families), haircut for cross-trial correlation to an effective "
                f"{self.effective_trials} trials, so both a wider search and an extra family "
                "lower the result rather than hiding. No promotion follows from this artifact; "
                "the sealed holdout remains unread."
            ),
        }


def _sample_sharpe(returns: Sequence[float]) -> float:
    """Non-annualised Sharpe using sample variance (÷ n-1).

    One convention across the DSR path (D-112, F6): this matches
    :func:`sharpe_variance_from_trials`, which is the cross-sectional *sample* variance of the
    trial Sharpes. ``n < 2`` never attempts a Sharpe.
    """
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    variance = sum((value - mean) ** 2 for value in returns) / (n - 1)
    return mean / sqrt(variance) if variance > 0 else 0.0


def _pairwise_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    """Pearson correlation over bars active in at least one series, clamped to ``[0, 1]``.

    Co-flat bars (both series 0.0) are excluded: including them would make two rarely-active
    trials look near-perfectly correlated through shared zeros, spuriously shrinking the
    effective trial count and making the deflated bar *easier* to clear — the wrong direction
    for a control. Undefined or negative correlation clamps to 0.0 (treated as independent),
    which is the conservative choice because fewer implied-correlated trials means a higher bar.
    """
    indices = [i for i in range(len(left)) if left[i] != 0.0 or right[i] != 0.0]
    if len(indices) < 2:
        return 0.0
    a = [left[i] for i in indices]
    b = [right[i] for i in indices]
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    if var_a <= 0 or var_b <= 0:
        return 0.0
    covariance = sum((a[k] - mean_a) * (b[k] - mean_b) for k in range(len(a)))
    return max(0.0, min(1.0, covariance / sqrt(var_a * var_b)))


def _average_correlation(bar_returns: Sequence[Sequence[float]]) -> float:
    """Mean pairwise correlation of the trials' aligned per-bar PnL vectors."""
    vectors = [tuple(vector) for vector in bar_returns if vector]
    pairs = list(combinations(range(len(vectors)), 2))
    if not pairs:
        return 0.0
    width = min(len(vector) for vector in vectors)
    total = sum(_pairwise_correlation(vectors[i][:width], vectors[j][:width]) for i, j in pairs)
    return total / len(pairs)


def score_trade_significance(
    *,
    observed_trade_returns: Sequence[float],
    trial_trade_returns: Sequence[Sequence[float]],
    trial_bar_returns: Sequence[Sequence[float]],
    hierarchy_trials: int,
    sample_count: int,
    min_validation_trades: int = DEFAULT_MIN_VALIDATION_TRADES,
) -> dict[str, Any]:
    """Deflated significance of one frozen selection, computed on its trade returns.

    Single source of truth shared by :func:`run_campaign` and the frozen-campaign re-score, so
    the live path and the correction cannot silently disagree.

    ``sample_count`` must equal ``len(observed_trade_returns)``: the whole point of D-112 is that
    the count fed to the DSR is the length of the series its Sharpe was computed on. The guard
    fails closed rather than trusting a caller to keep them in step.
    """
    if sample_count != len(observed_trade_returns):
        raise CampaignError(
            "sample_count must equal the scored trade series length "
            f"(got sample_count={sample_count}, len(returns)={len(observed_trade_returns)}); "
            "counting whole validation bars while scoring only completed trades inflates z"
        )
    n = sample_count
    if n < min_validation_trades:
        return {
            "status": "INSUFFICIENT_ACTIVITY",
            "validation_trades": n,
            "min_validation_trades": min_validation_trades,
            "observed_sharpe": None,
            "effective_trials": None,
            "average_correlation": None,
            "dsr": None,
            "reason": (
                f"{n} completed validation trade(s) < pre-registered floor "
                f"{min_validation_trades}; no DSR is claimed on this little activity"
            ),
        }

    observed_sharpe = _sample_sharpe(observed_trade_returns)
    trial_sharpes = [_sample_sharpe(returns) for returns in trial_trade_returns]
    variance = sharpe_variance_from_trials(trial_sharpes)
    average_correlation = _average_correlation(trial_bar_returns)
    effective_trials = implied_independent_trials(hierarchy_trials, average_correlation)
    dsr = deflated_sharpe_ratio(
        observed_sharpe=observed_sharpe,
        sharpe_variance=variance,
        independent_trials=effective_trials,
        sample_count=n,
    )
    return {
        "status": "OK",
        "validation_trades": n,
        "min_validation_trades": min_validation_trades,
        "observed_sharpe": observed_sharpe,
        "effective_trials": effective_trials,
        "average_correlation": average_correlation,
        "dsr": dsr,
    }


def _as_trial_score(value: float | TrialScore) -> TrialScore:
    """Normalise an evaluator return. A bare float is a legacy opaque score with no series."""
    if isinstance(value, TrialScore):
        return value
    return TrialScore(score=float(value), trade_returns=(), bar_returns=())


def run_campaign[T](
    root: Path,
    *,
    family: str,
    search_space: dict[str, Any],
    primary_endpoint: str,
    cost_model: dict[str, Any],
    chronology: str,
    thresholds: dict[str, Any],
    stop_rules: str,
    split: TemporalSplit[T],
    parameter_grid: Sequence[dict[str, Any]],
    evaluate: Callable[[Sequence[T], dict[str, Any]], float | TrialScore],
    fold_count: int = 5,
    min_validation_trades: int = DEFAULT_MIN_VALIDATION_TRADES,
) -> CampaignResult:
    """Run one pre-registered campaign and return its honest result.

    `evaluate` scores one parameter set over a data window and must be pure: given the same
    window and parameters it returns the same score. It is called only with training data
    during the search — the split makes anything else unreachable. Returning a
    :class:`TrialScore` (rather than a bare float) is what unlocks trade-level significance.

    ``fold_count`` is retained for signature compatibility; nested walk-forward folds were dead
    on this path (the fold test blocks were never scored) and are no longer computed (D-112, F4).
    """
    if not parameter_grid:
        raise CampaignError("a campaign requires at least one parameter set")

    registration_ref = preregister(
        root,
        family=family,
        search_space=search_space,
        primary_endpoint=primary_endpoint,
        cost_model=cost_model,
        chronology=chronology,
        thresholds=thresholds,
        stop_rules=stop_rules,
    )

    results: list[TrialResult] = []
    scores: list[TrialScore] = []
    for index, parameters in enumerate(parameter_grid):
        trial_key = f"{registration_ref}-{index:05d}"
        score = _as_trial_score(evaluate(split.train, parameters))

        # Recorded as evaluated, not summarised afterwards: a count reconstructed later is
        # the self-report this whole mechanism exists to replace.
        record_trial(root, registration_ref, trial_key)
        results.append(TrialResult(trial_key, dict(parameters), score.score))
        scores.append(score)

    best_index = max(range(len(results)), key=lambda i: results[i].train_score)
    selected = results[best_index]

    # Only now may validation be read. Whether the evaluator returns a TrialScore (real family,
    # trade-level significance) or a bare float (legacy opaque score) is decided by this return.
    split.freeze_selection()
    raw_validation = evaluate(split.validation, selected.parameters)
    validation = _as_trial_score(raw_validation)
    trade_level = isinstance(raw_validation, TrialScore)

    ledger_trials = trial_count(root, registration_ref)
    hierarchy_trials = global_trial_count(root)
    admitted_families = family_count(root)
    verdict = verify_declared_trials(root, registration_ref, len(parameter_grid))

    dsr: dict[str, float] | None = None
    blockers = list(verdict.blockers)
    validation_trades: int | None = None
    insufficient_activity = False
    effective_trials: float | None = None
    average_correlation: float | None = None

    if len(results) < 2:
        blockers.append("DSR_UNAVAILABLE: fewer than two trials")
    elif not trade_level:
        # Legacy/opaque-score path: no trade series, so significance falls back to the
        # whole-window count and the raw hierarchy. Real families return TrialScore.
        try:
            variance = sharpe_variance_from_trials([score.score for score in scores])
            dsr = deflated_sharpe_ratio(
                observed_sharpe=validation.score,
                sharpe_variance=variance,
                independent_trials=float(hierarchy_trials),
                sample_count=len(split.validation),
            )
        except ValueError as error:
            blockers.append(f"DSR_UNAVAILABLE: {error}")
    else:
        outcome = score_trade_significance(
            observed_trade_returns=validation.trade_returns,
            trial_trade_returns=[score.trade_returns for score in scores],
            trial_bar_returns=[score.bar_returns for score in scores],
            hierarchy_trials=hierarchy_trials,
            sample_count=len(validation.trade_returns),
            min_validation_trades=min_validation_trades,
        )
        validation_trades = outcome["validation_trades"]
        if outcome["status"] == "INSUFFICIENT_ACTIVITY":
            insufficient_activity = True
            blockers.append(f"INSUFFICIENT_ACTIVITY: {outcome['reason']}")
        else:
            dsr = outcome["dsr"]
            effective_trials = outcome["effective_trials"]
            average_correlation = outcome["average_correlation"]

    result = CampaignResult(
        registration_ref=registration_ref,
        family=family,
        raw_trials=len(parameter_grid),
        ledger_trials=ledger_trials,
        hierarchy_trials=hierarchy_trials,
        admitted_families=admitted_families,
        selected=selected,
        validation_score=validation.score,
        dsr=dsr,
        blockers=tuple(blockers),
        holdout_sealed=not split.holdout_opened,
        validation_trades=validation_trades,
        insufficient_activity=insufficient_activity,
        effective_trials=effective_trials,
        average_correlation=average_correlation,
        min_validation_trades=min_validation_trades,
    )
    _write(root, result)
    return result


def _write(root: Path, result: CampaignResult) -> None:
    target = root / CAMPAIGN_DIR / f"{result.registration_ref}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
