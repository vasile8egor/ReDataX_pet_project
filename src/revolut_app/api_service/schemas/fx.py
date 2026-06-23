from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from uuid import UUID

from revolut_app.fx_lab.constants import (
    DEFAULT_AMOUNT_MULTIPLIER,
    DEFAULT_HAWKES_ALPHA,
    DEFAULT_HAWKES_BETA,
    DEFAULT_HAWKES_DT_SECONDS,
    DEFAULT_HEDGE_PRESSURE_THRESHOLD,
    DEFAULT_HEDGE_TARGET_PRESSURE,
    DEFAULT_MAX_HEDGE_FRACTION,
    DEFAULT_MAX_SNAPSHOTS,
    DEFAULT_MIN_HEDGE_NOTIONAL,
    DEFAULT_POLICY_COMPARISON_AMOUNT_MULTIPLIER,
    DEFAULT_POLICY_SNAPSHOT_EVERY_N_EVENTS,
    DEFAULT_SIMULATION_BASE_INTENSITY,
    DEFAULT_SIMULATION_SEED,
    DEFAULT_SIMULATION_STEPS,
    DEFAULT_STRESS_HEDGE_CAPACITY_MULTIPLIER,
    DEFAULT_STRESS_VOLATILITY_MULTIPLIER,
    DEFAULT_RG_STRESS_THRESHOLD,
    DEFAULT_RG_WINDOW_SIZES,
    MAX_ALPHA,
    MAX_AMOUNT_MULTIPLIER,
    MAX_BETA,
    MAX_DT_SECONDS,
    MAX_INTENSITY,
    MAX_HEDGE_PRESSURE_THRESHOLD,
    MAX_HEDGE_TARGET_PRESSURE,
    MAX_MAX_HEDGE_FRACTION,
    MAX_MAX_SNAPSHOTS,
    MAX_SIMULATION_STEPS,
    MIN_ALPHA,
    MIN_AMOUNT_MULTIPLIER,
    MIN_BETA,
    MIN_DT_SECONDS,
    MIN_INTENSITY,
    MIN_HEDGE_NOTIONAL,
    MIN_HEDGE_PRESSURE_THRESHOLD,
    MIN_HEDGE_TARGET_PRESSURE,
    MIN_MAX_HEDGE_FRACTION,
    MIN_MAX_SNAPSHOTS,
    MIN_POLICY_COMPARISON_POLICIES,
    MIN_POLICY_SNAPSHOT_EVERY_N_EVENTS,
    MIN_RG_WINDOW_SIZE,
    MIN_SIMULATION_STEPS,
    MAX_POLICY_SNAPSHOT_EVERY_N_EVENTS,
)
from revolut_app.fx_lab.execution_constants import (
    DEFAULT_HEDGE_COST_BPS,
    DEFAULT_MAX_HEDGE_ACTIONS,
    MAX_HEDGE_ACTIONS,
    MAX_HEDGE_COST_BPS,
    MIN_HEDGE_ACTIONS,
    MIN_HEDGE_COST_BPS,
)
from revolut_app.fx_lab.models import (
    Currency,
    CustomerSegment,
    FXSide,
    StressRegime,
    HamiltonianPreset,
)
from revolut_app.fx_lab.hedging import HedgeAction
from revolut_app.fx_lab.pnl import PnLEventType
from revolut_app.fx_lab.policies import QuotePolicyName
from revolut_app.fx_lab.experiment_models import PhysicsMode


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
    accepted: bool
    acceptance_probability: float
    rejected_events: int


