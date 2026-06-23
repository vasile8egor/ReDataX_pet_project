from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
    StressRegime,
)


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
class FXQuoteComponents:
    base_spread_bps: float
    inventory_penalty_bps: float
    liquidity_penalty_bps: float
    regime_penalty_bps: float
    hamiltonian_penalty_bps: float = 0.0

    @property
    def total_spread_bps(self) -> float:
        return (
            self.base_spread_bps
            + self.inventory_penalty_bps
            + self.liquidity_penalty_bps
            + self.regime_penalty_bps
            + self.hamiltonian_penalty_bps
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
