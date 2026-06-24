from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from clickhouse_driver import Client
from revolut_app.fx_lab.shared.constants import (
    CLICKHOUSE_SNAPSHOT_INSERT_BATCH_SIZE,
    ZERO_INT,
)

from .queries import (
    ALTER_DIM_EVENT_DATASET_Q,
    ALTER_INVENTORY_SNAPSHOTS_Q,
    DIM_EVENT_DATASET_Q,
    FACT_INVENTORY_SNAPSHOTS_Q,
    FACT_SIMULATION_RUNS_Q,
    FACT_FX_EVENTS_Q,
    FX_POLICY_RUN_SUMMARY_VIEW_Q,
    FX_INVENTORY_TRAJECTORY_VIEW_Q,
    FX_REGIME_DISTRIBUTION_VIEW_Q,
    FX_HAMILTONIAN_STATE_VIEW_Q,
    INSERT_INTO_DIM_EVENT_Q,
    INSERT_INTO_FACT_SIM_Q,
    INSERT_INTO_FACT_FX_EVENTS_Q,
    INSERT_INTO_FACT_INVENTORY_SNAPSHOTS_Q,
    SELECT_ALL_FX_EVENTS_Q,
    SELECT_EXISTING_COMPARISON_Q,
    SELECT_EXISTING_EVENT_DATASET_Q,
)


@dataclass(frozen=True)
class EventDatasetRecord:
    event_dataset_id: UUID
    comparison_id: UUID

    generator: str
    seed: int | None

    steps: int
    dt_seconds: int
    base_intensity: float
    alpha: float
    beta: float
    amount_multiplier: float

    generated_requests: int
    created_at: datetime


@dataclass(frozen=True)
class SimulationRunRecord:
    run_id: UUID
    comparison_id: UUID
    event_dataset_id: UUID

    model_version: str
    physics_mode: str
    pricing_policy: str
    hedging_policy: str

    seed: int | None

    steps: int
    dt_seconds: int
    base_intensity: float
    alpha: float
    beta: float
    amount_multiplier: float

    generated_requests: int
    accepted_events: int
    rejected_events: int
    acceptance_rate: float

    average_quoted_spread_bps: float
    average_accepted_spread_bps: float
    customer_spread_cost_usd: float

    spread_revenue_usd: float
    allocated_product_revenue_usd: float
    hedge_cost_usd: float
    funding_cost_usd: float
    net_pnl_usd: float

    final_regime: str
    max_abs_pressure: float
    stress_time_fraction: float

    final_inventory_pressure_json: str
    parameters_json: str

    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True)
class FXEventRecord:
    event_dataset_id: UUID
    event_id: UUID

    event_sequence: int
    source_step_index: int
    event_ts: datetime

    customer_id: str

    base_currency: str
    quote_currency: str
    side: str

    amount: float

    customer_segment: str
    channel: str

    generator: str
    seed: int | None
    source_steps: int
    dt_seconds: int
    base_intensity: float
    alpha: float
    beta: float


