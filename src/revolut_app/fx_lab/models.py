from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


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
    position_limit: float = 100_000.0
    hedge_capacity: float = 50_000.0
    max_hedge_capacity: float = 50_000.0
    funding_cost_bps: float = 1.0
    market_volatility: float = 0.01
    order_flow_buy_ewma: float = 0.0
    order_flow_sell_ewma: float = 0.0
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def limit_utilization(self) -> float:
        if self.position_limit <= 0:
            return 0.0
        return abs(self.position) / self.position_limit

    @property
    def hedge_capacity_used_ratio(self) -> float:
        if self.max_hedge_capacity <= 0:
            return 1.0
        used = self.max_hedge_capacity - self.hedge_capacity
        return max(0.0, min(1.0, used / self.max_hedge_capacity))


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
