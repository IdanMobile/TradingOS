#!/usr/bin/env bash
# launchd wrapper: fixed offline-worker argv; no command or path comes from a job payload.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" "$ROOT/scripts/run_job_worker.py" run-loop --poll 1.0
