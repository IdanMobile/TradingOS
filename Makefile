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
# Frees the port first so a stale dashboard server can't block a restart with "Address already in
# use". ponytail: SIGTERMs whatever holds the fixed dashboard port 8765 — safe in dev, that port is
# the dashboard's alone; it never touches the demo lane (a separate process on no port).
dashboard:
	@pids=$$(lsof -ti:8765 2>/dev/null); if [ -n "$$pids" ]; then echo "freeing port 8765 (pid $$pids)"; kill $$pids 2>/dev/null || true; sleep 1; fi
	uv run python -m tios.services.dashboard_ui.server

# ONE COMMAND TO BRING EVERYTHING UP: dashboard + supervised activity lane, persistent across
# sleep and login. `make down` reverses it exactly.
#
# Deliberately NOT folded into `make dashboard`. That target is read-only — no venue, no orders —
# and it must stay the command you can run just to LOOK at something. If the innocuous command also
# opened positions, the day that matters is the day you ran it without meaning to. `up` is named so
# that starting trading is something you asked for, and it says so before it does it.
#
# Fake money, Bybit VENUE_DEMO, execution authority NONE, 0 validated strategies. This raises
# measurement UPTIME; it cannot improve results. Stop everything instantly, without this Makefile:
#   touch artifacts/trading_domain/demo_lane/KILL_SWITCH
up:
	@echo "make up will:"
	@echo "  1. clear a stale KILL_SWITCH so the supervisor is allowed to start the lane"
	@echo "  2. install + load the launchd agent $(LANE_AGENT) (persists across login and sleep)"
	@echo "  3. start the read-only dashboard on http://127.0.0.1:8765"
	@echo "  the lane trades FAKE money on the demo account. 'make down' reverses all of it."
	@rm -f artifacts/trading_domain/demo_lane/KILL_SWITCH
	@$(MAKE) --no-print-directory lane-supervise-install
	@echo "lane supervised. giving launchd a moment, then starting the dashboard..."
	@sleep 2
	@$(MAKE) --no-print-directory lane-supervise-status | head -5 || true
	@$(MAKE) --no-print-directory dashboard

# Reverses `make up`: stops the lane via its own kill switch (the supervisor then refuses to
# restart it), removes the launchd agent, and frees the dashboard port. The kill switch is written
# BEFORE the agent is removed so there is no window where launchd relaunches a lane on the way out.
down:
	@echo "stopping the lane (KILL_SWITCH), removing $(LANE_AGENT), freeing port 8765"
	@mkdir -p artifacts/trading_domain/demo_lane
	@touch artifacts/trading_domain/demo_lane/KILL_SWITCH
	@$(MAKE) --no-print-directory lane-supervise-uninstall || true
	@pids=$$(lsof -ti:8765 2>/dev/null); if [ -n "$$pids" ]; then kill $$pids 2>/dev/null || true; fi
	@echo "down. open positions are NOT closed — they keep their venue-side resting stops."
	@echo "clear the stop flag when you next want to run: make up"

# D-104/D-105 ETH demo measurement lane (Bybit DEMO account, fake money, UNVALIDATED
# candidate). Stop it any time: touch artifacts/trading_domain/demo_lane/KILL_SWITCH
demo-lane:
	uv run python scripts/demo_eth_lane.py --loop

demo-lane-once:
	uv run python scripts/demo_eth_lane.py --once

# Supervised auto-start for the demo activity lane (launchd). The LaunchAgent runs
# scripts/supervise_demo_lane.py, never the lane directly: KILL_SWITCH refusal, the crash-loop
# guard and the audit record live in that wrapper. Fake money, execution authority NONE —
# supervision increases measurement UPTIME only, it does not improve results.
LANE_AGENT = com.tios.demo-lane
LANE_AGENT_PLIST = $(HOME)/Library/LaunchAgents/$(LANE_AGENT).plist

lane-supervise-install:
	@echo "installing $(LANE_AGENT): copy ops/$(LANE_AGENT).plist -> $(LANE_AGENT_PLIST), then launchctl bootstrap gui/$$(id -u)"
	@mkdir -p $(HOME)/Library/LaunchAgents
	cp ops/$(LANE_AGENT).plist $(LANE_AGENT_PLIST)
	@# Idempotent: bootstrap fails if the label is already loaded, so drop any existing one first.
	@# `make up` must be safe to re-run; the bootout is expected to fail on a clean machine.
	-@launchctl bootout gui/$$(id -u)/$(LANE_AGENT) 2>/dev/null || true
	launchctl bootstrap gui/$$(id -u) $(LANE_AGENT_PLIST)

lane-supervise-uninstall:
	@echo "uninstalling $(LANE_AGENT): launchctl bootout gui/$$(id -u), then remove $(LANE_AGENT_PLIST)"
	-launchctl bootout gui/$$(id -u)/$(LANE_AGENT)
	rm -f $(LANE_AGENT_PLIST)

lane-supervise-status:
	@echo "status of $(LANE_AGENT) (launchctl print; nothing is started or stopped)"
	@launchctl print gui/$$(id -u)/$(LANE_AGENT) || echo "$(LANE_AGENT) is not loaded"

# Clears the supervisor's crash-loop guard so a refused lane can be supervised again.
lane-supervise-clear-guard:
	@echo "clearing the crash-loop guard: rm -f artifacts/trading_domain/demo_lane/supervisor_starts.json"
	rm -f artifacts/trading_domain/demo_lane/supervisor_starts.json

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

.PHONY: check check-full _gate bootstrap audit required dashboard up down jobs-init jobs-once \
	eth-signal orchestrator orchestrator-once lane-supervise-install lane-supervise-uninstall \
	lane-supervise-status lane-supervise-clear-guard demo-lane demo-lane-once
