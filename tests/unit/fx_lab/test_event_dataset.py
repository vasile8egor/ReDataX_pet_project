from datetime import datetime, timedelta
from uuid import UUID

from revolut_app.fx_lab.market.event_generation import HawkesLikeFXEventGenerator


def test_same_seed_and_dataset_id_produce_same_dataset(
    fixed_dataset_id: UUID,
    fixed_start_at: datetime,
):
    first = HawkesLikeFXEventGenerator(
        seed=42,
    ).simulate_event_dataset(
        steps=2000,
        dt_seconds=10,
        base_intensity=0.03,
        alpha=0.08,
        beta=0.12,
        start_at=fixed_start_at,
        event_dataset_id=fixed_dataset_id,
        seed=42,
    )
    second = HawkesLikeFXEventGenerator(
        seed=42,
    ).simulate_event_dataset(
        steps=2000,
        dt_seconds=10,
        base_intensity=0.03,
        alpha=0.08,
        beta=0.12,
        start_at=fixed_start_at,
        event_dataset_id=fixed_dataset_id,
        seed=42,
    )
    assert first == second


def test_different_seed_changes_event_stream(
    fixed_dataset_id: UUID,
    fixed_start_at: datetime,
):
    first = HawkesLikeFXEventGenerator(
        seed=42
    ).simulate_event_dataset(
        steps=2000,
        dt_seconds=10,
        base_intensity=0.03,
        alpha=0.08,
        beta=0.12,
        start_at=fixed_start_at,
        event_dataset_id=fixed_dataset_id,
        seed=42,
    )
    second = HawkesLikeFXEventGenerator(
        seed=40
    ).simulate_event_dataset(
        steps=2000,
        dt_seconds=10,
        base_intensity=0.03,
        alpha=0.08,
        beta=0.12,
        start_at=fixed_start_at,
        event_dataset_id=fixed_dataset_id,
        seed=40,
    )

    first_sign = [
        (
            event.source_step_index,
            event.request.base_currency,
            event.request.quote_currency,
            event.request.side,
            event.request.amount,
            event.request.segment,
        )
        for event in first.events
    ]
    second_sign = [
        (
            event.source_step_index,
            event.request.base_currency,
            event.request.quote_currency,
            event.request.side,
            event.request.amount,
            event.request.segment,
        )
        for event in second.events
    ]

    assert first_sign != second_sign


def test_event_timestamps_match_source_steps(
    fx_event_dataset,
):
    for event in fx_event_dataset.events:
        expected_timestamp = (
            fx_event_dataset.started_at
            + timedelta(
                seconds=(event.source_step_index * fx_event_dataset.dt_seconds)
            )
        )
        assert event.event_ts == expected_timestamp


def test_event_sequence_is_contiguous(fx_event_dataset):
    event_seq = [event.event_sequence for event in fx_event_dataset.events]
    expected_event_seq = list(range(1, len(fx_event_dataset.events) + 1))
    assert event_seq == expected_event_seq
