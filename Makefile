# Local gate (T-003-04, TEST_MASTER_PLAN §5). Single entry point: `make check`
check:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy
	uv run pytest

bootstrap:
	python3 scripts/bootstrap.py

# Dependency vulnerability audit (T-003-05). Network-dependent, so not part of `check`.
audit:
	uv export --no-emit-project --quiet -o /tmp/tios-requirements.txt && uv run pip-audit -r /tmp/tios-requirements.txt --disable-pip

.PHONY: check bootstrap audit
