import pytest

from revolut_app.fx_lab.risk.rg import (
    PressureFrame,
    TemporalCoarseGrainingParameters,
    coarse_grain_pressure_trajectory,
)


def test_block_size_one_preserves_pressure_values():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={
                "EUR": 0.2,
                "GBP": -0.1,
                "USD": 0.4,
            },
            h_total=0.5,
        ),
        PressureFrame(
            event_index=2,
            pressures={
                "EUR": 0.3,
                "GBP": -0.2,
                "USD": 0.5,
            },
            h_total=0.7,
        ),
    ]

    blocks = coarse_grain_pressure_trajectory(
        frames=frames,
        parameters=(
            TemporalCoarseGrainingParameters(
                block_size=1
            )
        ),
    )

    assert len(blocks) == 2

    assert blocks[0].mean_pressures == (
        frames[0].pressures
    )

    assert blocks[0].mean_h_total == pytest.approx(
        0.5
    )

    assert all(
        value == pytest.approx(0.0)
        for value in blocks[0].variances.values()
    )


def test_coarse_block_calculates_exact_moments():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={"EUR": 1.0},
            h_total=2.0,
        ),
        PressureFrame(
            event_index=2,
            pressures={"EUR": 3.0},
            h_total=4.0,
        ),
    ]

    blocks = coarse_grain_pressure_trajectory(
        frames=frames,
        parameters=(
            TemporalCoarseGrainingParameters(
                block_size=2
            )
        ),
    )

    block = blocks[0]

    assert block.mean_pressures["EUR"] == pytest.approx(
        2.0
    )

    assert block.second_moments["EUR"] == pytest.approx(
        5.0
    )

    assert block.fourth_moments["EUR"] == pytest.approx(
        41.0
    )

    assert block.variances["EUR"] == pytest.approx(
        1.0
    )

    assert block.mean_h_total == pytest.approx(
        3.0
    )


def test_incomplete_block_is_dropped_by_default():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={"EUR": float(index)},
        )
        for index in range(1, 6)
    ]

    blocks = coarse_grain_pressure_trajectory(
        frames=frames,
        parameters=(
            TemporalCoarseGrainingParameters(
                block_size=2
            )
        ),
    )

    assert len(blocks) == 2
    assert blocks[0].event_count == 2
    assert blocks[1].event_count == 2


def test_incomplete_block_can_be_preserved():
    frames = [
        PressureFrame(
            event_index=index,
            pressures={"EUR": float(index)},
        )
        for index in range(1, 6)
    ]

    blocks = coarse_grain_pressure_trajectory(
        frames=frames,
        parameters=(
            TemporalCoarseGrainingParameters(
                block_size=2,
                drop_incomplete_block=False,
            )
        ),
    )

    assert len(blocks) == 3
    assert blocks[-1].event_count == 1
    assert (
        blocks[-1].mean_pressures["EUR"]
        == pytest.approx(5.0)
    )


def test_pressure_dimensions_must_match():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={
                "EUR": 0.1,
                "USD": 0.2,
            },
        ),
        PressureFrame(
            event_index=2,
            pressures={
                "EUR": 0.2,
                "GBP": 0.3,
            },
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same pressure dimensions",
    ):
        coarse_grain_pressure_trajectory(
            frames=frames,
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=2
                )
            ),
        )


def test_event_indices_must_be_strictly_increasing():
    frames = [
        PressureFrame(
            event_index=2,
            pressures={"EUR": 0.1},
        ),
        PressureFrame(
            event_index=1,
            pressures={"EUR": 0.2},
        ),
    ]

    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        coarse_grain_pressure_trajectory(
            frames=frames,
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=2
                )
            ),
        )


def test_partial_hamiltonian_data_is_rejected():
    frames = [
        PressureFrame(
            event_index=1,
            pressures={"EUR": 0.1},
            h_total=0.2,
        ),
        PressureFrame(
            event_index=2,
            pressures={"EUR": 0.2},
            h_total=None,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="present for all frames",
    ):
        coarse_grain_pressure_trajectory(
            frames=frames,
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=2
                )
            ),
        )


def test_empty_pressure_dimensions_are_rejected():
    with pytest.raises(
        ValueError,
        match="at least one pressure dimension",
    ):
        coarse_grain_pressure_trajectory(
            frames=[
                PressureFrame(
                    event_index=1,
                    pressures={},
                ),
            ],
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=1
                )
            ),
        )


def test_non_finite_pressure_is_rejected():
    with pytest.raises(
        ValueError,
        match="Pressure must be finite",
    ):
        coarse_grain_pressure_trajectory(
            frames=[
                PressureFrame(
                    event_index=1,
                    pressures={"EUR": float("nan")},
                ),
            ],
            parameters=(
                TemporalCoarseGrainingParameters(
                    block_size=1
                )
            ),
        )


def test_block_size_must_be_positive():
    with pytest.raises(
        ValueError,
        match="block_size must be positive",
    ):
        TemporalCoarseGrainingParameters(
            block_size=0
        )
