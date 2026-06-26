import pytest

from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.risk.rg import (
    EffectiveHamiltonianObservation,
    PressureObservation,
    TemporalCoarseGrainingParameters,
    TrajectoryExtractionParameters,
    build_effective_hamiltonian_observations,
    coarse_grain_pressure_trajectory,
    extract_pressure_trajectories,
    fit_effective_hamiltonian,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)


CURRENCIES = (
    "EUR",
    "GBP",
    "USD",
)


def test_recovers_exact_effective_coefficients():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    pressure_trajectories = {
        "run-1": (
            {
                "EUR": 0.10,
                "GBP": -0.20,
                "USD": 0.30,
            },
            {
                "EUR": 0.25,
                "GBP": 0.05,
                "USD": -0.35,
            },
            {
                "EUR": -0.15,
                "GBP": 0.40,
                "USD": 0.10,
            },
            {
                "EUR": 0.50,
                "GBP": -0.10,
                "USD": -0.20,
            },
        ),
        "run-2": (
            {
                "EUR": -0.30,
                "GBP": 0.15,
                "USD": 0.25,
            },
            {
                "EUR": 0.45,
                "GBP": 0.20,
                "USD": -0.05,
            },
            {
                "EUR": -0.05,
                "GBP": -0.35,
                "USD": 0.30,
            },
            {
                "EUR": 0.20,
                "GBP": 0.55,
                "USD": -0.25,
            },
        ),
        "run-3": (
            {
                "EUR": 0.35,
                "GBP": -0.25,
                "USD": 0.05,
            },
            {
                "EUR": -0.40,
                "GBP": 0.10,
                "USD": 0.45,
            },
            {
                "EUR": 0.15,
                "GBP": 0.30,
                "USD": -0.50,
            },
            {
                "EUR": -0.25,
                "GBP": -0.45,
                "USD": 0.20,
            },
        ),
    }

    pressure_observations = []

    for trajectory_id, frames in (
        pressure_trajectories.items()
    ):
        for event_index, pressures in enumerate(
            frames,
            start=1,
        ):
            h_total = engine.evaluate(
                pressures
            ).total

            for currency in CURRENCIES:
                pressure_observations.append(
                    PressureObservation(
                        trajectory_id=trajectory_id,
                        event_index=event_index,
                        currency=currency,
                        pressure=pressures[currency],
                        h_total=h_total,
                    )
                )

    trajectories = extract_pressure_trajectories(
        observations=pressure_observations,
        parameters=TrajectoryExtractionParameters(
            expected_currencies=CURRENCIES,
        ),
    )

    observations = []

    for trajectory_id, frames in (
        trajectories.items()
    ):
        blocks = coarse_grain_pressure_trajectory(
            frames=frames,
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=1,
                )
            ),
        )

        observations.extend(
            build_effective_hamiltonian_observations(
                trajectory_id=trajectory_id,
                block_size=1,
                blocks=blocks,
            )
        )

    result = fit_effective_hamiltonian(
        observations=observations
    )

    assert result.intercept == pytest.approx(
        0.0,
        abs=1e-9,
    )
    assert (
        result.quadratic_coefficient
        == pytest.approx(
            2.037037037,
            rel=1e-7,
        )
    )
    assert (
        result.quartic_coefficient
        == pytest.approx(
            2.057613169,
            rel=1e-7,
        )
    )

    assert result.train_rmse < 1e-10
    assert result.cv_rmse < 1e-10
    assert result.train_r_squared == pytest.approx(
        1.0
    )
    assert result.cv_r_squared == pytest.approx(
        1.0,
        abs=1e-10,
    )


def test_rejects_mixed_block_sizes():
    observations = [
        EffectiveHamiltonianObservation(
            trajectory_id="run-1",
            block_size=1,
            quadratic_invariant=0.1,
            quartic_invariant=0.01,
            target_mean_h=0.2,
        ),
        EffectiveHamiltonianObservation(
            trajectory_id="run-2",
            block_size=2,
            quadratic_invariant=0.2,
            quartic_invariant=0.04,
            target_mean_h=0.3,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same block_size",
    ):
        fit_effective_hamiltonian(
            observations=observations
        )
