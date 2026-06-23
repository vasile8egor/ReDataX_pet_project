from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from revolut_app.fx_lab.shared.constants import (
    DEFAULT_PNL_FUNDING_COST_USD,
    DEFAULT_PNL_LAST_EVENTS_LIMIT,
    PNL_PRECISION,
    ZERO_FLOAT,
)


class PnLEventType(str, Enum):
    spread_revenue = 'spread_revenue'
    hedge_cost = 'hedge_cost'
    funding_cost = 'funding_cost'


@dataclass(frozen=True)
class PnLEvent:
    event_id: str
    event_type: PnLEventType
    timestamp: datetime
    amount_usd: float
    description: str
    metadata: dict[str, str | float | int] = field(default_factory=dict)

    @classmethod
    def new(
        cls, *,
        event_type: PnLEventType,
        amount_usd: float,
        description: str,
        metadata: dict[str, str | float | int] | None = None,
    ) -> 'PnLEvent':
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            amount_usd=round(float(amount_usd), PNL_PRECISION),
            description=description,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class PnLSnapshot:
    spread_revenue_usd: float
    hedge_cost_usd: float
    funding_cost_usd: float
    gross_pnl_usd: float
    net_pnl_usd: float
    events_count: int
    last_events: list[PnLEvent]


class PnLLedger:
    def __init__(self) -> None:
        self.events: list[PnLEvent] = []

    def record_spread_revenue(
        self, *,
        quote_id: str,
        currency_pair: str,
        notional_usd: float,
        spread_bps: float,
        revenue_usd: float,
    ) -> PnLEvent:
        event = PnLEvent.new(
            event_type=PnLEventType.spread_revenue,
            amount_usd=revenue_usd,
            description=(
                f'Spread revenue from accepted FX quote {quote_id}'
            ),
            metadata={
                'quote_id': quote_id,
                'currency_pair': currency_pair,
                'notional_usd': round(notional_usd, PNL_PRECISION),
                'spread_bps': round(spread_bps, PNL_PRECISION),
            },
        )
        self.events.append(event)
        return event

    def record_hedge_cost(
        self, *,
        currency: str,
        hedge_action: str,
        executed_amount: float,
        notional_usd: float,
        hedge_cost_bps: float,
        hedge_cost_usd: float,
    ) -> PnLEvent:
        event = PnLEvent.new(
            event_type=PnLEventType.hedge_cost,
            amount_usd=hedge_cost_usd,
            description=(
                f"Hedge execution cost for {hedge_action} {currency}"
            ),
            metadata={
                "currency": currency,
                "hedge_action": hedge_action,
                "executed_amount": round(
                    executed_amount,
                    PNL_PRECISION,
                ),
                "notional_usd": round(notional_usd, PNL_PRECISION),
                "hedge_cost_bps": round(hedge_cost_bps, PNL_PRECISION),
            },
        )
        self.events.append(event)
        return event

    def snapshot(
        self, *,
        funding_cost_usd: float = DEFAULT_PNL_FUNDING_COST_USD,
        last_events_limit: int = DEFAULT_PNL_LAST_EVENTS_LIMIT,
    ) -> PnLSnapshot:
        spread_revenue_usd = sum(
            event.amount_usd
            for event in self.events
            if event.event_type == PnLEventType.spread_revenue
        )

        hedge_cost_usd = sum(
            event.amount_usd
            for event in self.events
            if event.event_type == PnLEventType.hedge_cost
        )

        gross_pnl_usd = spread_revenue_usd
        net_pnl_usd = (
            spread_revenue_usd - hedge_cost_usd - funding_cost_usd
        )

        return PnLSnapshot(
            spread_revenue_usd=round(spread_revenue_usd, PNL_PRECISION),
            hedge_cost_usd=round(hedge_cost_usd, PNL_PRECISION),
            funding_cost_usd=round(funding_cost_usd, PNL_PRECISION),
            gross_pnl_usd=round(gross_pnl_usd, PNL_PRECISION),
            net_pnl_usd=round(net_pnl_usd, PNL_PRECISION),
            events_count=len(self.events),
            last_events=self.events[-last_events_limit:],
        )
