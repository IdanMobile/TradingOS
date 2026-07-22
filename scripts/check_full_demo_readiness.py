#!/usr/bin/env python3
"""Print the strictly read-only full-demo readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tios.ops.demo_readiness import assess_full_demo_readiness, exit_code

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--pretty", action="store_true", help="indent JSON for operator reading")
    return result


def main() -> int:
    args = parser().parse_args()
    report = assess_full_demo_readiness(ROOT)
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
