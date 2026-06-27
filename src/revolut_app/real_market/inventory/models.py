from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


ZERO = Decimal('0')


@dataclass(frozen=True, slots=True)
class UnifiedMarketEvent:
    trade_date: date
    event_index: int

    symbol: str
    aggregate_trade_id: int

    event_timestamp: datetime
    timestamp_us: int

    price: Decimal
    base_quantity: Decimal
    quote_quantity: Decimal

    aggressor_side: str


@dataclass(frozen=True, slots=True)
class InventoryDelta:
    btc: Decimal = ZERO
    eth: Decimal = ZERO
    usdt: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class InventoryState:
    btc: Decimal = ZERO
    eth: Decimal = ZERO
    usdt: Decimal = ZERO

    def apply(
        self,
        delta: InventoryDelta,
    ):
        return InventoryState(
            btc=self.btc + delta.btc,
            eth=self.eth + delta.eth,
            usdt=self.usdt + delta.usdt,
        )


@dataclass(frozen=True, slots=True)
class InventoryReplayRecord:
    trade_date: date
    event_index: int

    symbol: str
    aggregate_trade_id: int

    event_timestamp: datetime
    timestamp_us: int

    price: Decimal
    base_quantity: Decimal
    quote_quantity: Decimal

    aggressor_side: str

    delta_btc: Decimal
    delta_eth: Decimal
    delta_usdt: Decimal

    inventory_btc: Decimal
    inventory_eth: Decimal
    inventory_usdt: Decimal
