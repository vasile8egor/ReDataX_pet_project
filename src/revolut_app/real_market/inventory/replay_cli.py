import argparse
import os
from datetime import date
from decimal import Decimal

from clickhouse_driver import Client

from revolut_app.real_market.inventory.models import (
    UnifiedMarketEvent,
)
from revolut_app.real_market.inventory.replay import (
    replay_passive_market_maker_inventory,
)
from revolut_app.real_market.loaders.clickhouse import (
    RealMarketInventoryLoader,
)
from .queries import SELECT_EVENTS_Q


REPLAY_MODEL_VERSION = (
    'passive-market-maker-unhedged-v1'
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--date',
        required=True,
        type=date.fromisoformat,
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50_000,
    )

    parser.add_argument(
        '--model-version',
        default=REPLAY_MODEL_VERSION,
    )

    arguments = parser.parse_args()

    read_client = _build_clickhouse_client()
    write_client = _build_clickhouse_client()

    events = (
        _row_to_event(row)
        for row in read_client.execute_iter(
            SELECT_EVENTS_Q,
            {
                'trade_date': (
                    arguments.date
                )
            },
            settings={
                'max_block_size': 50_000,
            },
        )
    )

    replay_records = (
        replay_passive_market_maker_inventory(
            events
        )
    )

    loader = RealMarketInventoryLoader(
        client=write_client,
        batch_size=arguments.batch_size,
    )

    inserted = loader.persist(
        records=replay_records,
        replay_model_version=(
            arguments.model_version
        ),
    )

    print(
        f'model_version={arguments.model_version}'
    )

    print(f'inserted={inserted}')


def _build_clickhouse_client():
    return Client(
        host=os.getenv(
            'CLICKHOUSE_HOST',
            'clickhouse',
        ),
        port=int(
            os.getenv(
                'CLICKHOUSE_PORT',
                '9000',
            )
        ),
        user=os.getenv(
            'CLICKHOUSE_USER',
            'default',
        ),
        password=os.getenv(
            'CLICKHOUSE_PASSWORD',
            'default',
        ),
    )


def _row_to_event(row: tuple[object, ...]):
    (
        trade_date,
        event_index,
        symbol,
        aggregate_trade_id,
        event_timestamp,
        timestamp_us,
        price,
        base_quantity,
        quote_quantity,
        aggressor_side,
    ) = row

    return UnifiedMarketEvent(
        trade_date=trade_date,
        event_index=int(event_index),
        symbol=str(symbol),
        aggregate_trade_id=int(aggregate_trade_id),
        event_timestamp=event_timestamp,
        timestamp_us=int(timestamp_us),
        price=_as_decimal(price),
        base_quantity=_as_decimal(base_quantity),
        quote_quantity=_as_decimal(quote_quantity),
        aggressor_side=str(aggressor_side),
    )


def _as_decimal(value: object):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


if __name__ == '__main__':
    main()
