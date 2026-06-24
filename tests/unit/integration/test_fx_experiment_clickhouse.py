import pytest

from revolut_app.loaders.fx_experiment_loader import FXEventDataset


pytestmark = pytest.mark.integration


def test_event_dataset_round_trip(
    clickhouse_loader,
    fx_event_dataset,
):
    records = [
        FXEventDataset(
            event_dataset_id=fx_event_dataset.event_dataset_id,
            event_id=event.event_id,
            event_sequence=event.event_sequence,
            source_step_index=event.source_step_index,
            event_ts=event.events_ts,
            customer_id=event.customer_id,
            base_currency=event.base_currency.value,
            quote_currency=event.quote_currency.value,
            side=event.request.side.value,
            amount=event.request.amount,
            customer_segment=event.request.customer_segment.value,
            channel=event.request.channel
        )
        for event in fx_event_dataset.events
    ]

    inserted = clickhouse_loader.persist_events(records)
    loaded = clickhouse_loader.load_event_dataset(
        event_dataset_id=fx_event_dataset.event_dataset_id
    )

    assert inserted == len(records)
    assert len(loaded) == len(records)

    original_signature = [
        (
            item.event_id,
            item.event_sequence,
            item.source_step_index,
            item.event_ts,
            item.base_currency,
            item.quote_currency,
            item.side,
            item.amount,
            item.customer_segment,
        )
        for item in records
    ]
    loaded_signature = [
        (
            item.event_id,
            item.event_sequence,
            item.source_step_index,
            item.event_ts,
            item.base_currency,
            item.quote_currency,
            item.side,
            item.amount,
            item.customer_segment,
        )
        for item in loaded
    ]
    assert original_signature == loaded_signature


def test_duplicate_event_dataset_is_rejected(clickhouse_loader, event_records):
    clickhouse_loader.persist_events(event_records)

    with pytest.raises(
        ValueError,
        match='already persisted'
    ):
        clickhouse_loader.persist_events(event_records)
