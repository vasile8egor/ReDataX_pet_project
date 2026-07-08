from datetime import datetime, timezone
from uuid import uuid4

import pytest
from clickhouse_driver.errors import Error as ClickHouseError

from revolut_app.fx_lab.experiments.models import FXEventDataset
from revolut_app.fx_lab.market.event_generation import (
    HawkesLikeFXEventGenerator,
)
from revolut_app.loaders.fx_experiment_loader import (
    EventDatasetRecord,
    FXEventRecord,
    FXExperimentClickHouseLoader,
    SimulationRunRecord,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def clickhouse_loader():
    loader = FXExperimentClickHouseLoader()
    try:
        loader.client.execute('SELECT 1')
    except ClickHouseError as exc:
        pytest.skip(f'ClickHouse is not available: {exc}')
    return loader


@pytest.fixture
def fx_event_dataset():
    generator = HawkesLikeFXEventGenerator(seed=42)
    return generator.simulate_event_dataset(
        steps=200,
        dt_seconds=10,
        base_intensity=0.05,
        alpha=0.08,
        beta=0.12,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        event_dataset_id=uuid4(),
        seed=42,
    )


@pytest.fixture
def event_records(
    fx_event_dataset: FXEventDataset,
):
    return _event_records_from_dataset(fx_event_dataset)


def test_event_dataset_round_trip(
    clickhouse_loader,
    fx_event_dataset,
    event_records,
):
    _, _, _, event_rows = _persist_event_dataset(
        clickhouse_loader,
        fx_event_dataset,
        event_records,
    )
    loaded = clickhouse_loader.load_event_dataset(
        event_dataset_id=fx_event_dataset.event_dataset_id
    )

    assert event_rows == len(event_records)
    assert len(loaded) == len(event_records)

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
        for item in event_records
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


def test_duplicate_event_dataset_is_rejected(
    clickhouse_loader,
    fx_event_dataset,
    event_records,
):
    _persist_event_dataset(
        clickhouse_loader,
        fx_event_dataset,
        event_records,
    )

    with pytest.raises(
        ValueError,
        match='already has persisted rows',
    ):
        _persist_event_dataset(
            clickhouse_loader,
            fx_event_dataset,
            event_records,
        )


def _persist_event_dataset(
    loader: FXExperimentClickHouseLoader,
    event_dataset: FXEventDataset,
    event_records: list[FXEventRecord],
):
    comparison_id = uuid4()
    return loader.load_comparison(
        event_dataset=EventDatasetRecord(
            event_dataset_id=event_dataset.event_dataset_id,
            comparison_id=comparison_id,
            generator=event_dataset.generator,
            seed=event_dataset.seed,
            steps=event_dataset.source_steps,
            dt_seconds=event_dataset.dt_seconds,
            base_intensity=event_dataset.base_intensity,
            alpha=event_dataset.alpha,
            beta=event_dataset.beta,
            amount_multiplier=1.0,
            generated_requests=len(event_dataset.events),
            created_at=event_dataset.started_at,
        ),
        runs=[
            SimulationRunRecord(
                run_id=uuid4(),
                comparison_id=comparison_id,
                event_dataset_id=event_dataset.event_dataset_id,
                model_version='test',
                physics_mode='none',
                pricing_policy='naive',
                hedging_policy='none',
                seed=event_dataset.seed,
                steps=event_dataset.source_steps,
                dt_seconds=event_dataset.dt_seconds,
                base_intensity=event_dataset.base_intensity,
                alpha=event_dataset.alpha,
                beta=event_dataset.beta,
                amount_multiplier=1.0,
                generated_requests=len(event_dataset.events),
                accepted_events=0,
                rejected_events=len(event_dataset.events),
                acceptance_rate=0.0,
                average_quoted_spread_bps=0.0,
                average_accepted_spread_bps=0.0,
                customer_spread_cost_usd=0.0,
                spread_revenue_usd=0.0,
                allocated_product_revenue_usd=0.0,
                hedge_cost_usd=0.0,
                funding_cost_usd=0.0,
                net_pnl_usd=0.0,
                final_regime='calm',
                max_abs_pressure=0.0,
                stress_time_fraction=0.0,
                final_inventory_pressure_json='{}',
                parameters_json='{}',
                started_at=event_dataset.started_at,
                finished_at=event_dataset.finished_at,
            )
        ],
        snapshots=[],
        events=event_records,
        persist_event_dataset=True,
    )


def _event_records_from_dataset(
    event_dataset: FXEventDataset,
):
    return [
        FXEventRecord(
            event_dataset_id=event_dataset.event_dataset_id,
            event_id=event.event_id,
            event_sequence=event.event_sequence,
            source_step_index=event.source_step_index,
            event_ts=event.event_ts,
            customer_id=event.request.customer_id,
            base_currency=event.request.base_currency.value,
            quote_currency=event.request.quote_currency.value,
            side=event.request.side.value,
            amount=event.request.amount,
            customer_segment=event.request.segment.value,
            channel=event.request.channel,
            generator=event_dataset.generator,
            seed=event_dataset.seed,
            source_steps=event_dataset.source_steps,
            dt_seconds=event_dataset.dt_seconds,
            base_intensity=event_dataset.base_intensity,
            alpha=event_dataset.alpha,
            beta=event_dataset.beta,
        )
        for event in event_dataset.events
    ]
