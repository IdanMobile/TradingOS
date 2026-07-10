# Local gate (T-003-04, TEST_MASTER_PLAN §5). Single entry point: `make check`
check:
	@set -eu; \
	artifact=artifacts/quality/check.json; \
	temporary="$$artifact.tmp.$$$$"; \
	rm -f "$$artifact" "$$artifact".tmp.*; \
	trap 'status=$$?; rm -f "$$temporary"; if [ "$$status" -ne 0 ]; then rm -f "$$artifact"; fi; exit "$$status"' EXIT; \
	trap 'exit 130' HUP INT TERM; \
	uv run ruff check src tests scripts; \
	uv run ruff format --check src tests scripts; \
	uv run mypy; \
	uv run pytest; \
	mkdir -p artifacts/quality; \
	CHECK_ARTIFACT="$$artifact" CHECK_ARTIFACT_TMP="$$temporary" uv run python -c 'import datetime,json,os,pathlib; target=pathlib.Path(os.environ["CHECK_ARTIFACT"]); temporary=pathlib.Path(os.environ["CHECK_ARTIFACT_TMP"]); payload={"schema_version":2,"gate":"check","command":"make check","status":"PASS","includes_dependency_audit":False,"generated_at":datetime.datetime.now(datetime.UTC).isoformat()}; temporary.write_text(json.dumps(payload,indent=2)+"\n"); stream=temporary.open("rb"); os.fsync(stream.fileno()); stream.close(); os.replace(temporary,target)'

bootstrap:
	python3 scripts/bootstrap.py

# Dependency vulnerability audit (T-003-05). Network-dependent, so not part of `check`.
audit:
	uv export --no-emit-project --quiet -o /tmp/tios-requirements.txt && uv run pip-audit -r /tmp/tios-requirements.txt --disable-pip

# Release/merge gate. `audit` is separate because its vulnerability database requires network;
# failure or inability to reach it fails this target while `check` remains usable offline.
required: check audit

dashboard:
	uv run python -m tios.services.dashboard_ui.server

jobs-init:
	uv run python scripts/run_job_worker.py init

jobs-once:
	uv run python scripts/run_job_worker.py run-once

.PHONY: check bootstrap audit required dashboard jobs-init jobs-once