class DaySimulationResponse(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    generated_requests: int
    executed_events: int
    accepted_events: int
    rejected_events: int
    acceptance_rate: float
    final_regime: StressRegime
    max_abs_pressure: float
    stress_time_fraction: float
    elevated_or_stress_time_fraction: float
    synthetic_spread_revenue_usd: float
    final_inventory_pressure: dict[str, float]
    regime_counts: dict[str, int]
    snapshots: list[InventorySnapshotPointResponse]


class RGFlowRequest(BaseModel):
    window_sizes: list[int] = Field(
        default_factory=lambda: DEFAULT_RG_WINDOW_SIZES.copy(),
        min_length=1,
    )
    stress_threshold: float = Field(
        default=DEFAULT_RG_STRESS_THRESHOLD,
        gt=0.0
    )

    @field_validator('window_sizes')
    @classmethod
    def validate_window_sizes(cls, value: list[int]) -> list[int]:
        invalid = [
            window_size
            for window_size in value
            if window_size < MIN_RG_WINDOW_SIZE
        ]
        if invalid:
            raise ValueError(
                'window_sizes must contain only positive integers'
            )
        return value


class RGFlowPointResponse(BaseModel):
    window_size: int
    currency: str
    mean_phi: float
    var_phi: float
    autocorr_lag1: float
    stress_probability: float


class RGFlowResponse(BaseModel):
    source_run_id: str
    source_snapshots: int
    window_sizes: list[int]
    stress_threshold: float
    points: list[RGFlowPointResponse]


class HedgeRecommendationRequest(BaseModel):
    pressure_threshold: float = Field(
        default=DEFAULT_HEDGE_PRESSURE_THRESHOLD,
        gt=MIN_HEDGE_PRESSURE_THRESHOLD,
        le=MAX_HEDGE_PRESSURE_THRESHOLD,
    )
    target_pressure: float = Field(
        default=DEFAULT_HEDGE_TARGET_PRESSURE,
        ge=MIN_HEDGE_TARGET_PRESSURE,
        le=MAX_HEDGE_TARGET_PRESSURE,
    )
    max_hedge_fraction: float = Field(
        default=DEFAULT_MAX_HEDGE_FRACTION,
        gt=MIN_MAX_HEDGE_FRACTION,
        le=MAX_MAX_HEDGE_FRACTION,
    )
    min_notional: float = Field(
        default=DEFAULT_MIN_HEDGE_NOTIONAL,
        ge=MIN_HEDGE_NOTIONAL,
    )


class HedgeRecommendationItemResponse(BaseModel):
    currency: Currency
    action: HedgeAction
    amount: float
    desired_amount: float
    capacity_limited: bool
    unhedged_amount: float
    current_position: float
    position_limit: float
    current_pressure: float
    threshold: float
    target_pressure: float
    expected_pressure_reduction: float
    reason: str


class HedgeRecommendationResponse(BaseModel):
    regime: StressRegime
    pressure_threshold: float
    target_pressure: float
    recommendations: list[HedgeRecommendationItemResponse]


class HedgeExecutionRequest(BaseModel):
    pressure_threshold: float = Field(
        default=DEFAULT_HEDGE_PRESSURE_THRESHOLD,
        gt=MIN_HEDGE_PRESSURE_THRESHOLD,
        le=MAX_HEDGE_PRESSURE_THRESHOLD,
    )
    target_pressure: float = Field(
        default=DEFAULT_HEDGE_TARGET_PRESSURE,
        ge=MIN_HEDGE_TARGET_PRESSURE,
        le=MAX_HEDGE_TARGET_PRESSURE,
    )
    max_hedge_fraction: float = Field(
        default=DEFAULT_MAX_HEDGE_FRACTION,
        gt=MIN_MAX_HEDGE_FRACTION,
        le=MAX_MAX_HEDGE_FRACTION,
    )
    min_notional: float = Field(
        default=DEFAULT_MIN_HEDGE_NOTIONAL,
        ge=MIN_HEDGE_NOTIONAL,
    )

    hedge_cost_bps: float = Field(
        default=DEFAULT_HEDGE_COST_BPS,
        ge=MIN_HEDGE_COST_BPS,
        le=MAX_HEDGE_COST_BPS,
    )
    max_actions: int = Field(
        default=DEFAULT_MAX_HEDGE_ACTIONS,
        ge=MIN_HEDGE_ACTIONS,
        le=MAX_HEDGE_ACTIONS,
    )


class HedgeExecutionItemResponse(BaseModel):
    currency: Currency
    action: HedgeAction
    request_amount: float
    executed_amount: float
    hedge_cost_usd: float

    position_before: float
    position_after: float

    pressure_before: float
    pressure_after: float

    hedge_capacity_before: float
    hedge_capacity_after: float


class HedgeExecutionResponse(BaseModel):
    before: RiskSnapshotResponse
    after: RiskSnapshotResponse
    executed_hedges: list[HedgeExecutionItemResponse]
    total_hedge_cost_usd: float
    executed_count: int
    skipped_count: int
    message: str


class PnLEventResponse(BaseModel):
    event_id: str
    event_type: PnLEventType
    timestamp: datetime
    amount_usd: float
    description: str
    metadata: dict[str, str | float | int]


class PnLSnapshotResponse(BaseModel):
    spread_revenue_usd: float
    hedge_cost_usd: float
    funding_cost_usd: float
    gross_pnl_usd: float
    net_pnl_usd: float
    events_count: int
    last_events: list[PnLEventResponse]


class PolicyComparisonRequest(BaseModel):
    policies: list[QuotePolicyName] = Field(
        default_factory=lambda: [
            QuotePolicyName.naive,
            QuotePolicyName.inventory_aware,
            QuotePolicyName.platform,
        ],
        min_length=MIN_POLICY_COMPARISON_POLICIES,
    )
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
        gt=MIN_BETA,
        le=MAX_BETA,
    )
    seed: int | None = DEFAULT_SIMULATION_SEED
    amount_multiplier: float = Field(
        default=DEFAULT_POLICY_COMPARISON_AMOUNT_MULTIPLIER,
        gt=MIN_AMOUNT_MULTIPLIER,
        le=MAX_AMOUNT_MULTIPLIER,
    )
    persist_result: bool = True
    model_version: str = Field(
        default='baseline_v1',
        min_length=1,
        max_length=100,
    )
    physics_mode: PhysicsMode = PhysicsMode.none
    hedging_policy: str = Field(
        default='none',
        min_length=1,
        max_length=100,
    )
    snapshot_every_n_events: int = Field(
        default=DEFAULT_POLICY_SNAPSHOT_EVERY_N_EVENTS,
        ge=MIN_POLICY_SNAPSHOT_EVERY_N_EVENTS,
        le=MAX_POLICY_SNAPSHOT_EVERY_N_EVENTS,
    )
    event_dataset_id: UUID | None = None
    simulation_start_at: datetime | None = None
    hamiltonian_preset: HamiltonianPreset | None = None

    @model_validator(mode='after')
    def validate_hamiltonian_configuration(self):
        if (
            self.physics_mode == PhysicsMode.none
            and self.hamiltonian_preset is not None
        ):
            raise ValueError(
                'hamiltonian_preset must be null when physics mode is none'
            )
        if self.physics_mode in {
            PhysicsMode.observer,
            PhysicsMode.controller
        } and self.hamiltonian_preset is None:
            raise ValueError(
                'hamiltonian_preset is required when physics mode is not none'
            )
        return self


