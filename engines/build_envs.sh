#!/bin/zsh
# T-003-03: per-engine isolated environments (AD-02, RG-04). Idempotent.
# Version pins: research/EXISTING_CAPABILITY_REGISTRY.md §1 (2026-07-06).
# Each lane succeeds independently; failures become blocker records, never silent skips.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

manifest() { # $1=engine dir
  local venv="engines/$1/.venv"
  {
    echo "engine: $1"
    echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "python: $("$venv/bin/python" -V 2>&1)"
    echo "--- pip freeze ---"
    uv pip freeze --python "$venv/bin/python"
  } > "engines/$1/env_manifest.txt"
}

blocker() { # $1=engine $2=reason
  {
    echo "engine: $1"
    echo "recorded: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "status: BLOCKED"
    echo "reason: $2"
    echo "reproduce: engines/build_envs.sh (lane $1); full log engines/build.log"
  } > "engines/$1/BLOCKER.md"
  echo "[$1] BLOCKED: $2"
}

pip_lane() { # $1=engine $2=python-version $3...=pip specs
  local name="$1" py="$2"; shift 2
  echo "=== [$name] python=$py specs: $* ==="
  if uv venv --python "$py" "engines/$name/.venv" --clear \
     && uv pip install --python "engines/$name/.venv/bin/python" "$@"; then
    manifest "$name"
    rm -f "engines/$name/BLOCKER.md"
    echo "[$name] OK"
  else
    blocker "$name" "install failed for: $* (see build.log)"
  fi
}

docker_ready() {
  for _ in {1..60}; do docker info >/dev/null 2>&1 && return 0; sleep 3; done
  return 1
}

# --- venv lanes ---
pip_lane freqtrade 3.12 "freqtrade==2026.6" "scipy"  # scipy: required by freqtrade.data.metrics but absent from its wheel deps
pip_lane nautilus  3.13 "nautilus_trader==1.230.0"
pip_lane vectorbt  3.13 "vectorbt==1.1.0"
pip_lane lean      3.12 "lean==1.0.227"   # QuantConnect CLI; engine itself runs in Docker

# vectorbt license capture (T-001-01 / RG-03 evidence)
if [ -x engines/vectorbt/.venv/bin/python ]; then
  lic=$(find engines/vectorbt/.venv/lib -type f -path "*/vectorbt-*.dist-info/*" \( -iname "LICENSE*" -o -iname "COPYING*" \) 2>/dev/null | head -1)
  if [ -n "$lic" ]; then
    cp "$lic" engines/vectorbt/LICENSE_CAPTURED.txt
    echo "[vectorbt] license captured: $lic"
  else
    echo "[vectorbt] WARNING: no LICENSE file found in dist — verify from source repo"
  fi
fi

# --- Docker lanes ---
if docker_ready; then
  echo "=== [hummingbot] docker pull (digest-pinned; tag version-2.15.0) ==="
  HB_IMAGE="hummingbot/hummingbot@sha256:1b14fca4577cb7e8fcb4455fae09fd46b9d26334d23fa5b5e502199725371eb1"
  if docker pull "$HB_IMAGE"; then
    echo "image-digest: $HB_IMAGE" > engines/hummingbot/env_manifest.txt
    rm -f engines/hummingbot/BLOCKER.md
    echo "[hummingbot] OK"
  else
    blocker hummingbot "docker pull hummingbot/hummingbot:version-2.15.0 failed"
  fi
  echo "=== [lean] engine image pulled lazily by lean CLI on first run ==="
else
  blocker hummingbot "Docker daemon not available after 180s wait"
  echo "[lean] NOTE: CLI installed; engine Docker image deferred until daemon available" >> engines/lean/env_manifest.txt
fi

# No silent success: any lane blocker fails the whole script (security review #1, finding 1)
blocked=(engines/*/BLOCKER.md(N))
if (( ${#blocked} )); then
  echo "=== build_envs.sh done with ${#blocked} BLOCKED lane(s): ${blocked} ==="
  exit 1
fi
echo "=== build_envs.sh done: all lanes OK ==="
