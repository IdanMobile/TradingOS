#!/usr/bin/env python3
"""T-003-02 workspace bootstrap. Idempotent: safe to re-run on a clean or existing checkout.

Creates the AD §F repository tree, MODULE_CATALOG module skeletons, the SSOT WS1
artifacts evidence tree with machine-readable manifest stubs, and runtime data dirs.
Never overwrites an existing file.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# MODULE_CATALOG modules laid out per AD §F
TIOS_PACKAGES = [
    "core_types", "dataset", "strategy", "parity", "experiment", "validation",
    "evidence", "approval", "knowledge", "ai_eval", "memory", "security_ops",
    "adapters", "adapters/freqtrade", "adapters/nautilus", "adapters/lean",
    "adapters/hummingbot", "adapters/vectorbt", "adapters/lineage",
    "services", "services/jobs", "services/ingestion", "services/reporting",
    "services/dashboard_api", "services/dashboard_ui",
]

# SSOT WS1 minimum evidence directories
ARTIFACT_DIRS = [
    "datasets", "bakeoff", "lineage", "validation",
    "strategy_ingestion", "ai_benchmarks", "reports",
]

# Isolated per-engine environments (AD-02); contents built by T-003-03
ENGINE_DIRS = ["freqtrade", "nautilus", "lean", "hummingbot", "vectorbt"]

# Gitignored payload dirs; recreated here so a clean checkout works
DATA_DIRS = ["data/raw", "data/normalized"]

OTHER_DIRS = ["fixtures", "tests"]


def ensure_file(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def main() -> None:
    created = []

    pkg_root = ROOT / "src" / "tios"
    for pkg in ["", *TIOS_PACKAGES]:
        init = pkg_root / pkg / "__init__.py"
        if ensure_file(init, ""):
            created.append(init)

    for name in ARTIFACT_DIRS:
        d = ROOT / "artifacts" / name
        manifest = d / "manifest.json"
        stub = json.dumps({"schema": "tios-artifact-manifest-v1", "artifacts": []}, indent=2) + "\n"
        if ensure_file(manifest, stub):
            created.append(manifest)

    for name in ENGINE_DIRS:
        keep = ROOT / "engines" / name / ".gitkeep"
        if ensure_file(keep, ""):
            created.append(keep)

    for rel in DATA_DIRS + OTHER_DIRS:
        d = ROOT / rel
        if not d.exists():
            d.mkdir(parents=True)
            created.append(d)

    for p in created:
        print(f"created {p.relative_to(ROOT)}")
    print(f"bootstrap: {len(created)} new path(s); existing paths untouched.")


if __name__ == "__main__":
    main()
