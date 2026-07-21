# Local gate (T-003-04, TEST_MASTER_PLAN §5). Single entry point: `make check`
#
# `check` excludes the `slow` data-package byte-integrity tests, which are ~94% of total
# runtime (31 min -> ~2 min). Those verify that retained archives still hash correctly —
# they change when DATA changes, not when code does, so gating every code edit on them
# was checking the wrong thing frequently. They run in `make check-full`, which is the
# real release gate and is what `required` depends on.
#
# The orchestrator gates self-modification on `check`; a human merge should use `required`.
# GATE_FULL is a separate plain flag rather than reusing GATE_PYTEST_ARGS: embedding the
# quoted `-m "not slow"` inside another quoted assignment nests quotes, and sh splits it
# into three words.
check: GATE_PYTEST_ARGS = -m "not slow"
check: GATE_FULL = 0
check: _gate

check-full: GATE_PYTEST_ARGS =
check-full: GATE_FULL = 1
check-full: _gate

_gate:
	@set -eu; \
	artifact=artifacts/quality/check.json; \
	temporary="$$artifact.tmp.$$$$"; \
	rm -f "$$artifact" "$$artifact".tmp.*; \
	trap 'status=$$?; rm -f "$$temporary"; if [ "$$status" -ne 0 ]; then rm -f "$$artifact"; fi; exit "$$status"' EXIT; \
	trap 'exit 130' HUP INT TERM; \
	python3 -c 'import hashlib,pathlib,re; text=pathlib.Path("PACKAGE_INTEGRITY_MANIFEST.md").read_text(); rows=re.findall(r"\| `([^`]+)` \| `([a-f0-9]{64})`", text); bad=[path for path,digest in rows if not pathlib.Path(path).is_file() or hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()!=digest]; print("package integrity:", "PASS" if not bad else "FAIL " + ", ".join(bad)); raise SystemExit(bool(bad))'; \
	uv run ruff check src tests scripts; \
	uv run ruff format --check src tests scripts; \
	uv run mypy; \
	uv run pytest $(GATE_PYTEST_ARGS); \
	mkdir -p artifacts/quality; \
	CHECK_ARTIFACT="$$artifact" CHECK_ARTIFACT_TMP="$$temporary" GATE_FULL="$(GATE_FULL)" uv run python -c 'import datetime,json,os,pathlib; target=pathlib.Path(os.environ["CHECK_ARTIFACT"]); temporary=pathlib.Path(os.environ["CHECK_ARTIFACT_TMP"]); full=os.environ.get("GATE_FULL")=="1"; payload={"schema_version":3,"gate":"check-full" if full else "check","command":"make check-full" if full else "make check","status":"PASS","includes_slow_data_tests":full,"includes_dependency_audit":False,"generated_at":datetime.datetime.now(datetime.UTC).isoformat()}; temporary.write_text(json.dumps(payload,indent=2)+"\n"); stream=temporary.open("rb"); os.fsync(stream.fileno()); stream.close(); os.replace(temporary,target)'

bootstrap:
	python3 scripts/bootstrap.py

# Dependency vulnerability audit (T-003-05). Network-dependent, so not part of `check`.
audit:
	uv export --no-emit-project --quiet -o /tmp/tios-requirements.txt && uv run pip-audit -r /tmp/tios-requirements.txt --disable-pip

# Release/merge gate. `audit` is separate because its vulnerability database requires network;
# failure or inability to reach it fails this target while `check` remains usable offline.
# Depends on `check-full`, not `check`: a release must verify data-package integrity too.
required: check-full audit

# Local dashboard (loopback-only, read-only: no venue, no orders, no real money).
# Open the URL it prints (default http://127.0.0.1:8765).
dashboard:
	uv run python -m tios.services.dashboard_ui.server

# D-104/D-105 ETH demo measurement lane (Bybit DEMO account, fake money, UNVALIDATED
# candidate). Stop it any time: touch artifacts/trading_domain/demo_lane/KILL_SWITCH
demo-lane:
	uv run python scripts/demo_eth_lane.py --loop

demo-lane-once:
	uv run python scripts/demo_eth_lane.py --once

jobs-init:
	uv run python scripts/run_job_worker.py init

jobs-once:
	uv run python scripts/run_job_worker.py run-once

# Read-only ETH strategy signal + independent risk result. Never creates orders.
eth-signal:
	@uv run python scripts/verify_eth_volume_breakout_flow.py --summary

# Autonomous orchestrator. Observes statistical health, evidence freshness, blockers,
# strategy coverage, and the execution envelope. Halts on escalation; never places orders.
# Stop a loop with: touch artifacts/orchestrator/KILL_SWITCH
orchestrator:
	uv run python scripts/run_orchestrator.py --loop

orchestrator-once:
	@uv run python scripts/run_orchestrator.py --once

.PHONY: check check-full _gate bootstrap audit required dashboard jobs-init jobs-once eth-signal \
	orchestrator orchestrator-once
