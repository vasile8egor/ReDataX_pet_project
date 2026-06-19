from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from clickhouse_driver import Client
from .queries import (
    ALTER_DIM_EVENT_DATASET_Q,
    DIM_EVENT_DATASET_Q,
    FACT_INVENTORY_SNAPSHOTS_Q,
    FACT_SIMULATION_RUNS_Q,
    INSERT_INTO_DIM_EVENT_Q,
    INSERT_INTO_FACT_SIM_Q,
    INSERT_INTO_FACT_INVENT_Q
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


class FXExperimentClickHouseLoader:
    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
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

    def ensure_schema(self):
        self.client.execute(
            '''create database if not exists gold'''
        )
        self.client.execute(DIM_EVENT_DATASET_Q)
        self.client.execute(ALTER_DIM_EVENT_DATASET_Q)
        self.client.execute(FACT_SIMULATION_RUNS_Q)
        self.client.execute(FACT_INVENTORY_SNAPSHOTS_Q)

    def load_comparison(
        self, *,
        event_dataset: EventDatasetRecord,
        runs: list[SimulationRunRecord],
        snapshots: list[InventorySnapshotRecord]
    ):
        if not runs:
            raise ValueError(
                'At least one simulation run is required'
            )

        self.ensure_schema()

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
            )
            for item in snapshots
        ]
        self.client.execute(INSERT_INTO_DIM_EVENT_Q, dataset_rows)
        self.client.execute(INSERT_INTO_FACT_SIM_Q, run_rows)
        self.client.execute(INSERT_INTO_FACT_INVENT_Q, snapshot_rows)
        return (
            len(dataset_rows),
            len(run_rows),
            len(snapshot_rows),
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
