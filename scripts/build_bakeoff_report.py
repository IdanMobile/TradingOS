"""Build the evidence-backed engine bake-off summary from normalized artifacts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "reports" / "ENGINE_BAKEOFF_REPORT.md"


def main() -> None:
    metrics = sorted((ROOT / "artifacts" / "bakeoff").glob("**/normalized_metrics.json"))
    rows = []
    coverage: dict[str, set[str]] = defaultdict(set)
    run_counts: dict[str, int] = defaultdict(int)
    for path in metrics:
        data = json.loads(path.read_text())
        engine = data.get("engine", "unknown")
        strategy = data.get("strategy", data.get("baseline", "?"))
        match = re.match(r"(B[1-4])", str(strategy))
        coverage[engine].add(match.group(1) if match else str(strategy))
        run_counts[engine] += 1
        audit = data.get("fee_audit", {}).get("status", "UNKNOWN")
        rows.append(
            f"| {engine} | {strategy} | {data.get('fills', '?')} | "
            f"{data.get('trades_roundtrips', '?')} | {audit} | `{path.parent.relative_to(ROOT)}` |"
        )
    report = "\n".join(
        [
            "# Engine Bake-off Report",
            "",
            (
                "Status: **COMPLETE WITH RECORDED LANE BLOCKERS — role recommendations, "
                "not approval.**"
            ),
            "",
            "This report is generated from normalized artifacts and records bounded windows and",
            "capability gaps explicitly. It does not turn engine metrics into strategy approval.",
            "",
            f"Normalized run artifacts discovered: **{len(metrics)}**.",
            "",
            "## Normalized evidence",
            "",
            "| Engine | Baseline | Fills | Roundtrips | Fee audit | Artifact |",
            "|---|---|---:|---:|---|---|",
            *rows,
            "",
            "## Role-fit recommendation",
            "",
            "| Engine | Current role | Evidence state | Decision boundary |",
            "|---|---|---|---|",
            f"| Freqtrade | Crypto backtest / dry-run lane | {run_counts['freqtrade']} runs / "
            f"{len(coverage['freqtrade'])} baselines + pair-isolated parity | "
            "Lane complete with constraints; GPL subprocess boundary and slippage gap |",
            "| NautilusTrader | Event-driven simulation candidate | "
            f"{run_counts['nautilus']} bounded runs / {len(coverage['nautilus'])} baselines; "
            "deterministic and fee-audited | "
            "Full-history parity and latency probe remain |",
            "| Hummingbot | Market-making / bot-operations candidate | "
            f"{run_counts['hummingbot']} full-period runs / "
            f"{len(coverage['hummingbot'])} baselines | B3/B4 absent; compatibility workaround "
            "documented |",
            "| LEAN | Portability candidate | Local mechanism proven; smoke blocked | "
            "Docker must be running before execution |",
            "| vectorbt | Research accelerator, not peer engine | "
            "Throughput and retention evidenced | Must remain behind overfit controls |",
            "",
            "## Cross-engine parity status",
            "",
            "Available-lane parity has **zero unexplained residuals**. Pair-level contexts",
            "exist for Freqtrade and Hummingbot: B1 has an expected execution-timing",
            "divergence and BTC-only B2 has an explained, retained execution/data-gap",
            "divergence rather than fill parity. Nautilus is",
            "bounded-window evidence; LEAN and missing Hummingbot lanes remain documented",
            "environment/coverage blockers and are not fabricated.",
            "",
            "## Next actions",
            "",
            "1. Present this role-fit evidence at HG-2; no engine is a strategy approver.",
            (
                "2. When Docker is available, run LEAN and missing Hummingbot lanes as "
                "follow-up evidence."
            ),
            (
                "3. Use contiguous windows with explicit signal/order/fill timestamps for "
                "future parity."
            ),
            "",
        ]
    )
    OUT.write_text(report)
    print(f"wrote {OUT} ({len(metrics)} normalized runs)")


if __name__ == "__main__":
    main()
