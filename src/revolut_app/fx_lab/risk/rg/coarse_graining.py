from collections.abc import Iterable
from math import isfinite

from revolut_app.fx_lab.risk.rg.models import (
    CoarsePressureBlock,
    PressureFrame,
    TemporalCoarseGrainingParameters,
)


def coarse_grain_pressure_trajectory(
    frames: Iterable[PressureFrame],
    parameters: TemporalCoarseGrainingParameters,
):
    resolved_frames = list(frames)

    if not resolved_frames:
        return []

    _validate_frames(resolved_frames)

    blocks: list[CoarsePressureBlock] = []
    block_size = parameters.block_size

    for start_offset in range(0, len(resolved_frames), block_size):
        chunk = resolved_frames[start_offset: start_offset + block_size]
        if (
            len(chunk) < block_size
            and parameters.drop_incomplete_block
        ):
            break
        blocks.append(
            _build_coarse_block(
                block_index=len(blocks),
                frames=chunk
            )
        )
    return blocks


def _build_coarse_block(
    *,
    block_index: int,
    frames: list[PressureFrame],
):
    event_count = len(frames)

    pressure_keys = tuple(
        frames[0].pressures.keys()
    )

    mean_pressures: dict[str, float] = {}
    second_moments: dict[str, float] = {}
    fourth_moments: dict[str, float] = {}
    variances: dict[str, float] = {}

    for key in pressure_keys:
        values = [
            frame.pressures[key]
            for frame in frames
        ]

        mean_value = (
            sum(values) / event_count
        )

        second_moment = (
            sum(value**2 for value in values)
            / event_count
        )

        fourth_moment = (
            sum(value**4 for value in values)
            / event_count
        )

        variance = max(
            0.0,
            second_moment - mean_value**2,
        )

        mean_pressures[key] = mean_value
        second_moments[key] = second_moment
        fourth_moments[key] = fourth_moment
        variances[key] = variance

    if frames[0].h_total is None:
        mean_h_total = None
    else:
        mean_h_total = (
            sum(
                frame.h_total
                for frame in frames
                if frame.h_total is not None
            )
            / event_count
        )

    return CoarsePressureBlock(
        block_index=block_index,
        start_event_index=frames[0].event_index,
        end_event_index=frames[-1].event_index,
        event_count=event_count,
        mean_pressures=mean_pressures,
        second_moments=second_moments,
        fourth_moments=fourth_moments,
        variances=variances,
        mean_h_total=mean_h_total,
    )


def _validate_frames(frames: list[PressureFrame]):
    expected_keys = set(frames[0].pressures)

    if not expected_keys:
        raise ValueError(
            'Pressure frames must contain '
            'at least one pressure dimension'
        )

    previous_event_index: int | None = None

    h_presence = {
        frame.h_total is not None
        for frame in frames
    }

    if len(h_presence) > 1:
        raise ValueError(
            'h_total must be present for all frames '
            'or absent for all frames'
        )

    for frame in frames:
        actual_keys = set(frame.pressures)

        if actual_keys != expected_keys:
            raise ValueError(
                'All pressure frames must contain '
                'the same pressure dimensions'
            )

        if (
            previous_event_index is not None
            and frame.event_index
            <= previous_event_index
        ):
            raise ValueError(
                'Pressure frames must be ordered '
                'by strictly increasing event_index'
            )

        previous_event_index = frame.event_index

        for currency, value in frame.pressures.items():
            if not isfinite(value):
                raise ValueError(
                    'Pressure must be finite: '
                    f'''currency={currency}, value={value}'''
                )

        if (
            frame.h_total is not None
            and not isfinite(frame.h_total)
        ):
            raise ValueError(
                'h_total must be finite'
            )
