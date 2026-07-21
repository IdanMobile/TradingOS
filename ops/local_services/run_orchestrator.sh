#!/usr/bin/env bash
# launchd wrapper: fixed argv; its helper distinguishes an intentional halt from a crash.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" "$ROOT/ops/local_services/manage.py" run-orchestrator
