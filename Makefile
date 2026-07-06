# Local gate (T-003-04, TEST_MASTER_PLAN §5). Single entry point: `make check`
check:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy
	uv run pytest

bootstrap:
	python3 scripts/bootstrap.py

.PHONY: check bootstrap
