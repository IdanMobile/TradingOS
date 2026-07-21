import json
from pathlib import Path

from tios.ops.driver import park
from tios.ops.orchestrator import ESCALATE, INFO, REPORT_DIR, SITUATION_FILENAME
from tios.services.dashboard_api.orchestrator_view import build_orchestrator_view


def _situation(root: Path, *, halted: bool, observations: list[dict]) -> None:
    target = root / REPORT_DIR / SITUATION_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "observed_at": "2026-07-20T02:00:00+00:00",
                "halted": halted,
                "observations": observations,
            }
        ),
        encoding="utf-8",
    )


def test_never_run_state_is_explicit(tmp_path: Path) -> None:
    view = build_orchestrator_view(tmp_path)
    assert view["state"] == "NEVER_RUN"
    assert not view["halted"]
    assert view["execution_authority"] == "NONE"


def test_running_state_reports_no_operator_need(tmp_path: Path) -> None:
    _situation(
        tmp_path,
        halted=False,
        observations=[{"domain": "evidence", "severity": INFO, "summary": "all current"}],
    )
    view = build_orchestrator_view(tmp_path)
    assert view["state"] == "RUNNING"
    assert view["escalations"] == []


def test_halted_state_surfaces_escalations_first(tmp_path: Path) -> None:
    """A halted orchestrator that looks idle is the worst thing this page could show."""
    _situation(
        tmp_path,
        halted=True,
        observations=[
            {"domain": "evidence", "severity": INFO, "summary": "routine"},
            {"domain": "statistical", "severity": ESCALATE, "summary": "holdout opened twice"},
        ],
    )

    view = build_orchestrator_view(tmp_path)

    assert view["state"] == "HALTED_AWAITING_OPERATOR"
    assert view["halted"]
    assert len(view["escalations"]) == 1
    assert "holdout opened twice" in view["escalations"][0]["summary"]
    assert "operator" in view["interpretation"]


def test_parked_items_are_projected_with_causes(tmp_path: Path) -> None:
    park(tmp_path, item="historical REST payloads", cause="bytes never retained", phase="2")
    view = build_orchestrator_view(tmp_path)
    assert len(view["parked"]) == 1
    assert view["parked"][0]["cause"] == "bytes never retained"


def test_corrupt_situation_file_degrades_to_never_run(tmp_path: Path) -> None:
    target = tmp_path / REPORT_DIR / SITUATION_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not json", encoding="utf-8")
    assert build_orchestrator_view(tmp_path)["state"] == "NEVER_RUN"


def test_view_never_exposes_a_control(tmp_path: Path) -> None:
    """Read-only by construction: no action, command, or mutation key may appear."""
    _situation(tmp_path, halted=False, observations=[])
    view = build_orchestrator_view(tmp_path)
    forbidden = {"actions_available", "commands", "start", "stop", "controls", "endpoints"}
    assert not (forbidden & set(view))
    assert view["execution_authority"] == "NONE"
