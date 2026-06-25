import pytest

from revolut_app.fx_lab.risk.rg import (
    EffectiveHamiltonianCoefficients,
    EffectiveHamiltonianEvaluator,
    RollingPressureWindow,
    ScaleAwareTransitionEvaluator,
)


def test_rolling_window_calculates_exact_mean():
    window = RollingPressureWindow(
        currencies=("EUR", "USD"),
        block_size=2,
    )

    window.append(
        {
            "EUR": 1.0,
            "USD": 2.0,
        }
    )

    window.append(
        {
            "EUR": 3.0,
            "USD": 4.0,
        }
    )

    assert window.mean_pressures() == (
        pytest.approx(
            {
                "EUR": 2.0,
                "USD": 3.0,
            }
        )
    )


def test_projected_mean_replaces_oldest_frame():
    window = RollingPressureWindow(
        currencies=("EUR",),
        block_size=2,
    )

    window.append({"EUR": 1.0})
    window.append({"EUR": 3.0})

    projected = window.projected_next_mean(
        projected_pressures={
            "EUR": 5.0,
        }
    )

    assert projected["EUR"] == (
        pytest.approx(4.0)
    )


def test_projection_does_not_commit_state():
    window = RollingPressureWindow(
        currencies=("EUR",),
        block_size=2,
    )

    window.append({"EUR": 1.0})
    window.append({"EUR": 3.0})

    before = window.mean_pressures()

    window.projected_next_mean(
        projected_pressures={
            "EUR": 10.0,
        }
    )

    after = window.mean_pressures()

    assert after == before


def test_normalized_delta_is_block_size_times_delta():
    coefficients = (
        EffectiveHamiltonianCoefficients(
            block_size=2,
            intercept=0.0,
            quadratic=1.0,
            quartic=0.0,
        )
    )

    window = RollingPressureWindow(
        currencies=("EUR",),
        block_size=2,
    )

    window.append({"EUR": 1.0})
    window.append({"EUR": 3.0})

    evaluator = (
        ScaleAwareTransitionEvaluator(
            pressure_window=window,
            hamiltonian=(
                EffectiveHamiltonianEvaluator(
                    coefficients=coefficients
                )
            ),
        )
    )

    result = (
        evaluator
        .evaluate_projected_transition(
            current_pressures={
                "EUR": 3.0,
            },
            projected_pressures={
                "EUR": 5.0,
            }
        )
    )

    assert result.temporal_drift_delta_h == (
        pytest.approx(5.0)
    )
    assert result.request_delta_h == (
        pytest.approx(7.0)
    )
    assert result.total_accepted_delta_h == (
        pytest.approx(12.0)
    )

    assert (
        result.normalized_total_accepted_delta_h
        == pytest.approx(24.0)
    )


def test_block_size_one_matches_local_transition():
    coefficients = (
        EffectiveHamiltonianCoefficients(
            block_size=1,
            intercept=0.7,
            quadratic=2.0,
            quartic=3.0,
        )
    )

    window = RollingPressureWindow(
        currencies=("EUR",),
        block_size=1,
    )

    window.append({"EUR": 0.2})

    evaluator = (
        ScaleAwareTransitionEvaluator(
            pressure_window=window,
            hamiltonian=(
                EffectiveHamiltonianEvaluator(
                    coefficients=coefficients
                )
            ),
        )
    )

    result = (
        evaluator
        .evaluate_projected_transition(
            current_pressures={
                "EUR": 0.2,
            },
            projected_pressures={
                "EUR": 0.4,
            }
        )
    )

    expected = (
        2.0 * (0.4**2 - 0.2**2)
        + 3.0 * (0.4**4 - 0.2**4)
    )

    assert result.request_delta_h == (
        pytest.approx(expected)
    )

    assert (
        result.normalized_request_delta_h
        == pytest.approx(expected)
    )


def test_transition_is_not_ready_before_full_history():
    coefficients = (
        EffectiveHamiltonianCoefficients(
            block_size=4,
            intercept=0.0,
            quadratic=1.0,
            quartic=1.0,
        )
    )

    window = RollingPressureWindow(
        currencies=("EUR",),
        block_size=4,
    )

    window.append({"EUR": 0.1})

    evaluator = (
        ScaleAwareTransitionEvaluator(
            pressure_window=window,
            hamiltonian=(
                EffectiveHamiltonianEvaluator(
                    coefficients=coefficients
                )
            ),
        )
    )

    result = (
        evaluator
        .evaluate_projected_transition(
            current_pressures={
                "EUR": 0.1,
            },
            projected_pressures={
                "EUR": 0.2,
            }
        )
    )

    assert result.history_ready is False
    assert result.normalized_request_delta_h == 0.0


def test_effective_hamiltonian_rejects_non_finite_coefficients():
    with pytest.raises(
        ValueError,
        match="coefficient must be finite",
    ):
        EffectiveHamiltonianCoefficients(
            block_size=1,
            intercept=0.0,
            quadratic=float("nan"),
            quartic=1.0,
        )
