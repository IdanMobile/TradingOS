"""Checks for the Operations-tab completion matrix (initiative x stage x completion)."""

from __future__ import annotations

from pathlib import Path

from tios.services.dashboard_api.operations import build_operations
from tios.services.dashboard_api.status import build_completion_matrix

ROOT = Path(__file__).resolve().parents[1]


def test_completion_matrix_reflects_real_stage_state() -> None:
    matrix = build_completion_matrix(ROOT)
    assert matrix["current_stage"] == "S2 (constrained)"
    assert "not product completeness" in matrix["note"]
    rows = {row["id"]: row for row in matrix["rows"]}

    # S3 paper trading (initiative 15) is NOT entered: not done, all tasks gated.
    paper = rows["15"]
    assert paper["stage"].startswith("S3")
    assert paper["overall"] != "DONE"
    assert paper["tasks_gated"] == paper["tasks_total"] > 0

    # An S1 foundation initiative (repository foundation) is genuinely done.
    repo = rows["03"]
    assert repo["stage"].startswith("S1")
    assert repo["overall"] == "DONE"
    assert repo["tasks_done"] == repo["tasks_total"] > 0


def test_operations_projection_includes_completion_matrix() -> None:
    ops = build_operations(ROOT)
    assert "completion_matrix" in ops
    assert ops["completion_matrix"]["rows"]  # non-empty grid
    assert ops["execution_authority"] == "NONE"


def test_completion_matrix_is_empty_without_todo_index(tmp_path: Path) -> None:
    # No TODO.md / todos/ in an empty root -> read-only projection returns an empty grid.
    matrix = build_completion_matrix(tmp_path)
    assert matrix["rows"] == [] and matrix["by_stage"] == {}


def test_operations_tab_renders_completion_matrix() -> None:
    html = (ROOT / "src" / "tios" / "services" / "dashboard_ui" / "dashboard.html").read_text()
    assert 'id="opsCompletion"' in html
    assert "Completion matrix" in html
