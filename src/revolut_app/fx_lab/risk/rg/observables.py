from __future__ import annotations

from math import log
from statistics import fmean

from revolut_app.fx_lab.risk.hamiltonian.engine import (
    HamiltonianEngine,
)
from revolut_app.fx_lab.risk.rg.coarse_graining import (
    coarse_grain_pressure_trajectory,
)
from revolut_app.fx_lab.risk.rg.models import (
    CoarsePressureBlock,
    CurrencyScaleObservables,
    MultiscaleAnalysisParameters,
    MultiscaleTrajectoryObservables,
    PressureFrame,
    ScaleObservables,
    TemporalCoarseGrainingParameters,
    VarianceScalingExponent,
)


TRACE_DIMENSION = '__trace__'


def analyze_multiscale_trajectory(
    *,
    trajectory_id: str,
    frames: list[PressureFrame],
    parameters: MultiscaleAnalysisParameters,
    hamiltonian_engine: HamiltonianEngine | None = None,
):
    if not trajectory_id:
        raise ValueError(
            'trajectory_id cannot be empty'
        )

    if not frames:
        raise ValueError(
            'frames cannot be empty'
        )

    scale_results: list[ScaleObservables] = []

    for block_size in parameters.block_sizes:
        blocks = coarse_grain_pressure_trajectory(
            frames=frames,
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=block_size,
                    drop_incomplete_block=True,
                )
            ),
        )

        if not blocks:
            raise ValueError(
                'Block size is larger than '
                'the available trajectory: '
                f'block_size={block_size}, '
                f'frame_count={len(frames)}'
            )

        scale_results.append(
            _calculate_scale_observables(
                blocks=blocks,
                frame_count=len(frames),
                block_size=block_size,
                stress_pressure_threshold=(
                    parameters
                    .stress_pressure_threshold
                ),
                hamiltonian_engine=(
                    hamiltonian_engine
                ),
            )
        )

    variance_scaling = (
        _calculate_variance_scaling(
            scales=scale_results
        )
    )

    return MultiscaleTrajectoryObservables(
        trajectory_id=trajectory_id,
        frame_count=len(frames),
        scales=tuple(scale_results),
        variance_scaling=tuple(
            variance_scaling
        ),
    )


