"""The 'Needs your attention' feed must surface only genuinely actionable items."""

from __future__ import annotations

from tios.services.dashboard_api import cockpit


def test_decision_is_actionable_only_beyond_keep_deferred() -> None:
    assert cockpit._decision_is_actionable({"options": [{"id": "keep_deferred"}]}) is False
    assert cockpit._decision_is_actionable({"options": [{"id": "acknowledge_recurring"}]}) is False
    assert cockpit._decision_is_actionable({"options": []}) is False
    assert (
        cockpit._decision_is_actionable(
            {"options": [{"id": "keep_deferred"}, {"id": "authorize_design_only"}]}
        )
        is True
    )


def test_research_attention_excludes_deferred_only_decisions() -> None:
    status = {
        "generated_at": "2026-07-12T00:00:00+00:00",
        "open_tasks": [],
        "workspace_actions": [
            {
                "id": "T-015-01",
                "title": "Paper-lane architecture decision",
                "status": "DEFERRED-S3",
                "latest_decision": None,
                "options": [{"id": "keep_deferred", "label": "Keep deferred"}],
            },
            {
                "id": "T-020-01",
                "title": "S3 design research",
                "status": "DEFERRED-S3",
                "latest_decision": None,
                "options": [{"id": "keep_deferred"}, {"id": "authorize_design_only"}],
            },
        ],
    }
    attention = cockpit._research_attention(status, {"latest_jobs": []})
    ids = {item["item_id"] for item in attention}
    assert "T-015-01" not in ids  # deferred-only -> not "needs attention"
    assert "T-020-01" in ids  # a real decision exists -> surfaced
    assert all("Decide in" in item["summary"] for item in attention)  # says what to do
