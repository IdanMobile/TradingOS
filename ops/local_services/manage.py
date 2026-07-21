#!/usr/bin/env python3
"""Repository-local entrypoint for :mod:`tios.ops.local_services`."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str((ROOT / "src").resolve()))
local_services = importlib.import_module("tios.ops.local_services")


if __name__ == "__main__":
    raise SystemExit(local_services.main(ROOT))
