import pytest

from math import log

from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.risk.rg import (
    MultiscaleAnalysisParameters,
    PressureFrame,
    analyze_multiscale_trajectory,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)


def test_block_size_one_preserves_mean_hamiltonian():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    pressure_values = [
        {
            'EUR': 0.2,
            'GBP': -0.1,
            'USD': 0.3,
        },
        {
            'EUR': 0.4,
            'GBP': -0.2,
            'USD': 0.1,
        },
    ]

    frames = [
        PressureFrame(
            event_index=index,
            pressures=pressures,
            h_total=(
                engine.evaluate(
                    pressures
                ).total
            ),
        )
        for index, pressures
        in enumerate(
            pressure_values,
            start=1,
        )
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='run-1',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(1,)
            )
        ),
        hamiltonian_engine=engine,
    )

    scale = result.scales[0]

    assert scale.mean_micro_h_total == (
        pytest.approx(
            scale.mean_coarse_h_total
        )
    )

    assert (
        scale.mean_unresolved_h_total
        == pytest.approx(0.0)
    )


def test_second_moment_decomposition_is_exact():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={'EUR': 1.0},
        ),
        PressureFrame(
            event_index=2,
            pressures={'EUR': 3.0},
        ),
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='run-1',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(2,)
            )
        ),
    )

    eur = result.scales[0].currencies[
        'EUR'
    ]

    assert eur.mean_micro_second_moment == (
        pytest.approx(5.0)
    )

    assert eur.coarse_second_moment == (
        pytest.approx(4.0)
    )

    assert eur.mean_internal_variance == (
        pytest.approx(1.0)
    )

    assert (
        eur.second_moment_decomposition_error
        == pytest.approx(0.0)
    )


def test_alternating_signal_is_removed_by_blocking():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={
                'EUR': value,
            },
        )
        for index, value in enumerate(
            [1.0, -1.0, 1.0, -1.0],
            start=1,
        )
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='alternating',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(1, 2)
            )
        ),
    )

    scale_1, scale_2 = result.scales

    assert (
        scale_1
        .currencies['EUR']
        .coarse_variance
        == pytest.approx(1.0)
    )

    assert (
        scale_2
        .currencies['EUR']
        .coarse_variance
        == pytest.approx(0.0)
    )

    assert (
        scale_2
        .currencies['EUR']
        .mean_internal_variance
        == pytest.approx(1.0)
    )


def test_coarse_stress_fraction_uses_block_field():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={
                'EUR': value,
            },
        )
        for index, value in enumerate(
            [1.0, -1.0, 1.0, -1.0],
            start=1,
        )
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='stress-test',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(1, 2),
                stress_pressure_threshold=0.9,
            )
        ),
    )

    assert (
        result.scales[0]
        .coarse_stress_fraction
        == pytest.approx(1.0)
    )

    assert (
        result.scales[1]
        .coarse_stress_fraction
        == pytest.approx(0.0)
    )


def test_variance_scaling_exponent():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={'EUR': value},
        )
        for index, value in enumerate(
            [3.0, 1.0, -1.0, -3.0],
            start=1,
        )
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='scaling-test',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(1, 2)
            )
        ),
    )

    eur_scaling = next(
        item
        for item in result.variance_scaling
        if item.dimension == 'EUR'
    )

    expected = -log(4.0 / 5.0) / log(2.0)

    assert eur_scaling.exponent == (
        pytest.approx(expected)
    )


def test_trace_covariance_is_sum_of_currency_variances():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={
                'EUR': 1.0,
                'USD': 2.0,
            },
        ),
        PressureFrame(
            event_index=2,
            pressures={
                'EUR': -1.0,
                'USD': -2.0,
            },
        ),
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='run-1',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(1,)
            )
        ),
    )

    scale = result.scales[0]

    expected = sum(
        item.coarse_variance
        for item
        in scale.currencies.values()
    )

    assert scale.trace_coarse_covariance == (
        pytest.approx(expected)
    )


def test_reports_dropped_frames():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={'EUR': float(index)},
        )
        for index in range(1, 6)
    ]

    result = analyze_multiscale_trajectory(
        trajectory_id='run-1',
        frames=frames,
        parameters=(
            MultiscaleAnalysisParameters(
                block_sizes=(2,)
            )
        ),
    )

    scale = result.scales[0]

    assert scale.block_count == 2
    assert scale.frames_used == 4
    assert scale.frames_dropped == 1


def test_rejects_block_size_larger_than_trajectory():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={'EUR': 0.1},
        )
    ]

    with pytest.raises(
        ValueError,
        match='larger than',
    ):
        analyze_multiscale_trajectory(
            trajectory_id='run-1',
            frames=frames,
            parameters=(
                MultiscaleAnalysisParameters(
                    block_sizes=(2,)
                )
            )
        )


def test_rejects_non_finite_stress_threshold():
    with pytest.raises(
        ValueError,
        match='stress_pressure_threshold',
    ):
        MultiscaleAnalysisParameters(
            stress_pressure_threshold=float('nan'),
        )