class FXExperimentClickHouseLoader:
    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.client = Client(
            host=host or os.getenv("CLICKHOUSE_HOST", "clickhouse"),
            port=port or int(os.getenv("CLICKHOUSE_PORT", "9000")),
            user=user or os.getenv("CLICKHOUSE_USER", "default"),
            password=(
                password
                if password is not None
                else os.getenv("CLICKHOUSE_PASSWORD", "default")
            ),
            database=os.getenv("CLICKHOUSE_DATABASE", "gold"),
        )

    def ensure_schema(self) -> None:
        self.client.execute(
            '''create database if not exists gold'''
        )
        self.client.execute(DIM_EVENT_DATASET_Q)
        self.client.execute(ALTER_DIM_EVENT_DATASET_Q)
        self.client.execute(FACT_SIMULATION_RUNS_Q)
        self.client.execute(FACT_INVENTORY_SNAPSHOTS_Q)
        self.client.execute(ALTER_INVENTORY_SNAPSHOTS_Q)
        self.client.execute(FACT_FX_EVENTS_Q)
        self.client.execute(FX_POLICY_RUN_SUMMARY_VIEW_Q)
        self.client.execute(FX_INVENTORY_TRAJECTORY_VIEW_Q)
        self.client.execute(FX_REGIME_DISTRIBUTION_VIEW_Q)
        self.client.execute(FX_HAMILTONIAN_STATE_VIEW_Q)

    @staticmethod
    def _chunks(
        rows: list[tuple],
        *,
        size: int,
    ) -> Iterator[list[tuple]]:
        if size <= ZERO_INT:
            raise ValueError('Chunk size must be positive')

        for start in range(0, len(rows), size):
            yield rows[start: start + size]

    def _ensure_event_dataset_not_persisted(
        self,
        event_dataset_id: UUID,
    ) -> None:
        dataset_rows, event_rows = self.client.execute(
            SELECT_EXISTING_EVENT_DATASET_Q,
            {'event_dataset_id': event_dataset_id},
        )[0]

        if dataset_rows or event_rows:
            raise ValueError(
                'Event dataset already has persisted rows for '
                f'event_dataset_id={event_dataset_id}: '
                f'datasets={dataset_rows}, events={event_rows}'
            )

    def _ensure_comparison_not_persisted(
        self,
        comparison_id: UUID,
    ) -> None:
        run_rows, snapshot_rows = self.client.execute(
            SELECT_EXISTING_COMPARISON_Q,
            {'comparison_id': comparison_id},
        )[0]

        if run_rows or snapshot_rows:
            raise ValueError(
                'Comparison already has persisted rows for '
                f'comparison_id={comparison_id}: '
                f'runs={run_rows}, snapshots={snapshot_rows}'
            )

    def load_comparison(
        self, *,
        event_dataset: EventDatasetRecord,
        runs: list[SimulationRunRecord],
        snapshots: list[InventorySnapshotRecord],
        events: list[FXEventRecord],
        persist_event_dataset: bool,
    ) -> tuple[int, int, int, int]:
        if not runs:
            raise ValueError(
                'At least one simulation run is required'
            )

        self.ensure_schema()
        self._ensure_comparison_not_persisted(
            event_dataset.comparison_id,
        )
        if persist_event_dataset:
            self._ensure_event_dataset_not_persisted(
                event_dataset.event_dataset_id,
            )

        dataset_rows = [
            (
                event_dataset.event_dataset_id,
                event_dataset.comparison_id,
                event_dataset.generator,
                event_dataset.seed,
                event_dataset.steps,
                event_dataset.dt_seconds,
                event_dataset.base_intensity,
                event_dataset.alpha,
                event_dataset.beta,
                event_dataset.amount_multiplier,
                event_dataset.generated_requests,
                event_dataset.created_at,
            )
        ]
        run_rows = [
            (
                run.run_id,
                run.comparison_id,
                run.event_dataset_id,
                run.model_version,
                run.physics_mode,
                run.pricing_policy,
                run.hedging_policy,
                run.seed,
                run.steps,
                run.dt_seconds,
                run.base_intensity,
                run.alpha,
                run.beta,
                run.amount_multiplier,
                run.generated_requests,
                run.accepted_events,
                run.rejected_events,
                run.acceptance_rate,
                run.average_quoted_spread_bps,
                run.average_accepted_spread_bps,
                run.customer_spread_cost_usd,
                run.spread_revenue_usd,
                run.allocated_product_revenue_usd,
                run.hedge_cost_usd,
                run.funding_cost_usd,
                run.net_pnl_usd,
                run.final_regime,
                run.max_abs_pressure,
                run.stress_time_fraction,
                run.final_inventory_pressure_json,
                run.parameters_json,
                run.started_at,
                run.finished_at,
            )
            for run in runs
        ]
        snapshot_rows = [
            (
                item.run_id,
                item.comparison_id,
                item.event_dataset_id,
                item.model_version,
                item.physics_mode,
                item.pricing_policy,
                item.event_index,
                item.source_event_id,
                item.source_step_index,
                item.snapshot_ts,
                item.currency,
                item.position,
                item.position_limit,
                item.limit_utilization,
                item.position_pressure,
                item.order_flow_buy_ewma,
                item.order_flow_sell_ewma,
                item.order_flow_imbalance,
                item.phi,
                item.hedge_capacity,
                item.max_hedge_capacity,
                item.hedge_capacity_used_ratio,
                item.funding_cost_bps,
                item.market_volatility,
                item.regime,
                int(item.event_accepted),
                item.acceptance_probability,
                item.cumulative_accepted_events,
                item.cumulative_rejected_events,
                item.cumulative_spread_revenue_usd,
                item.h_total,
                item.h_quadratic,
                item.h_quartic,
                item.h_coupling,
                item.h_external,
                (
                    int(item.controller_activated)
                    if item.controller_activated is not None
                    else None
                ),
                item.controller_h_before_event,
                item.controller_spread_adjustment_bps,
                item.transition_h_before_event,
                item.transition_h_after_if_accepted,
                item.transition_delta_h_if_accepted,
            )
            for item in snapshots
        ]
        event_rows = self._event_rows(events)

        if persist_event_dataset:
            self._persist_event_rows(event_rows)

        for batch in self._chunks(
            snapshot_rows,
            size=CLICKHOUSE_SNAPSHOT_INSERT_BATCH_SIZE,
        ):
            self.client.execute(
                INSERT_INTO_FACT_INVENTORY_SNAPSHOTS_Q,
                batch,
            )

        self.client.execute(INSERT_INTO_FACT_SIM_Q, run_rows)
        if persist_event_dataset:
            self.client.execute(INSERT_INTO_DIM_EVENT_Q, dataset_rows)
        return (
            len(dataset_rows) if persist_event_dataset else ZERO_INT,
            len(run_rows),
            len(snapshot_rows),
            len(event_rows) if persist_event_dataset else ZERO_INT,
        )

    def load_event_dataset(
        self, *,
        event_dataset_id: UUID,
    ) -> list[FXEventRecord]:
        self.ensure_schema()
        rows = self.client.execute(
            SELECT_ALL_FX_EVENTS_Q,
            {'event_dataset_id': event_dataset_id},
        )
        return [
            FXEventRecord(
                event_dataset_id=row[0],
                event_id=row[1],
                event_sequence=row[2],
                source_step_index=row[3],
                event_ts=row[4],
                customer_id=row[5],
                base_currency=row[6],
                quote_currency=row[7],
                side=row[8],
                amount=row[9],
                customer_segment=row[10],
                channel=row[11],
                generator=row[12],
                seed=row[13],
                source_steps=row[14],
                dt_seconds=row[15],
                base_intensity=row[16],
                alpha=row[17],
                beta=row[18],
            )
            for row in rows
        ]

    @staticmethod
    def _event_rows(events: list[FXEventRecord]) -> list[tuple]:
        return [
            (
                item.event_dataset_id,
                item.event_id,
                item.event_sequence,
                item.source_step_index,
                item.event_ts,
                item.customer_id,
                item.base_currency,
                item.quote_currency,
                item.side,
                item.amount,
                item.customer_segment,
                item.channel,
            )
            for item in events
        ]

    def _persist_event_rows(self, rows: list[tuple]) -> None:
        for batch in self._chunks(
            rows,
            size=CLICKHOUSE_SNAPSHOT_INSERT_BATCH_SIZE,
        ):
            self.client.execute(
                INSERT_INTO_FACT_FX_EVENTS_Q,
                batch,
            )


