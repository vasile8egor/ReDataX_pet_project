from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4, UUID

from revolut_app.fx_lab.constants import (
    DEFAULT_FUNDING_COST_BPS,
    DEFAULT_HEDGE_CAPACITY,
    DEFAULT_MARKET_VOLATILITY,
    DEFAULT_ORDER_FLOW_EWMA,
    DEFAULT_POSITION_LIMIT,
    ONE_FLOAT,
    ZERO_FLOAT,
)


class Currency(str, Enum):
    GBP = 'GBP'
    EUR = 'EUR'
    USD = 'USD'


class FXSide(str, Enum):
    buy = 'buy'
    sell = 'sell'


class CustomerSegment(str, Enum):
    retail = 'retail'
    premium = 'premium'
    business = 'business'


class StressRegime(str, Enum):
    calm = 'calm'
    elevated = 'elevated'
    stress = 'stress'


@dataclass(frozen=True)
class QuoteRequest:
    customer_id: str
    base_currency: Currency
    quote_currency: Currency
    side: FXSide
    amount: float
    segment: CustomerSegment
    channel: str = 'app'


@dataclass
class CurrencyState:
    currency: Currency
    position: float
    position_limit: float = DEFAULT_POSITION_LIMIT
    hedge_capacity: float = DEFAULT_HEDGE_CAPACITY
    max_hedge_capacity: float = DEFAULT_HEDGE_CAPACITY
    funding_cost_bps: float = DEFAULT_FUNDING_COST_BPS
    market_volatility: float = DEFAULT_MARKET_VOLATILITY
    order_flow_buy_ewma: float = DEFAULT_ORDER_FLOW_EWMA
    order_flow_sell_ewma: float = DEFAULT_ORDER_FLOW_EWMA
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def limit_utilization(self) -> float:
        if self.position_limit <= ZERO_FLOAT:
            return ZERO_FLOAT
        return abs(self.position) / self.position_limit

    @property
    def hedge_capacity_used_ratio(self) -> float:
        if self.max_hedge_capacity <= ZERO_FLOAT:
            return ONE_FLOAT
        used = self.max_hedge_capacity - self.hedge_capacity
        return max(ZERO_FLOAT, min(ONE_FLOAT, used / self.max_hedge_capacity))


@dataclass
class FXQuoteComponents:
    base_spread_bps: float
    inventory_penalty_bps: float
    liquidity_penalty_bps: float
    regime_penalty_bps: float

    @property
    def total_spread_bps(self) -> float:
        return (
            self.base_spread_bps
            + self.inventory_penalty_bps
            + self.liquidity_penalty_bps
            + self.regime_penalty_bps
        )


@dataclass
class FXQuote:
    quote_id: str
    timestamp: datetime
    request: QuoteRequest
    mid_rate: float
    client_rate: float
    components: FXQuoteComponents
    inventory_pressure: dict[str, float]
    regime: StressRegime
    executed: bool = False

    @classmethod
    def new(
        cls,
        *,
        request: QuoteRequest,
        mid_rate: float,
        client_rate: float,
        components: FXQuoteComponents,
        inventory_pressure: dict[str, float],
        regime: StressRegime,
        executed: bool = False,
    ) -> 'FXQuote':
        return cls(
            quote_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            request=request,
            mid_rate=mid_rate,
            client_rate=client_rate,
            components=components,
            inventory_pressure=inventory_pressure,
            regime=regime,
            executed=executed,
        )


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