class ExperimentPersistenceResponse(BaseModel):
    persistence: bool
    event_dataset_rows: int
    simulation_run_rows: int
    inventory_snapshot_rows: int
    event_rows: int


class PolicyRunResponse(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime

    policy: QuotePolicyName

    generated_requests: int
    accepted_events: int
    rejected_events: int
    acceptance_rate: float

    average_quoted_spread_bps: float
    average_accepted_spread_bps: float
    customer_spread_cost_usd: float

    spread_revenue_usd: float
    allocated_product_revenue_usd: float
    funding_cost_usd: float
    net_pnl_usd: float

    final_regime: StressRegime
    max_abs_pressure: float
    stress_time_fraction: float
    final_inventory_pressure: dict[str, float]


class PolicyComparisonResponse(BaseModel):
    event_dataset_id: UUID
    event_dataset_reused: bool
    persistence: ExperimentPersistenceResponse
    comparison_id: str
    started_at: datetime
    finished_at: datetime
    generated_requests: int
    seed: int | None

    results: list[PolicyRunResponse]

    best_policy_by_net_pnl: QuotePolicyName
    lowest_risk_policy: QuotePolicyName
    lowest_customer_spread_policy: QuotePolicyName

    model_version: str
    physics_mode: PhysicsMode
    hamiltonian_preset: HamiltonianPreset | None
