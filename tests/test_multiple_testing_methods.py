import pytest

from tios.validation import (
    deflated_sharpe_ratio,
    expected_maximum_noise_sharpe,
    implied_independent_trials,
    probability_of_backtest_overfitting,
    probability_of_backtest_overfitting_from_return_statistics,
    sharpe_variance_from_trials,
)


def test_pbo_cscv_known_answer_fixture() -> None:
    result = probability_of_backtest_overfitting(
        (
            (10, 10, -10, -10),
            (1, 1, 1, 1),
            (-10, -10, 10, 10),
        )
    )

    assert result["split_count"] == 6
    assert result["pbo"] == pytest.approx(1 / 3)
    assert result["lambda_logits"] == pytest.approx(
        (
            -1.0986122886681098,
            1.0986122886681098,
            1.0986122886681098,
            1.0986122886681098,
            1.0986122886681098,
            -1.0986122886681098,
        )
    )


def test_dsr_known_answer_fixture() -> None:
    trial_sharpes = (0.10, 0.20, 0.30, 0.40)
    sharpe_variance = sharpe_variance_from_trials(trial_sharpes)

    assert sharpe_variance == pytest.approx(0.016666666666666666)
    assert expected_maximum_noise_sharpe(sharpe_variance, 4) == pytest.approx(0.1358284725416625)

    strong = deflated_sharpe_ratio(0.50, sharpe_variance, 4, 36)
    weak = deflated_sharpe_ratio(0.10, sharpe_variance, 4, 36)

    assert strong["z_score"] == pytest.approx(2.0312517321749834)
    assert strong["dsr"] == pytest.approx(0.9788852674948445)
    assert weak["z_score"] == pytest.approx(-0.2114361707275827)
    assert weak["dsr"] == pytest.approx(0.4162734672557345)

    non_normal = deflated_sharpe_ratio(
        0.50,
        sharpe_variance,
        4,
        36,
        skewness=1.0,
        kurtosis=4.0,
    )
    assert non_normal["z_score"] == pytest.approx(2.5983859463896857)
    assert non_normal["dsr"] == pytest.approx(0.9953168422791726)


def test_pbo_uses_sharpe_from_retained_slice_statistics() -> None:
    # Each tuple is count, sum, sum-of-squares. The resulting CSCV fixture is
    # deliberately tiny; it validates aggregation and the governed score path.
    result = probability_of_backtest_overfitting_from_return_statistics(
        (
            ((2, 3, 5), (2, 3, 5), (2, -3, 5), (2, -3, 5)),
            ((2, 1, 1), (2, 1, 1), (2, 1, 1), (2, 1, 1)),
            ((2, -3, 5), (2, -3, 5), (2, 3, 5), (2, 3, 5)),
        )
    )
    assert result["split_count"] == 6
    assert result["pbo"] == pytest.approx(1 / 3)


def test_implied_independent_trials_matches_appendix_three_endpoints() -> None:
    assert implied_independent_trials(10, 0.0) == 10
    assert implied_independent_trials(10, 1.0) == 1
    assert implied_independent_trials(10, 0.25) == pytest.approx(7.75)


def test_multiple_testing_methods_fail_closed_on_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even number"):
        probability_of_backtest_overfitting(((1, 2, 3), (3, 2, 1)))
    with pytest.raises(ValueError, match="same slice count"):
        probability_of_backtest_overfitting(((1, 2), (3,)))
    with pytest.raises(ValueError, match="sample_count"):
        deflated_sharpe_ratio(0.1, 0.01, 2, 1)
    with pytest.raises(ValueError, match="independent_trials"):
        expected_maximum_noise_sharpe(0.01, 0)
    with pytest.raises(ValueError, match="at least two trial Sharpes"):
        sharpe_variance_from_trials((0.1,))
    with pytest.raises(ValueError, match="average_correlation"):
        implied_independent_trials(2, -0.1)
