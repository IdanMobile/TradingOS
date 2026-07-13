from tios.services.dashboard_api.strategy_eligibility import (
    build_strategy_eligibility_projection,
)


def test_prospective_projection_remains_fail_closed_during_warmup() -> None:
    projection = build_strategy_eligibility_projection(
        {
            "runtime": {
                "finalized_window_count": 5,
                "requested_checkpoint_count": 8_640,
            },
            "evidence": {"latest": [{"artifact_ref": "artifacts/prospective/session.json"}]},
            "capabilities": {"live_orders": "DISABLED"},
        }
    )

    assert projection["state"] == "NOT_ELIGIBLE"
    assert projection["metric_eligible"] is False
    assert projection["scorecard_eligible"] is False
    assert projection["promotion_eligible"] is False
    assert projection["execution_authority"] == "NONE"
    assert "TRIAL_POPULATION_INCOMPLETE" in projection["scorecard_blockers"]
    assert "MANDATORY_GATES_NOT_ALL_PASS" in projection["promotion_blockers"]


def test_missing_or_unsafe_observation_cannot_become_eligible() -> None:
    missing = build_strategy_eligibility_projection({})
    unsafe = build_strategy_eligibility_projection(
        {"runtime": {"finalized_window_count": 8_640}, "capabilities": {}}
    )

    assert not missing["metric_eligible"]
    assert not missing["promotion_eligible"]
    assert "LIVE_ORDER_CAPABILITY_PRESENT" in unsafe["promotion_blockers"]