@dataclass(frozen=True)
class InventorySnapshotRecord:
    run_id: UUID
    comparison_id: UUID
    event_dataset_id: UUID

    model_version: str
    physics_mode: str
    pricing_policy: str

    event_index: int
    source_event_id: UUID | None
    source_step_index: int | None
    snapshot_ts: datetime

    currency: str

    position: float
    position_limit: float
    limit_utilization: float
    position_pressure: float

    order_flow_buy_ewma: float
    order_flow_sell_ewma: float
    order_flow_imbalance: float

    phi: float

    hedge_capacity: float
    max_hedge_capacity: float
    hedge_capacity_used_ratio: float

    funding_cost_bps: float
    market_volatility: float

    regime: str

    event_accepted: bool
    acceptance_probability: float

    cumulative_accepted_events: int
    cumulative_rejected_events: int
    cumulative_spread_revenue_usd: float

    h_total: float | None = None
    h_quadratic: float | None = None
    h_quartic: float | None = None
    h_coupling: float | None = None
    h_external: float | None = None

    controller_activated: bool | None = None
    controller_h_before_event: float | None = None
    controller_spread_adjustment_bps: float | None = None

    transition_h_before_event: float | None = None
    transition_h_after_if_accepted: float | None = None
    transition_delta_h_if_accepted: float | None = None
