from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from clickhouse_driver import Client

from revolut_app.real_market.binance.downloader import (
    calculate_sha256,
)
from revolut_app.real_market.binance.parser import (
    iter_binance_spot_agg_trades,
)
from revolut_app.real_market.loaders.clickhouse import (
    RealMarketAggTradesLoader,
    build_real_market_record,
)
from revolut_app.real_market.models import (
    BinanceAggTradeArchiveSpec,
)


DEFAULT_DATA_DIRECTORY = Path(
    '/opt/airflow/data/real_market/binance'
)

DEFAULT_SYMBOLS = (
    'BTCUSDT',
    'ETHUSDT',
    'ETHBTC',
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--date',
        required=True,
        type=date.fromisoformat,
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        default=list(DEFAULT_SYMBOLS),
    )

    parser.add_argument(
        '--data-directory',
        type=Path,
        default=DEFAULT_DATA_DIRECTORY,
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50_000,
    )

    arguments = parser.parse_args()

    client = Client(
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

    loader = RealMarketAggTradesLoader(
        client=client,
        batch_size=arguments.batch_size,
    )

    specs = [
        BinanceAggTradeArchiveSpec(
            symbol=symbol,
            trade_date=arguments.date,
        )
        for symbol in arguments.symbols
    ]

    archive_paths = {}

    for spec in specs:
        archive_path = (
            arguments.data_directory
            / 'spot'
            / 'daily'
            / 'aggTrades'
            / spec.symbol
            / spec.filename
        )

        if not archive_path.exists():
            raise FileNotFoundError(
                f'Archive not found: {archive_path}'
            )

        archive_paths[spec.symbol] = archive_path

    loader.delete_day(
        trade_date=arguments.date,
        symbols=[spec.symbol for spec in specs],
    )

    total_inserted = 0

    for spec in specs:
        archive_path = archive_paths[spec.symbol]

        archive_sha256 = calculate_sha256(
            archive_path
        )

        records = (
            build_real_market_record(
                trade=trade,
                trade_date=spec.trade_date,
                archive_sha256=archive_sha256,
            )
            for trade in (
                iter_binance_spot_agg_trades(
                    archive_path=archive_path,
                    spec=spec,
                )
            )
        )

        inserted = loader.persist_records(
            records
        )

        total_inserted += inserted

        print(
            f'symbol={spec.symbol} inserted={inserted}'
        )

    print(
        f'total_inserted={total_inserted}'
    )


if __name__ == '__main__':
    main()