def _calculate_scale_observables(
    *,
    blocks: list[CoarsePressureBlock],
    frame_count: int,
    block_size: int,
    stress_pressure_threshold: float,
    hamiltonian_engine: HamiltonianEngine | None,
):
    currencies = tuple(
        sorted(blocks[0].mean_pressures)
    )

    currency_results: dict[
        str,
        CurrencyScaleObservables,
    ] = {}

    for currency in currencies:
        coarse_values = [
            block.mean_pressures[currency]
            for block in blocks
        ]

        mean_coarse_pressure = fmean(
            coarse_values
        )

        coarse_second_moment = fmean(
            value**2
            for value in coarse_values
        )

        coarse_fourth_moment = fmean(
            value**4
            for value in coarse_values
        )

        coarse_variance = max(
            0.0,
            coarse_second_moment
            - mean_coarse_pressure**2,
        )

        mean_micro_second_moment = fmean(
            block.second_moments[currency]
            for block in blocks
        )

        mean_internal_variance = fmean(
            block.variances[currency]
            for block in blocks
        )

        decomposition_error = (
            mean_micro_second_moment
            - coarse_second_moment
            - mean_internal_variance
        )

        currency_results[currency] = (
            CurrencyScaleObservables(
                currency=currency,
                mean_coarse_pressure=(
                    mean_coarse_pressure
                ),
                coarse_second_moment=(
                    coarse_second_moment
                ),
                coarse_fourth_moment=(
                    coarse_fourth_moment
                ),
                coarse_variance=(
                    coarse_variance
                ),
                mean_micro_second_moment=(
                    mean_micro_second_moment
                ),
                mean_internal_variance=(
                    mean_internal_variance
                ),
                second_moment_decomposition_error=(
                    decomposition_error
                ),
            )
        )

    trace_coarse_covariance = sum(
        observable.coarse_variance
        for observable
        in currency_results.values()
    )

    mean_coarse_norm_squared = fmean(
        sum(
            value**2
            for value
            in block.mean_pressures.values()
        )
        for block in blocks
    )

    mean_internal_variance_total = fmean(
        sum(block.variances.values())
        for block in blocks
    )

    max_abs_coarse_pressures = [
        max(
            abs(value)
            for value
            in block.mean_pressures.values()
        )
        for block in blocks
    ]

    mean_max_abs_coarse_pressure = fmean(
        max_abs_coarse_pressures
    )

    coarse_stress_fraction = (
        sum(
            value
            >= stress_pressure_threshold
            for value
            in max_abs_coarse_pressures
        )
        / len(max_abs_coarse_pressures)
    )

    mean_micro_h_total = _mean_micro_h(
        blocks
    )

    mean_coarse_h_total = _mean_coarse_h(
        blocks=blocks,
        hamiltonian_engine=(
            hamiltonian_engine
        ),
    )

    if (
        mean_micro_h_total is not None
        and mean_coarse_h_total is not None
    ):
        mean_unresolved_h_total = (
            mean_micro_h_total
            - mean_coarse_h_total
        )
    else:
        mean_unresolved_h_total = None

    frames_used = len(blocks) * block_size

    return ScaleObservables(
        block_size=block_size,
        block_count=len(blocks),
        frames_used=frames_used,
        frames_dropped=(
            frame_count - frames_used
        ),
        currencies=currency_results,
        trace_coarse_covariance=(
            trace_coarse_covariance
        ),
        mean_coarse_norm_squared=(
            mean_coarse_norm_squared
        ),
        mean_internal_variance_total=(
            mean_internal_variance_total
        ),
        mean_max_abs_coarse_pressure=(
            mean_max_abs_coarse_pressure
        ),
        coarse_stress_fraction=(
            coarse_stress_fraction
        ),
        mean_micro_h_total=(
            mean_micro_h_total
        ),
        mean_coarse_h_total=(
            mean_coarse_h_total
        ),
        mean_unresolved_h_total=(
            mean_unresolved_h_total
        ),
    )


def _mean_micro_h(
    blocks: list[CoarsePressureBlock],
):
    values = [
        block.mean_h_total
        for block in blocks
    ]

    if all(
        value is None
        for value in values
    ):
        return None

    if any(
        value is None
        for value in values
    ):
        raise ValueError(
            'Hamiltonian data must be present '
            'for every coarse block or absent for all'
        )

    return fmean(
        value
        for value in values
        if value is not None
    )


def _mean_coarse_h(
    *,
    blocks: list[CoarsePressureBlock],
    hamiltonian_engine: HamiltonianEngine | None,
):
    if hamiltonian_engine is None:
        return None

    return fmean(
        hamiltonian_engine.evaluate(
            block.mean_pressures
        ).total
        for block in blocks
    )


def _calculate_variance_scaling(
    *,
    scales: list[ScaleObservables],
):
    results: list[
        VarianceScalingExponent
    ] = []

    dimensions = [
        TRACE_DIMENSION,
        *sorted(scales[0].currencies),
    ]

    for previous, current in zip(
        scales,
        scales[1:],
    ):
        for dimension in dimensions:
            variance_from = _variance_for_dimension(
                scale=previous,
                dimension=dimension,
            )

            variance_to = _variance_for_dimension(
                scale=current,
                dimension=dimension,
            )

            if (
                variance_from <= 0.0
                or variance_to <= 0.0
            ):
                exponent = None
            else:
                exponent = -log(
                    variance_to / variance_from
                ) / log(
                    current.block_size
                    / previous.block_size
                )

            results.append(
                VarianceScalingExponent(
                    dimension=dimension,
                    from_block_size=(
                        previous.block_size
                    ),
                    to_block_size=(
                        current.block_size
                    ),
                    variance_from=variance_from,
                    variance_to=variance_to,
                    exponent=exponent,
                )
            )

    return results


def _variance_for_dimension(
    *,
    scale: ScaleObservables,
    dimension: str,
):
    if dimension == TRACE_DIMENSION:
        return scale.trace_coarse_covariance

    return (
        scale
        .currencies[dimension]
        .coarse_variance
    )
