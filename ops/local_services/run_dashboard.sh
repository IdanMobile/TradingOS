#!/usr/bin/env bash
# launchd wrapper: fixed dashboard argv, repository cwd, venv Python, and explicit PYTHONPATH.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" -m tios.services.dashboard_ui.server --host 127.0.0.1 --port 8765
