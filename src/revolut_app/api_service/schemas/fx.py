from datetime import datetime

from pydantic import BaseModel, Field

from revolut_app.fx_lab.constants import (
    DEFAULT_AMOUNT_MULTIPLIER,
    DEFAULT_HAWKES_ALPHA,
    DEFAULT_HAWKES_BETA,
    DEFAULT_HAWKES_DT_SECONDS,
    DEFAULT_MAX_SNAPSHOTS,
    DEFAULT_SIMULATION_BASE_INTENSITY,
    DEFAULT_SIMULATION_SEED,
    DEFAULT_SIMULATION_STEPS,
    DEFAULT_STRESS_HEDGE_CAPACITY_MULTIPLIER,
    DEFAULT_STRESS_VOLATILITY_MULTIPLIER,
    MAX_ALPHA,
    MAX_AMOUNT_MULTIPLIER,
    MAX_BETA,
    MAX_DT_SECONDS,
    MAX_INTENSITY,
    MAX_MAX_SNAPSHOTS,
    MAX_SIMULATION_STEPS,
    MIN_ALPHA,
    MIN_AMOUNT_MULTIPLIER,
    MIN_BETA,
    MIN_DT_SECONDS,
    MIN_INTENSITY,
    MIN_MAX_SNAPSHOTS,
    MIN_SIMULATION_STEPS,
)
from revolut_app.fx_lab.models import (
    Currency,
    CustomerSegment,
    FXSide,
    StressRegime,
)


class FXQuoteRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    base_currency: Currency
    quote_currency: Currency
    side: FXSide
    amount: float = Field(..., gt=0)
    segment: CustomerSegment = CustomerSegment.retail
    channel: str = 'app'
    execute: bool = False


class FXQuoteComponentsResponse(BaseModel):
    base_spread_bps: float
    inventory_penalty_bps: float
    liquidity_penalty_bps: float
    regime_penalty_bps: float
    total_spread_bps: float


class FXQuoteResponse(BaseModel):
    quote_id: str
    timestamp: datetime
    customer_id: str
    base_currency: Currency
    quote_currency: Currency
    side: FXSide
    amount: float
    mid_rate: float
    client_rate: float
    components: FXQuoteComponentsResponse
    inventory_pressure: dict[str, float]
    regime: StressRegime
    executed: bool


class InventoryStateResponse(BaseModel):
    currency: Currency
    position: float
    position_limit: float
    limit_utilization: float
    hedge_capacity: float
    max_hedge_capacity: float
    hedge_capacity_used_ratio: float
    funding_cost_bps: float
    market_volatility: float
    phi: float


class RiskSnapshotResponse(BaseModel):
    regime: StressRegime
    inventory_pressure: dict[str, float]
    states: list[InventoryStateResponse]


class StressShockRequest(BaseModel):
    volatility_multiplier: float = Field(
        default=DEFAULT_STRESS_VOLATILITY_MULTIPLIER,
        gt=0,
    )
    hedge_capacity_multiplier: float = Field(
        default=DEFAULT_STRESS_HEDGE_CAPACITY_MULTIPLIER,
        gt=0,
        le=1,
    )


class DaySimulationRequest(BaseModel):
    steps: int = Field(
        default=DEFAULT_SIMULATION_STEPS,
        ge=MIN_SIMULATION_STEPS,
        le=MAX_SIMULATION_STEPS,
    )
    dt_seconds: int = Field(
        default=DEFAULT_HAWKES_DT_SECONDS,
        ge=MIN_DT_SECONDS,
        le=MAX_DT_SECONDS,
    )

    base_intensity: float = Field(
        default=DEFAULT_SIMULATION_BASE_INTENSITY,
        ge=MIN_INTENSITY,
        le=MAX_INTENSITY,
    )
    alpha: float = Field(
        default=DEFAULT_HAWKES_ALPHA,
        ge=MIN_ALPHA,
        le=MAX_ALPHA,
    )
    beta: float = Field(
        default=DEFAULT_HAWKES_BETA,
        ge=MIN_BETA,
        le=MAX_BETA,
    )

    seed: int | None = DEFAULT_SIMULATION_SEED

    reset_state: bool = True
    amount_multiplier: float = Field(
        default=DEFAULT_AMOUNT_MULTIPLIER,
        ge=MIN_AMOUNT_MULTIPLIER,
        le=MAX_AMOUNT_MULTIPLIER,
    )
    max_snapshots: int = Field(
        default=DEFAULT_MAX_SNAPSHOTS,
        ge=MIN_MAX_SNAPSHOTS,
        le=MAX_MAX_SNAPSHOTS,
    )


class InventorySnapshotPointResponse(BaseModel):
    event_index: int
    timestamp: datetime
    regime: StressRegime
    inventory_pressure: dict[str, float]
    max_abs_pressure: float
    synthetic_spread_revenue_usd: float


class DaySimulationResponse(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    generated_requests: int
    executed_events: int
    final_regime: StressRegime
    max_abs_pressure: float
    stress_time_fraction: float
    elevated_or_stress_time_fraction: float
    synthetic_spread_revenue_usd: float
    final_inventory_pressure: dict[str, float]
    regime_counts: dict[str, int]
    snapshots: list[InventorySnapshotPointResponse]
