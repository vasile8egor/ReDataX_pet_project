import pytest

from revolut_app.fx_lab.risk.rg import (
    PressureObservation,
    TrajectoryExtractionParameters,
    extract_pressure_trajectories,
)


EXPECTED_CURRENCIES = (
    "EUR",
    "GBP",
    "USD",
)


def test_extracts_one_frame_from_currency_rows():
    observations = [
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="EUR",
            pressure=0.2,
            h_total=0.5,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="GBP",
            pressure=-0.1,
            h_total=0.5,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="USD",
            pressure=0.3,
            h_total=0.5,
        ),
    ]

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=(
            TrajectoryExtractionParameters(
                expected_currencies=(
                    EXPECTED_CURRENCIES
                )
            )
        ),
    )

    frames = trajectories["run-1"]

    assert len(frames) == 1

    assert frames[0].event_index == 1

    assert frames[0].pressures == {
        "EUR": 0.2,
        "GBP": -0.1,
        "USD": 0.3,
    }

    assert frames[0].h_total == pytest.approx(
        0.5
    )


def test_observations_are_sorted_by_event_index():
    observations = []

    for event_index in (2, 1):
        for currency in EXPECTED_CURRENCIES:
            observations.append(
                PressureObservation(
                    trajectory_id="run-1",
                    event_index=event_index,
                    currency=currency,
                    pressure=float(event_index),
                    h_total=float(event_index),
                )
            )

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=(
            TrajectoryExtractionParameters(
                expected_currencies=(
                    EXPECTED_CURRENCIES
                )
            )
        ),
    )

    assert [
        frame.event_index
        for frame in trajectories["run-1"]
    ] == [1, 2]


def test_initial_frame_is_excluded_by_default():
    observations = []

    for event_index in (0, 1):
        for currency in EXPECTED_CURRENCIES:
            observations.append(
                PressureObservation(
                    trajectory_id="run-1",
                    event_index=event_index,
                    currency=currency,
                    pressure=0.0,
                    h_total=0.0,
                )
            )

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=(
            TrajectoryExtractionParameters(
                expected_currencies=(
                    EXPECTED_CURRENCIES
                )
            )
        ),
    )

    assert [
        frame.event_index
        for frame in trajectories["run-1"]
    ] == [1]


def test_initial_frame_can_be_included():
    observations = []

    for event_index in (0, 1):
        for currency in EXPECTED_CURRENCIES:
            observations.append(
                PressureObservation(
                    trajectory_id="run-1",
                    event_index=event_index,
                    currency=currency,
                    pressure=0.0,
                    h_total=0.0,
                )
            )

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=(
            TrajectoryExtractionParameters(
                expected_currencies=(
                    EXPECTED_CURRENCIES
                ),
                include_initial_frame=True,
            )
        ),
    )

    assert [
        frame.event_index
        for frame in trajectories["run-1"]
    ] == [0, 1]


def test_missing_event_index_is_rejected():
    observations = []

    for event_index in (1, 3):
        for currency in EXPECTED_CURRENCIES:
            observations.append(
                PressureObservation(
                    trajectory_id="run-1",
                    event_index=event_index,
                    currency=currency,
                    pressure=0.1,
                    h_total=0.2,
                )
            )

    with pytest.raises(
        ValueError,
        match="missing event indices",
    ):
        extract_pressure_trajectories(
            observations=observations,
            parameters=(
                TrajectoryExtractionParameters(
                    expected_currencies=(
                        EXPECTED_CURRENCIES
                    )
                )
            ),
        )


def test_missing_currency_is_rejected():
    observations = [
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="EUR",
            pressure=0.1,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="USD",
            pressure=-0.1,
            h_total=0.2,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="Pressure dimensions do not match",
    ):
        extract_pressure_trajectories(
            observations=observations,
            parameters=(
                TrajectoryExtractionParameters(
                    expected_currencies=(
                        EXPECTED_CURRENCIES
                    )
                )
            ),
        )


def test_duplicate_currency_is_rejected():
    observations = [
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="EUR",
            pressure=0.1,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="EUR",
            pressure=0.3,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="GBP",
            pressure=0.0,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="USD",
            pressure=-0.1,
            h_total=0.2,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="Duplicate currency",
    ):
        extract_pressure_trajectories(
            observations=observations,
            parameters=(
                TrajectoryExtractionParameters(
                    expected_currencies=(
                        EXPECTED_CURRENCIES
                    )
                )
            ),
        )


def test_inconsistent_hamiltonian_is_rejected():
    observations = [
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="EUR",
            pressure=0.1,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="GBP",
            pressure=0.0,
            h_total=0.2,
        ),
        PressureObservation(
            trajectory_id="run-1",
            event_index=1,
            currency="USD",
            pressure=-0.1,
            h_total=0.3,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="Inconsistent Hamiltonian",
    ):
        extract_pressure_trajectories(
            observations=observations,
            parameters=(
                TrajectoryExtractionParameters(
                    expected_currencies=(
                        EXPECTED_CURRENCIES
                    )
                )
            ),
        )


def test_multiple_trajectories_are_separated():
    observations = []

    for trajectory_id in (
        "run-1",
        "run-2",
    ):
        for currency in EXPECTED_CURRENCIES:
            observations.append(
                PressureObservation(
                    trajectory_id=trajectory_id,
                    event_index=1,
                    currency=currency,
                    pressure=0.1,
                    h_total=0.2,
                )
            )

    trajectories = extract_pressure_trajectories(
        observations=observations,
        parameters=(
            TrajectoryExtractionParameters(
                expected_currencies=(
                    EXPECTED_CURRENCIES
                )
            )
        ),
    )

    assert set(trajectories) == {
        "run-1",
        "run-2",
    }


def test_hamiltonian_tolerance_must_be_finite():
    with pytest.raises(
        ValueError,
        match="hamiltonian_tolerance",
    ):
        TrajectoryExtractionParameters(
            hamiltonian_tolerance=float("nan"),
        )
