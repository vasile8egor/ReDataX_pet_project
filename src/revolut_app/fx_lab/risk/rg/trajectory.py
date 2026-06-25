from collections import defaultdict
from collections.abc import Iterable
from math import isclose, isfinite

from revolut_app.fx_lab.risk.rg.models import (
    PressureFrame,
    PressureObservation,
    TrajectoryExtractionParameters,
)


def extract_pressure_trajectories(
    *,
    observations: Iterable[PressureObservation],
    parameters: TrajectoryExtractionParameters,
) -> dict[str, list[PressureFrame]]:
    grouped: dict[
        str,
        dict[int, list[PressureObservation]],
    ] = defaultdict(
        lambda: defaultdict(list)
    )

    for observation in observations:
        _validate_observation(observation)

        grouped[
            observation.trajectory_id
        ][
            observation.event_index
        ].append(observation)

    trajectories: dict[
        str,
        list[PressureFrame],
    ] = {}

    for trajectory_id, event_groups in grouped.items():
        trajectories[trajectory_id] = (
            _extract_single_trajectory(
                trajectory_id=trajectory_id,
                event_groups=event_groups,
                parameters=parameters,
            )
        )

    return trajectories


def _validate_observation(
    observation: PressureObservation,
) -> None:
    if not observation.trajectory_id:
        raise ValueError(
            "trajectory_id cannot be empty"
        )

    if observation.event_index < 0:
        raise ValueError(
            "event_index cannot be negative"
        )

    if not observation.currency:
        raise ValueError(
            "currency cannot be empty"
        )

    if not isfinite(observation.pressure):
        raise ValueError(
            "pressure must be finite"
        )

    if (
        observation.h_total is not None
        and not isfinite(observation.h_total)
    ):
        raise ValueError(
            "h_total must be finite"
        )


def _extract_single_trajectory(
    *,
    trajectory_id: str,
    event_groups: dict[
        int,
        list[PressureObservation],
    ],
    parameters: TrajectoryExtractionParameters,
) -> list[PressureFrame]:
    event_indices = sorted(event_groups)

    if not parameters.include_initial_frame:
        event_indices = [
            event_index
            for event_index in event_indices
            if event_index != 0
        ]

    if not event_indices:
        return []

    expected_currencies = _resolve_expected_currencies(
        observations=event_groups[event_indices[0]],
        parameters=parameters,
    )

    if parameters.require_contiguous_event_indices:
        _validate_contiguous_indices(
            trajectory_id=trajectory_id,
            event_indices=event_indices,
        )

    frames: list[PressureFrame] = []

    for event_index in event_indices:
        frame = _build_pressure_frame(
            trajectory_id=trajectory_id,
            event_index=event_index,
            observations=event_groups[event_index],
            expected_currencies=expected_currencies,
            hamiltonian_tolerance=(
                parameters.hamiltonian_tolerance
            ),
        )

        frames.append(frame)

    return frames


def _resolve_expected_currencies(
    *,
    observations: list[PressureObservation],
    parameters: TrajectoryExtractionParameters,
) -> tuple[str, ...]:
    if parameters.expected_currencies is not None:
        return parameters.expected_currencies

    currencies = tuple(
        sorted(
            observation.currency
            for observation in observations
        )
    )

    if not currencies:
        raise ValueError(
            "Cannot infer pressure dimensions "
            "from an empty event"
        )

    return currencies


def _validate_contiguous_indices(
    *,
    trajectory_id: str,
    event_indices: list[int],
) -> None:
    for previous, current in zip(
        event_indices,
        event_indices[1:],
    ):
        if current != previous + 1:
            raise ValueError(
                "Trajectory contains missing event indices: "
                f"trajectory_id={trajectory_id}, "
                f"previous={previous}, "
                f"current={current}"
            )


def _build_pressure_frame(
    *,
    trajectory_id: str,
    event_index: int,
    observations: list[PressureObservation],
    expected_currencies: tuple[str, ...],
    hamiltonian_tolerance: float,
) -> PressureFrame:
    observed_currencies = [
        observation.currency
        for observation in observations
    ]

    if len(observed_currencies) != len(
        set(observed_currencies)
    ):
        raise ValueError(
            "Duplicate currency observation: "
            f"trajectory_id={trajectory_id}, "
            f"event_index={event_index}"
        )

    observed_set = set(observed_currencies)
    expected_set = set(expected_currencies)

    if observed_set != expected_set:
        missing = sorted(
            expected_set - observed_set
        )
        unexpected = sorted(
            observed_set - expected_set
        )

        raise ValueError(
            "Pressure dimensions do not match: "
            f"trajectory_id={trajectory_id}, "
            f"event_index={event_index}, "
            f"missing={missing}, "
            f"unexpected={unexpected}"
        )

    pressures = {
        observation.currency:
            observation.pressure
        for observation in observations
    }

    h_total = _resolve_h_total(
        trajectory_id=trajectory_id,
        event_index=event_index,
        observations=observations,
        tolerance=hamiltonian_tolerance,
    )

    return PressureFrame(
        event_index=event_index,
        pressures=pressures,
        h_total=h_total,
    )


def _resolve_h_total(
    *,
    trajectory_id: str,
    event_index: int,
    observations: list[PressureObservation],
    tolerance: float,
) -> float | None:
    h_values = [
        observation.h_total
        for observation in observations
    ]

    has_hamiltonian = [
        value is not None
        for value in h_values
    ]

    if any(has_hamiltonian) and not all(
        has_hamiltonian
    ):
        raise ValueError(
            "Hamiltonian data must be present "
            "for every currency or absent for all: "
            f"trajectory_id={trajectory_id}, "
            f"event_index={event_index}"
        )

    if not any(has_hamiltonian):
        return None

    resolved_values = [
        value
        for value in h_values
        if value is not None
    ]

    reference = resolved_values[0]

    for value in resolved_values[1:]:
        if not isclose(
            reference,
            value,
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            raise ValueError(
                "Inconsistent Hamiltonian values "
                "inside one event: "
                f"trajectory_id={trajectory_id}, "
                f"event_index={event_index}, "
                f"values={resolved_values}"
            )

    return reference
