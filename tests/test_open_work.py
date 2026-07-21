import json
from pathlib import Path

from tios.ops.driver import park
from tios.ops.orchestrator import ESCALATE, REPORT_DIR, SITUATION_FILENAME
from tios.services.dashboard_api.open_work import (
    AGENT_EXECUTABLE,
    BLOCKED_EXTERNAL,
    RECURRING,
    REQUIRES_OPERATOR,
    build_open_work,
)


def _refs(view: dict, bucket: str) -> set[str]:
    return {row["title"] for row in view[bucket]}


def test_empty_project_reports_nothing_open(tmp_path: Path) -> None:
    view = build_open_work(tmp_path)
    assert view["total_open"] == 0
    assert view["execution_authority"] == "NONE"


def test_parked_items_are_merged_with_the_task_registry(tmp_path: Path) -> None:
    """The registry alone reads as zero open while real work sits in the parked ledger."""
    park(tmp_path, item="no universe data", cause="dataset does not exist", phase="2")
    view = build_open_work(tmp_path)
    assert "no universe data" in _refs(view, BLOCKED_EXTERNAL)
    assert view["total_open"] == 1


def test_operator_phrases_route_to_requires_operator(tmp_path: Path) -> None:
    park(tmp_path, item="AI runs", cause="no provider credential is configured", phase="2")
    view = build_open_work(tmp_path)
    assert "AI runs" in _refs(view, REQUIRES_OPERATOR)


def test_merely_mentioning_the_operator_does_not_route_to_them(tmp_path: Path) -> None:
    """Loose substring matching inflates the list a human thinks they owe work on."""
    park(
        tmp_path,
        item="historical bytes",
        cause="the operator was not at fault; the bytes were never retained",
        phase="2",
    )
    view = build_open_work(tmp_path)
    assert "historical bytes" in _refs(view, BLOCKED_EXTERNAL)
    assert "historical bytes" not in _refs(view, REQUIRES_OPERATOR)


def test_resolved_parks_drop_out_of_open_work(tmp_path: Path) -> None:
    ledger = tmp_path / "artifacts" / "driver" / "parked_items.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps({"item": "done thing", "cause": "x", "status": "RESOLVED 2026-07-20"}) + "\n",
        encoding="utf-8",
    )
    assert build_open_work(tmp_path)["total_open"] == 0


def test_resolved_but_review_requested_stays_visible(tmp_path: Path) -> None:
    """A landed security-boundary change still needs a human to look at it."""
    ledger = tmp_path / "artifacts" / "driver" / "parked_items.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(
            {
                "item": "security assertion swapped",
                "cause": "fix landed and green",
                "status": "RESOLVED 2026-07-20 — OPERATOR REVIEW REQUESTED",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    view = build_open_work(tmp_path)
    assert "security assertion swapped" in _refs(view, REQUIRES_OPERATOR)


def test_escalations_lead_the_operator_bucket(tmp_path: Path) -> None:
    park(tmp_path, item="credential thing", cause="no provider credential", phase="2")
    situation = tmp_path / REPORT_DIR / SITUATION_FILENAME
    situation.parent.mkdir(parents=True, exist_ok=True)
    situation.write_text(
        json.dumps(
            {
                "observations": [
                    {"domain": "statistical", "severity": ESCALATE, "summary": "holdout read twice"}
                ]
            }
        ),
        encoding="utf-8",
    )

    view = build_open_work(tmp_path)

    assert view[REQUIRES_OPERATOR][0]["title"] == "holdout read twice"
    assert view[REQUIRES_OPERATOR][0]["source"] == "escalation"


def test_real_project_classification_is_stable() -> None:
    """The shipped project must not report work as needing a human when it does not."""
    root = Path()
    if not (root / "todos").is_dir():
        return
    view = build_open_work(root)
    assert view["counts"][RECURRING] > 0, "state-upkeep tasks are recurring by design"
    # Everything credential- or S4-gated belongs to the operator, never to an agent.
    for row in view[AGENT_EXECUTABLE]:
        assert "CREDENTIAL" not in row["detail"].upper()
        assert "S4" not in row["detail"].upper()
