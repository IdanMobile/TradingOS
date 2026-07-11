import pytest

from tios.validation import (
    deflated_sharpe_ratio,
    expected_maximum_noise_sharpe,
    probability_of_backtest_overfitting,
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

    assert strong["z_score"] == pytest.approx(2.144598891621087)
    assert strong["dsr"] == pytest.approx(0.9840075344965666)
    assert weak["z_score"] == pytest.approx(-0.210993163132767)
    assert weak["dsr"] == pytest.approx(0.4164463031498148)


def test_multiple_testing_methods_fail_closed_on_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even number"):
        probability_of_backtest_overfitting(((1, 2, 3), (3, 2, 1)))
    with pytest.raises(ValueError, match="same slice count"):
        probability_of_backtest_overfitting(((1, 2), (3,)))
    with pytest.raises(ValueError, match="sample_count"):
        deflated_sharpe_ratio(0.1, 0.01, 2, 1)
    with pytest.raises(ValueError, match="independent_trials"):
        expected_maximum_noise_sharpe(0.01, 0)
