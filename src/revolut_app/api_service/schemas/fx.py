from datetime import datetime
from pydantic import BaseModel, Field
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
    volatility_multiplier: float = Field(default=2.0, gt=0)
    hedge_capacity_multiplier: float = Field(default=0.7, gt=0, le=1)


class DaySimulationRequest(BaseModel):
    steps: int = Field(default=5000, ge=1, le=100_000)
    dt_seconds: int = Field(default=10, ge=1, le=3600)

    base_intensity: float = Field(default=0.03, ge=0.0, le=1.0)
    alpha: float = Field(default=0.08, ge=0.0, le=5.0)
    beta: float = Field(default=0.12, ge=0.0, le=10.0)

    seed: int | None = 42

    reset_state: bool = True
    amount_multiplier: float = Field(default=1000.0, ge=0, le=1_000_000.0)
    max_snapshots: int = Field(default=100, ge=0, le=10_000)


class InventorySnapshotPointResponse(BaseModel):
    event_idx: int
    timestamp: datetime
    regime: StressRegime
    inventory_pressure: float
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
    elevated_o_stress_time_fraction: float
    synthetic_spread_revenue_usd: float
    final_inventory_pressure: dict[str, float]
    regime_counts: dict[str, int]
    snapshots: list[InventorySnapshotPointResponse]
