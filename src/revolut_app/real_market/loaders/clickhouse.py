from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Sequence

from clickhouse_driver import Client

from revolut_app.real_market.models import (
    AggressorSide,
    BinanceAggTrade,
)
from revolut_app.real_market.inventory.models import (
    InventoryReplayRecord
)
from .queries import (
    CREATE_RAW_DATABASE_Q,
    CREATE_REAL_MARKET_AGG_TRADES_Q,
    CREATE_REAL_MARKET_INVENTORY_EVENTS_Q,
    CREATE_SILVER_DATABASE_Q,
    DELETE_REAL_MARKET_DAY_Q,
    INSERT_REAL_MARKET_AGG_TRADES_Q,
    INSERT_REAL_MARKET_INVENTORY_EVENTS_Q,
)


@dataclass(frozen=True, slots=True)
class RealMarketAggTradeRecord:
    venue: str
    market_type: str

    symbol: str
    trade_date: date

    aggregate_trade_id: int

    event_timestamp: datetime
    timestamp_us: int

    price: Decimal
    base_quantity: Decimal
    quote_quantity: Decimal

    first_trade_id: int
    last_trade_id: int

    buyer_was_maker: bool
    best_price_match: bool

    aggressor_side: int

    source_archive_sha256: str

    def as_clickhouse_row(
        self,
    ):
        return (
            self.venue,
            self.market_type,
            self.symbol,
            self.trade_date,
            self.aggregate_trade_id,
            self.event_timestamp,
            self.timestamp_us,
            self.price,
            self.base_quantity,
            self.quote_quantity,
            self.first_trade_id,
            self.last_trade_id,
            int(self.buyer_was_maker),
            int(self.best_price_match),
            self.aggressor_side,
            self.source_archive_sha256,
        )


def build_real_market_record(
    *,
    trade: BinanceAggTrade,
    trade_date: date,
    archive_sha256: str,
):
    event_timestamp = datetime.fromtimestamp(
        trade.timestamp_us / 1_000_000,
        tz=timezone.utc,
    )

    return RealMarketAggTradeRecord(
        venue='binance',
        market_type='spot',
        symbol=trade.symbol,
        trade_date=trade_date,
        aggregate_trade_id=(
            trade.aggregate_trade_id
        ),
        event_timestamp=event_timestamp,
        timestamp_us=trade.timestamp_us,
        price=trade.price,
        base_quantity=trade.quantity,
        quote_quantity=trade.quote_quantity,
        first_trade_id=trade.first_trade_id,
        last_trade_id=trade.last_trade_id,
        buyer_was_maker=trade.buyer_was_maker,
        best_price_match=trade.best_price_match,
        aggressor_side=(
            1
            if trade.aggressor_side == AggressorSide.BUY_BASE
            else -1
        ),
        source_archive_sha256=archive_sha256,
    )


class RealMarketAggTradesLoader:
    def __init__(
        self, *,
        client: Client,
        batch_size: int = 50_000,
    ):
        if batch_size <= 0:
            raise ValueError(
                'batch_size must be positive'
            )

        self._client = client
        self._batch_size = batch_size

    def ensure_schema(self):
        self._client.execute(
            CREATE_RAW_DATABASE_Q
        )

        self._client.execute(
            CREATE_REAL_MARKET_AGG_TRADES_Q
        )

    def persist_records(
        self,
        records: Iterable[RealMarketAggTradeRecord],
    ):
        self.ensure_schema()

        inserted = 0
        batch: list[tuple[object, ...]] = []

        for record in records:
            batch.append(
                record.as_clickhouse_row()
            )

            if len(batch) >= self._batch_size:
                self._insert_batch(batch)

                inserted += len(batch)
                batch.clear()

        if batch:
            self._insert_batch(batch)
            inserted += len(batch)

        return inserted

    def _insert_batch(self, batch: Sequence[tuple[object, ...]],):
        self._client.execute(
            INSERT_REAL_MARKET_AGG_TRADES_Q,
            batch,
            types_check=True,
        )

    def delete_day(
        self, *,
        trade_date: date,
        symbols: Sequence[str],
    ):
        if not symbols:
            return

        self.ensure_schema()
        self._client.execute(
            DELETE_REAL_MARKET_DAY_Q,
            {
                'venue': 'binance',
                'market_type': 'spot',
                'trade_date': trade_date,
                'symbols': tuple(symbols),
            },
        )


class RealMarketInventoryLoader:
    def __init__(self, client: Client, batch_size: int = 50_000):
        if batch_size <= 0:
            raise ValueError('batch_size must be positive')

        self._client = client
        self._batch_size = batch_size

    def ensure_schema(self):
        self._client.execute(
            CREATE_SILVER_DATABASE_Q
        )

        self._client.execute(
            CREATE_REAL_MARKET_INVENTORY_EVENTS_Q
        )

    def persist(
        self, *,
        records: Iterable[InventoryReplayRecord],
        replay_model_version: str,
    ):
        self.ensure_schema()

        if not replay_model_version:
            raise ValueError(
                'replay_model_version cant be empty'
            )

        inserted = 0
        batch: list[tuple[object, ...]] = []

        for record in records:
            batch.append(
                (
                    record.trade_date,
                    record.event_index,
                    record.symbol,
                    record.aggregate_trade_id,
                    record.event_timestamp,
                    record.timestamp_us,
                    record.price,
                    record.base_quantity,
                    record.quote_quantity,
                    _aggressor_side_to_clickhouse_value(
                        record.aggressor_side
                    ),
                    record.delta_btc,
                    record.delta_eth,
                    record.delta_usdt,
                    record.inventory_btc,
                    record.inventory_eth,
                    record.inventory_usdt,
                    replay_model_version,
                )
            )

            if len(batch) >= self._batch_size:
                self._insert(batch)
                inserted += len(batch)
                batch.clear()
        if batch:
            self._insert(batch)
            inserted += len(batch)
        return inserted

    def _insert(self, batch: Sequence[tuple[object, ...]]):
        self._client.execute(
            INSERT_REAL_MARKET_INVENTORY_EVENTS_Q,
            batch,
            types_check=True,
        )


def _aggressor_side_to_clickhouse_value(
    aggressor_side: str,
):
    if aggressor_side == AggressorSide.BUY_BASE.value:
        return 1

    if aggressor_side == AggressorSide.SELL_BASE.value:
        return -1

    raise ValueError(
        'Unsupported aggressor_side: '
        f'{aggressor_side}'
    )
