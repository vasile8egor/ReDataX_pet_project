from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.pricing.policies import QuotePolicyName
from revolut_app.fx_lab.shared.enums import Currency, StressRegime


class PhysicsMode(str, Enum):
    none = 'none'
    observer = 'observer'
    controller = 'controller'


@dataclass(frozen=True)
class FXEvent:
    event_id: UUID
    event_sequence: int
    source_step_index: int
    event_ts: datetime
    request: QuoteRequest


@dataclass(frozen=True)
class FXEventDataset:
    event_dataset_id: UUID
    generator: str
    seed: int | None
    started_at: datetime
    finished_at: datetime
    source_steps: int
    dt_seconds: int
    base_intensity: float
    alpha: float
    beta: float
    events: tuple[FXEvent, ...]


@dataclass(frozen=True)
class PolicyRunResult:
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
    snapshots: list['PolicyInventorySnapshot']


@dataclass(frozen=True)
class PolicyComparisonResult:
    comparison_id: str
    event_dataset_id: str

    started_at: datetime
    finished_at: datetime
    generated_requests: int
    seed: int | None
    results: list[PolicyRunResult]

    best_policy_by_net_pnl: QuotePolicyName
    lowest_risk_policy: QuotePolicyName
    lowest_customer_spread_policy: QuotePolicyName


@dataclass(frozen=True)
class PolicyInventorySnapshot:
    event_index: int
    snapshot_ts: datetime

    currency: Currency

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

    source_event_id: UUID | None
    source_step_index: int | None

    funding_cost_bps: float
    market_volatility: float

    regime: StressRegime

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
