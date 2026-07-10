"""Build the frozen T1-T8 fixture corpus (T-011-02, REQ-043).

Every fixture is self-contained (claim + its own source text, or synthetic
task input + ground truth) rather than referencing live external documents,
so the corpus needs no network access and carries no risk of asserting
unverified real-world facts. Where a fixture quotes this repository's own
frozen docs, that quote *is* the source and its `publication_date` is the
quoted file's path (git-tracked, so its history is independently checkable).

Run directly: `python benchmarks/ai_agent/fixtures/build_fixtures.py`.
Idempotent — re-running regenerates the same files (content is a literal
below, not derived from wall-clock time), so the manifest hash is stable
except for `frozen_utc` which is refreshed on each build.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).parent / "corpus"

# --- T1: source verification (12 claims, self-contained source + label) ---
T1_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T1-01",
        "source_ref": "benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md",
        "publication_date": "2026-07-06",
        "source_text": "Controlled mode has network disabled.",
        "claim": "The suite's Controlled mode runs with network access disabled.",
        "label": "supported",
        "evidence_span": "Controlled mode has network disabled.",
    },
    {
        "id": "T1-02",
        "source_ref": "benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md",
        "publication_date": "2026-07-06",
        "source_text": "Never emit one global model score.",
        "claim": "The suite requires emitting exactly one global model score per run.",
        "label": "contradicted",
        "evidence_span": "Never emit one global model score.",
    },
    {
        "id": "T1-03",
        "source_ref": "benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md",
        "publication_date": "2026-07-06",
        "source_text": "Do not treat raw profit as proof of reasoning skill.",
        "claim": "Raw profit is treated as sufficient proof of reasoning skill.",
        "label": "contradicted",
        "evidence_span": "Do not treat raw profit as proof of reasoning skill.",
    },
    {
        "id": "T1-04",
        "source_ref": "specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md",
        "publication_date": "2026-07-05",
        "source_text": "Never score model name alone.",
        "claim": "The blueprint's canonical evaluation unit is the model name alone.",
        "label": "contradicted",
        "evidence_span": "Never score model name alone.",
    },
    {
        "id": "T1-05",
        "source_ref": "specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md",
        "publication_date": "2026-07-05",
        "source_text": "same-model self-judging is not sufficient for critical tasks.",
        "claim": "A model judging its own outputs is sufficient evaluation for critical tasks.",
        "label": "contradicted",
        "evidence_span": "same-model self-judging is not sufficient for critical tasks.",
    },
    {
        "id": "T1-06",
        "source_ref": "specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md",
        "publication_date": "2026-07-05",
        "source_text": "LLM-as-judge scores require calibration and spot human review.",
        "claim": "LLM-as-judge scores are used without any human calibration step.",
        "label": "contradicted",
        "evidence_span": "LLM-as-judge scores require calibration and spot human review.",
    },
    {
        "id": "T1-07",
        "source_ref": "docs/architecture/AD.md",
        "publication_date": "2026-07-06",
        "source_text": "Anthropic >=60d notice; OpenAI as little as 2 weeks for previews",
        "claim": "Anthropic's minimum model-deprecation notice window is at least 60 days.",
        "label": "supported",
        "evidence_span": "Anthropic >=60d notice",
    },
    {
        "id": "T1-08",
        "source_ref": "docs/architecture/AD.md",
        "publication_date": "2026-07-06",
        "source_text": "OpenAI Evals platform EOL 2026-11-30",
        "claim": "The OpenAI Evals platform has no announced end-of-life date.",
        "label": "contradicted",
        "evidence_span": "OpenAI Evals platform EOL 2026-11-30",
    },
    {
        "id": "T1-09",
        "source_ref": "docs/architecture/AD.md",
        "publication_date": "2026-07-06",
        "source_text": "MLflow-first harness with Inspect as design reference",
        "claim": "The benchmark harness is built MLflow-first, treating Inspect as a design reference rather than a dependency.",  # noqa: E501
        "label": "supported",
        "evidence_span": "MLflow-first harness with Inspect as design reference",
    },
    {
        "id": "T1-10",
        "source_ref": "todos/11_ai_agent_eval.md",
        "publication_date": "2026-07-06",
        "source_text": "Human approval: Yes (operator reviews samples)",
        "claim": "T-011-04 judge calibration requires no human operator involvement.",
        "label": "contradicted",
        "evidence_span": "Human approval: Yes (operator reviews samples)",
    },
    {
        "id": "T1-11",
        "source_ref": "todos/11_ai_agent_eval.md",
        "publication_date": "2026-07-06",
        "source_text": "Precondition: intake-gate credential disposition = configured; T-001-04 pricing verification.",  # noqa: E501
        "claim": "T-011-05 may run before any AI-provider credential is configured.",
        "label": "contradicted",
        "evidence_span": "Precondition: intake-gate credential disposition = configured",
    },
    {
        "id": "T1-12",
        "source_ref": "benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md",
        "publication_date": "2026-07-06",
        "source_text": "Rerun frozen tasks after model/provider changes.",
        "claim": "Mode C (Longitudinal) reruns the frozen task set only once, at suite creation time.",  # noqa: E501
        "label": "insufficient",
        "evidence_span": "Rerun frozen tasks after model/provider changes.",
    },
]

# --- T2: strategy extraction (5 descriptions, matching src/tios/strategy FAMILIES) ---
T2_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T2-01",
        "family": "trend_following",
        "description": (
            "Go long when the 10-period SMA of close crosses above the 30-period SMA; "
            "exit when it crosses back below. No shorting. Evaluate signals on bar close, "
            "execute at the next bar's open."
        ),
        "ground_truth": {
            "family": "trend_following",
            "entry_rule": "sma_fast > sma_slow",
            "exit_rule": "sma_fast < sma_slow",
            "ambiguities": ["equal-value cross (sma_fast == sma_slow) is unspecified"],
        },
    },
    {
        "id": "T2-02",
        "family": "mean_reversion",
        "description": (
            "When RSI(14) drops below 30, buy; when RSI(14) rises above 70, sell. "
            "Position is flat otherwise."
        ),
        "ground_truth": {
            "family": "mean_reversion",
            "entry_rule": "rsi_14 < 30",
            "exit_rule": "rsi_14 > 70",
            "ambiguities": ["behavior while 30 <= RSI <= 70 and already in a position is unstated"],
        },
    },
    {
        "id": "T2-03",
        "family": "breakout",
        "description": (
            "Enter long when close exceeds the highest high of the prior 20 bars. "
            "Exit when close falls below the lowest low of the prior 10 bars."
        ),
        "ground_truth": {
            "family": "breakout",
            "entry_rule": "close > donchian_high_20",
            "exit_rule": "close < donchian_low_10",
            "ambiguities": ["whether the breakout bar itself is included in the 20-bar window"],
        },
    },
    {
        "id": "T2-04",
        "family": "carry",
        "description": (
            "Hold the position for as long as the funding-rate signal is positive; "
            "flatten immediately when it turns negative or zero."
        ),
        "ground_truth": {
            "family": "carry",
            "entry_rule": "funding_rate > 0",
            "exit_rule": "funding_rate <= 0",
            "ambiguities": ["funding-rate sampling frequency is not stated"],
        },
    },
    {
        "id": "T2-05",
        "family": "market_making",
        "description": (
            "Continuously quote both sides around the mid-price with a fixed spread; "
            "cancel and re-quote whenever the mid-price moves by more than half a tick."
        ),
        "ground_truth": {
            "family": "market_making",
            "entry_rule": "always_in_market",
            "exit_rule": "n/a (continuous quoting)",
            "ambiguities": ["inventory-skew adjustment to the spread is not described"],
        },
    },
]

# --- T3: semantic implementation review (2 items) ---
T3_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T3-01",
        "strategy": "Buy when close crosses above the 30-period SMA; sell when it crosses back below.",  # noqa: E501
        "implementation": "entry: close > sma_30 (evaluated and executed on the same bar's close)",
        "ground_truth_mismatches": [
            "implementation executes on the signal bar's close instead of the next bar's open (lookahead)"  # noqa: E501
        ],
    },
    {
        "id": "T3-02",
        "strategy": "Exit any long position after 5 bars regardless of price.",
        "implementation": "exit: bars_held >= 5, but bars_held is reset to 0 only on a new entry, never decremented while flat",  # noqa: E501
        "ground_truth_mismatches": [
            "bars_held counter can carry a stale non-zero value into the next trade if reset is missed while flat"  # noqa: E501
        ],
    },
]

# --- T4: backtest plan construction (2 items) ---
T4_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T4-01",
        "strategy_ref": "T2-01 (trend_following SMA cross)",
        "available_datasets": ["DS-CRYPTO-SPOT-BAKEOFF-V1 (frozen, 5m bars)"],
        "ground_truth_checklist": [
            "warm-up bars excluded from P&L (longest SMA window)",
            "signal-bar-close vs next-bar-open execution timing stated explicitly",
            "OOS split date recorded before any parameter search",
        ],
    },
    {
        "id": "T4-02",
        "strategy_ref": "T2-03 (breakout Donchian)",
        "available_datasets": ["DS-CRYPTO-SPOT-BAKEOFF-V1 (frozen, 5m bars)"],
        "ground_truth_checklist": [
            "current-bar inclusion in the rolling high/low window resolved and stated",
            "per-trade taker fee applied on both entry and exit",
            "missing-dependency check: donchian channel indicator availability confirmed",
        ],
    },
]

# --- T5: red-team critique (2 items, synthetic report numbers) ---
T5_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T5-01",
        "backtest_report": (
            "Strategy X: Sharpe 3.1, max drawdown 4%, 5 trades total, backtested on "
            "2021-01-01..2021-03-01 BTCUSDT 5m bars, no fees applied."
        ),
        "ground_truth_failure_modes": [
            "sample size (5 trades) too small for the Sharpe estimate to be meaningful",
            "no trading fees applied overstates net returns",
            "single 2-month window with no OOS or regime diversity",
        ],
    },
    {
        "id": "T5-02",
        "backtest_report": (
            "Strategy Y: 40% annualized return over 2020-2023, parameters chosen via grid "
            "search over the same 2020-2023 window; no walk-forward validation performed."
        ),
        "ground_truth_failure_modes": [
            "in-sample parameter search with no held-out OOS window (overfitting)",
            "no walk-forward or regime-split validation performed",
        ],
    },
]

# --- T6: tool comparison (3 tools, short well-known public facts) ---
T6_DOCS: dict[str, str] = {
    "freqtrade": "Freqtrade is an open-source, Python-based free crypto trading bot framework supporting backtesting and dry-run/live modes via exchange adapters (ccxt).",  # noqa: E501
    "vectorbt": "vectorbt is an open-source Python library for backtesting and analyzing trading strategies using vectorized (NumPy/pandas) operations for speed.",  # noqa: E501
    "nautilus_trader": "NautilusTrader is an open-source, high-performance algorithmic trading platform written in Python/Rust supporting backtesting and live trading with the same strategy code.",  # noqa: E501
}
T6_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T6-01",
        "tool_names": list(T6_DOCS.keys()),
        "docs": T6_DOCS,
        "ground_truth_matrix_keys": ["language", "backtest_live_code_parity", "vectorized_backtesting"],  # noqa: E501
    }
]

# --- T7: dictionary/ontology extraction (2 items, overloaded terms) ---
T7_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T7-01",
        "term": "leverage",
        "docs": {
            "spot_venue_doc": "Spot trading does not offer leverage; all positions are fully collateralized by the held asset.",  # noqa: E501
            "perp_venue_doc": "Perpetual futures leverage lets a trader open a position larger than their posted margin, up to an exchange-defined maximum multiple.",  # noqa: E501
        },
        "ground_truth_concepts": [
            {"concept": "leverage (spot)", "meaning": "not applicable / always 1x"},
            {"concept": "leverage (perpetual futures)", "meaning": "margin multiple up to an exchange maximum"},  # noqa: E501
        ],
    },
    {
        "id": "T7-02",
        "term": "fill",
        "docs": {
            "maker_taker_doc": "A fill is the (partial or full) execution of an order against the book; maker fills add liquidity, taker fills remove it.",  # noqa: E501
            "backtest_engine_doc": "In the backtest engine, a 'fill' is a simulated execution event assigned a synthetic price and timestamp, not a real exchange match.",  # noqa: E501
        },
        "ground_truth_concepts": [
            {"concept": "fill (live exchange)", "meaning": "real order-book match, maker or taker"},
            {"concept": "fill (backtest engine)", "meaning": "simulated execution event, no real matching"},  # noqa: E501
        ],
    },
]

# --- T8: research asset synthesis (1 item, 8 sources with a contradiction) ---
T8_SOURCES: list[dict[str, str]] = [
    {"ref": "S1", "kind": "primary", "date": "2026-06-01", "text": "Exchange fee schedule page: BTCUSDT taker fee 0.10%."},  # noqa: E501
    {"ref": "S2", "kind": "primary", "date": "2026-06-15", "text": "Exchange fee schedule page (updated): BTCUSDT taker fee 0.075% for VIP0 with a native-token discount."},  # noqa: E501
    {"ref": "S3", "kind": "secondary", "date": "2026-05-01", "text": "Blog post: 'BTCUSDT taker fee is 0.10%' (cites S1, predates S2's update)."},  # noqa: E501
    {"ref": "S4", "kind": "secondary", "date": "2026-01-10", "text": "Old forum post: 'fees are basically free on this exchange' (no date-stamped fee figure)."},  # noqa: E501
    {"ref": "S5", "kind": "primary", "date": "2026-06-15", "text": "Exchange API docs: fee endpoint returns effective per-account fee tier, may differ from the published schedule."},  # noqa: E501
    {"ref": "S6", "kind": "secondary", "date": "2026-06-20", "text": "Third-party fee comparison site lists this exchange at 0.10% taker, last checked 2026-05-01 per its own footer."},  # noqa: E501
    {"ref": "S7", "kind": "primary", "date": "2026-06-15", "text": "Exchange fee schedule page: native-token discount requires opt-in and a minimum balance."},  # noqa: E501
    {"ref": "S8", "kind": "secondary", "date": "2026-06-25", "text": "Community wiki: repeats the 0.075% figure without noting the opt-in/minimum-balance condition."},  # noqa: E501
]
T8_ITEMS: list[dict[str, Any]] = [
    {
        "id": "T8-01",
        "sources": T8_SOURCES,
        "ground_truth": {
            "primary_sources": ["S1", "S2", "S5", "S7"],
            "contradiction": "S1 (0.10%) vs S2 (0.075% conditional) — S2 is newer and primary and carries an unstated precondition (S7) that S3/S6/S8 omit.",  # noqa: E501
            "freshness_caveat": "S4 has no date-stamped figure and should not be used for a current fee value.",  # noqa: E501
        },
    }
]


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def build() -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {
        "t1_source_verification": T1_ITEMS,
        "t2_strategy_extraction": T2_ITEMS,
        "t3_semantic_review": T3_ITEMS,
        "t4_backtest_plan": T4_ITEMS,
        "t5_redteam_critique": T5_ITEMS,
        "t6_tool_comparison": T6_ITEMS,
        "t7_dictionary_ontology": T7_ITEMS,
        "t8_research_synthesis": T8_ITEMS,
    }
    manifest: dict[str, Any] = {
        "frozen_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {},
        "files": {},
        "leakage_controls": {
            "corpus_hashes_frozen": True,
            "publication_dates_recorded": True,
            "controlled_mode_network_disabled": True,
            "masking_applied_where_required": "not required: all fixtures are synthetic or self-referential to this repo's own frozen docs, no real ticker/entity/date leakage risk",  # noqa: E501
            "raw_profit_not_treated_as_reasoning_proof": True,
        },
    }
    for group, items in groups.items():
        manifest["counts"][group] = len(items)
        for item in items:
            rel = f"{group}/{item['id']}.json"
            _write_json(CORPUS_DIR / rel, item)
            digest = hashlib.sha256((CORPUS_DIR / rel).read_bytes()).hexdigest()
            manifest["files"][rel] = digest
    _write_json(CORPUS_DIR / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    m = build()
    total = sum(m["counts"].values())
    print(f"built {total} fixtures across {len(m['counts'])} task classes -> {CORPUS_DIR}")
