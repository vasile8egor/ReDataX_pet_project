from datetime import date
from decimal import Decimal

from revolut_app.real_market.loaders.clickhouse import (
    RealMarketAggTradesLoader,
    build_real_market_record,
)
from revolut_app.real_market.loaders.queries import (
    CREATE_RAW_DATABASE_Q,
    CREATE_REAL_MARKET_AGG_TRADES_Q,
    DELETE_REAL_MARKET_DAY_Q,
)
from revolut_app.real_market.models import (
    AggressorSide,
    BinanceAggTrade,
)


def test_builds_clickhouse_record():
    trade = BinanceAggTrade(
        symbol='BTCUSDT',
        aggregate_trade_id=100,
        price=Decimal('100000.5'),
        quantity=Decimal('0.01'),
        first_trade_id=200,
        last_trade_id=201,
        timestamp_us=(
            1736121600010006
        ),
        buyer_was_maker=False,
        best_price_match=True,
        aggressor_side=(
            AggressorSide.BUY_BASE
        ),
    )

    record = build_real_market_record(
        trade=trade,
        trade_date=date(2025, 1, 6),
        archive_sha256='a' * 64,
    )

    assert record.venue == 'binance'
    assert record.market_type == 'spot'

    assert record.symbol == 'BTCUSDT'

    assert record.base_quantity == (
        Decimal('0.01')
    )

    assert record.quote_quantity == (
        Decimal('1000.005')
    )

    assert record.aggressor_side == (
        1
    )

    assert record.event_timestamp.tzinfo \
        is not None


class _FakeClickHouseClient:
    def __init__(self):
        self.calls: list[tuple[object, ...]] = []

    def execute(self, *args: object, **kwargs: object):
        self.calls.append((*args, kwargs))


def test_delete_day_ensures_schema_before_mutation():
    client = _FakeClickHouseClient()

    loader = RealMarketAggTradesLoader(
        client=client,  # type: ignore[arg-type]
    )

    loader.delete_day(
        trade_date=date(2025, 1, 6),
        symbols=['BTCUSDT', 'ETHBTC'],
    )

    assert client.calls[0][0] == CREATE_RAW_DATABASE_Q
    assert client.calls[1][0] == CREATE_REAL_MARKET_AGG_TRADES_Q
    assert client.calls[2][0] == DELETE_REAL_MARKET_DAY_Q

    assert client.calls[2][1] == {
        'venue': 'binance',
        'market_type': 'spot',
        'trade_date': date(2025, 1, 6),
        'symbols': ('BTCUSDT', 'ETHBTC'),
    }
