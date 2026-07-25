#!/usr/bin/env python3
"""Deterministic, honest summary of the universe-search research ramp.

Zero AI, no network: reads the universe-search report (the honest screen run across every
frozen pair x timeframe by scripts/run_universe_search.py) and ranks what survived by BREADTH
(how many independent coin/timeframe contexts each strategy passed in) rather than by headline
return, because a huge single-context return on a volatile alt is the classic overfit artifact
this OS exists to NOT be fooled by.

It states plainly what these passes are and are NOT: context-level EXPLORATORY screen passes,
`promotion_eligible=false`, confounded by (a) multiple testing across thousands of trials,
(b) cross-coin correlation (crypto alts trend together, so N coins is not N independent
confirmations), and (c) single-regime pumps. They are leads for the strict gate (G10 DSR/PBO +
out-of-sample holdout with a trial-count deflation), never validated edge.

Read-only. No order, venue, credential, or execution authority; changes no state.

Usage:
    uv run python scripts/report_research_findings.py            # print + write markdown
    uv run python scripts/report_research_findings.py --no-write
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT
    / "artifacts"
    / "research_lab"
    / "universe_search"
    / "UNIVERSE_SEARCH_TRAIN_SELECT_V2_2026_07_13.json"
)
DEFAULT_MD = ROOT / "artifacts" / "reports" / "RESEARCH_FINDINGS_SUMMARY.md"


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    """Pure: rank the exploratory context passes by breadth and surface the confounders."""
    passes = report.get("context_passes", [])
    strategies: list[dict[str, Any]] = []
    coin_hits: Counter[str] = Counter()
    timeframe_hits: Counter[str] = Counter()
    total_contexts = 0
    for entry in passes:
        contexts = entry.get("contexts", [])
        total_contexts += len(contexts)
        coins = sorted({c.get("dataset", "?") for c in contexts})
        for c in contexts:
            ds = c.get("dataset", "?")
            coin_hits[ds] += 1
            if "_" in ds:
                timeframe_hits[ds.rsplit("_", 1)[1]] += 1
        best = max(contexts, key=lambda c: _num(c.get("holdout_total_return")), default={})
        strategies.append(
            {
                "strategy_id": entry.get("strategy_id"),
                "contexts_passed": len(contexts),
                "coins": [c.rsplit("_", 1)[0] for c in coins],
                "distinct_base_coins": len({c.rsplit("_", 1)[0] for c in coins}),
                "best_holdout_return_pct": round(_num(best.get("holdout_total_return")) * 100, 1),
                "best_context": best.get("dataset"),
            }
        )
    strategies.sort(key=lambda s: (s["contexts_passed"], s["distinct_base_coins"]), reverse=True)
    return {
        "schema": "tios.research_findings_summary.v1",
        "source": str(report.get("schema")),
        "evidence_scope": "CONTEXT_LEVEL_EXPLORATORY_SCREEN",
        "validated": False,
        "promotion_eligible": False,
        "execution_authority": "NONE",
        "dataset_count": report.get("dataset_count"),
        "pair_count": len(report.get("pairs", [])),
        "strategies_with_a_pass": len(passes),
        "total_context_passes": total_contexts,
        "by_breadth": strategies,
        "coins_by_strategy_count": coin_hits.most_common(15),
        "contexts_by_timeframe": dict(timeframe_hits),
        "caveats": [
            "Exploratory screen passes only: promotion_eligible=false, NOT validated edge.",
            "Multiple testing: thousands of trials produce screen passes by chance alone.",
            "Cross-coin correlation: alts move together, so N coins is not N independent bets.",
            "Single-regime: a big return on one volatile alt is the classic overfit artifact.",
            "Next gate: strict G10 (DSR>=0.95/PBO) + fresh holdout, on the broad leads.",
        ],
    }


def build_report(report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    if not report_path.is_file():
        return {"schema": "tios.research_findings_summary.v1", "error": "no universe-search report"}
    return summarize(json.loads(report_path.read_text(encoding="utf-8")))


def render_markdown(s: dict[str, Any]) -> str:
    if s.get("error"):
        return f"# Research findings\n\n{s['error']} — run scripts/run_universe_search.py first.\n"
    lines = [
        "# Research findings — universe honest screen (EXPLORATORY, not validated)",
        "",
        f"{s['strategies_with_a_pass']} strategies passed the honest screen in "
        f"{s['total_context_passes']} coin/timeframe contexts across {s['pair_count']} pairs "
        f"({s['dataset_count']} datasets). Authority NONE, not promotable, **not validated edge**.",
        "",
        "## Leads by breadth (survived in the most independent contexts — least fluke-prone)",
        "| Strategy | Contexts | Distinct coins | Best holdout % | Best context |",
        "|--|--|--|--|--|",
    ]
    for row in s["by_breadth"][:15]:
        lines.append(
            f"| {row['strategy_id']} | {row['contexts_passed']} | {row['distinct_base_coins']} | "
            f"{row['best_holdout_return_pct']} | {row['best_context']} |"
        )
    lines += [
        "",
        "## Where the passes concentrate (coin — # strategies)",
        ", ".join(f"{ds} ({n})" for ds, n in s["coins_by_strategy_count"]),
        "",
        f"Timeframe skew: {s['contexts_by_timeframe']}",
        "",
        "## Read this honestly",
    ]
    lines += [f"- {c}" for c in s["caveats"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Honest summary of the research ramp findings.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    summary = build_report(args.report)
    print(render_markdown(summary))
    if not args.no_write:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(render_markdown(summary), encoding="utf-8")
        print(f"wrote {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
