from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tios.core_types.engine import MANDATORY_GRID
from tios.experiment.executor import RunExecutor, RunRequest, assert_complete_grid
from tios.experiment.ledger import Experiment, ExperimentLedger


def _ledger(tmp_path):
    ledger = ExperimentLedger(tmp_path / "ledger.jsonl")
    ledger.declare(
        Experiment(
            experiment_id="EXP-001",
            hypothesis_ref="HYP-001",
            strategy_version_ref="SV-001",
            dataset_ref="DS-001",
            engine="synthetic",
            parameter_space={},
            scenarios=tuple(s.scenario_id for s in MANDATORY_GRID),
            selection_procedure="retain all",
            created_at=datetime(2026, 7, 10, tzinfo=UTC),
        )
    )
    return ledger


def test_executor_is_idempotent_and_records_failure(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    executor = RunExecutor(ledger)
    request = RunRequest("EXP-001", {"fast": "3"}, MANDATORY_GRID[1], "e" * 64)
    calls = 0

    def runner(_request):
        nonlocal calls
        calls += 1
        return {"return": Decimal("0.1")}, ("artifacts/run.json",)

    first = executor.execute(request, runner)
    second = executor.execute(request, runner)
    assert first.run_id == second.run_id
    assert calls == 1

    failed = executor.execute(
        RunRequest("EXP-001", {"fast": "5"}, MANDATORY_GRID[1], "e" * 64),
        lambda _: (_ for _ in ()).throw(RuntimeError("engine unavailable")),
    )
    assert failed.status == "FAILED"
    assert "engine unavailable" in (failed.failure_reason or "")


def test_grid_requires_all_six_scenarios(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    executor = RunExecutor(ledger)
    request = RunRequest("EXP-001", {}, MANDATORY_GRID[0], "e" * 64)
    run = executor.execute(request, lambda _: ({}, ()))
    with pytest.raises(ValueError, match="incomplete"):
        assert_complete_grid((run,))
