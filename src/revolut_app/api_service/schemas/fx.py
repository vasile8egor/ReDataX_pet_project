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
