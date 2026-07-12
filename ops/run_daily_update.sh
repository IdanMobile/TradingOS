#!/usr/bin/env bash
# launchd wrapper: sets cwd + PYTHONPATH explicitly so the venv resolves reliably
# under launchd's minimal environment (direct venv-python invocation trips EX_CONFIG).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" -m tios.dataset.daily_update
