from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tios.experiment.ledger import Experiment, ExperimentLedger, LedgerError, Run


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="EXP-001",
        hypothesis_ref="HYP-001",
        strategy_version_ref="SV-001",
        dataset_ref="DS-001",
        engine="freqtrade",
        parameter_space={"fast": ("3", "5")},
        scenarios=("F0/S0", "F1/S1"),
        selection_procedure="retain all trials; select by validation package",
        created_at=datetime(2026, 7, 10, tzinfo=UTC),
    )


def _run(run_id: str, status: str = "COMPLETED") -> Run:
    return Run(
        run_id=run_id,
        experiment_id="EXP-001",
        trial_key=run_id,
        params={"fast": "3"},
        scenario="F1/S1",
        status=status,  # type: ignore[arg-type]
        metrics={"return": Decimal("0.12")},
        artifact_refs=("artifacts/runs/RUN-001",),
        environment_manifest_hash="a" * 64,
        started_at=datetime(2026, 7, 10, tzinfo=UTC),
        finished_at=datetime(2026, 7, 10, 1, tzinfo=UTC),
        failure_reason="engine stopped" if status == "FAILED" else None,
    )


def test_ledger_retains_all_trials_and_winner_must_reference_one(tmp_path) -> None:
    ledger = ExperimentLedger(tmp_path / "ledger.jsonl")
    ledger.declare(_experiment())
    ledger.record_run(_run("RUN-001"))
    ledger.record_run(_run("RUN-002"))

    assert [run.run_id for run in ledger.runs("EXP-001")] == ["RUN-001", "RUN-002"]
    ledger.assert_winner_references_population("EXP-001", "RUN-002")
    with pytest.raises(LedgerError, match="retained run"):
        ledger.assert_winner_references_population("EXP-001", "RUN-999")


def test_ledger_is_append_only_and_failed_runs_preserve_reason(tmp_path) -> None:
    ledger = ExperimentLedger(tmp_path / "ledger.jsonl")
    ledger.declare(_experiment())
    ledger.record_run(_run("RUN-FAILED", "FAILED"))
    before = ledger.path.read_bytes()
    with pytest.raises(LedgerError, match="already exists"):
        ledger.record_run(_run("RUN-FAILED", "FAILED"))
    assert ledger.path.read_bytes() == before
    assert ledger.runs()[0].failure_reason == "engine stopped"
