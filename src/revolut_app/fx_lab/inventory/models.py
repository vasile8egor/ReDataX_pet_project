from dataclasses import dataclass, field
from datetime import datetime, timezone

from revolut_app.fx_lab.shared.constants import (
    DEFAULT_FUNDING_COST_BPS,
    DEFAULT_HEDGE_CAPACITY,
    DEFAULT_MARKET_VOLATILITY,
    DEFAULT_ORDER_FLOW_EWMA,
    DEFAULT_POSITION_LIMIT,
    ONE_FLOAT,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.shared.enums import Currency


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
    def limit_utilization(self):
        if self.position_limit <= ZERO_FLOAT:
            return ZERO_FLOAT
        return abs(self.position) / self.position_limit

    @property
    def hedge_capacity_used_ratio(self):
        if self.max_hedge_capacity <= ZERO_FLOAT:
            return ONE_FLOAT
        used = self.max_hedge_capacity - self.hedge_capacity
        return max(ZERO_FLOAT, min(ONE_FLOAT, used / self.max_hedge_capacity))
