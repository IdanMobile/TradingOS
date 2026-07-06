# Developer README — Trading Intelligence OS (S1)

## One-command local gate (T-003-04)

```sh
make check
```

Runs, in order: `ruff check`, `ruff format --check`, `mypy` (strict, src/tios), `pytest`
(unit + property tests, architecture dependency-law test, decision-ID uniqueness,
secret scan over tracked files). Must pass before any commit. Target: <5 min.

Setup: `uv sync` (installs the pinned dev group into `.venv`; exact versions in `uv.lock`).

## Layout

- `src/tios/` — modular monolith per `docs/architecture/MODULE_CATALOG.md` (dependency law enforced by `tests/test_architecture.py`)
- `engines/<name>/` — isolated per-engine environments (T-003-03); never imported by `src/tios`
- `artifacts/` — evidence tree (SSOT WS1); reports tracked, large files hashed
- `data/{raw,normalized}/` — gitignored payloads, tracked manifests
- `scripts/bootstrap.py` — idempotent workspace bootstrap

## Secrets

Copy `.env.example` → `.env` (gitignored) and fill values locally. Never commit or paste
secret values anywhere. The secret scan in the gate fails the build on key-shaped strings.
