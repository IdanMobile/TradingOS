#!/usr/bin/env python3
"""Run the autonomous orchestrator: one cycle, or continuously.

    python scripts/run_orchestrator.py --once
    python scripts/run_orchestrator.py --loop --interval 900

The loop halts on any ESCALATE observation rather than continuing past it. An orchestrator
that keeps running after seeing something it cannot explain is worse than one that stops:
it accumulates work on top of a situation nobody has looked at.

Stop a running loop with:  touch artifacts/orchestrator/KILL_SWITCH
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.ops.orchestrator import REPORT_DIR, Situation, run_cycle  # noqa: E402

KILL_SWITCH = REPORT_DIR / "KILL_SWITCH"
DEFAULT_INTERVAL_SECONDS = 900

PRODUCER_MAPS = (Path("research/PROSPECTIVE_SIGNAL_EVIDENCE_PRODUCER_MAP_V1.yaml"),)


def _render(situation: Situation) -> None:
    for observation in situation.observations:
        print(f"[{observation.severity:8}] {observation.domain:11} {observation.summary}")
    if situation.halted:
        print()
        print(f"HALTED: {len(situation.escalations)} escalation(s) require an operator.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="run a single observation cycle")
    group.add_argument("--loop", action="store_true", help="run continuously until halted")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"seconds between cycles (default {DEFAULT_INTERVAL_SECONDS})",
    )
    args = parser.parse_args()

    if args.once:
        situation = run_cycle(ROOT, PRODUCER_MAPS)
        _render(situation)
        return 1 if situation.halted else 0

    while True:
        if (ROOT / KILL_SWITCH).exists():
            print("kill switch present; stopping.")
            return 0

        situation = run_cycle(ROOT, PRODUCER_MAPS)
        print(f"--- cycle {situation.observed_at.isoformat()}")
        _render(situation)

        if situation.halted:
            return 1

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
