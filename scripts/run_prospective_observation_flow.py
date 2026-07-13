#!/usr/bin/env python3
"""Operate the TradingOS-managed prospective observation flow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tios.services.observations import (
    build_observation_projection,
    run_managed_observation,
    write_run_intent,
)

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("run", "adopt"):
        command = commands.add_parser(name)
        command.add_argument("--checkpoint-windows", type=int, required=True)
    commands.add_parser("status")
    commands.add_parser("verify")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "run":
        return run_managed_observation(ROOT, args.checkpoint_windows)
    if args.command == "adopt":
        path = write_run_intent(
            ROOT,
            args.checkpoint_windows,
            mode="ADOPTED",
        )
        print(path)
        return 0
    projection = build_observation_projection(ROOT)
    print(json.dumps(projection, indent=2))
    if args.command == "verify" and (
        projection["availability"] != "AVAILABLE"
        or projection["management"] != "MANAGED"
        or projection["state"] in {"ERROR", "STALE"}
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
