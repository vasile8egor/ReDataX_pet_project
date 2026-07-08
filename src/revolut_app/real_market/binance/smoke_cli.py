import argparse
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from revolut_app.real_market.binance.downloader import (
    DEFAULT_DOWNLOAD_ATTEMPTS,
    DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    download_binance_agg_trades_archive,
)
from revolut_app.real_market.binance.parser import (
    iter_binance_spot_agg_trades,
)
from revolut_app.real_market.binance.validation import (
    summarize_binance_agg_trades,
)
from revolut_app.real_market.models import (
    BinanceAggTradeArchiveSpec,
)


DEFAULT_SYMBOLS = (
    'BTCUSDT',
    'ETHUSDT',
    'ETHBTC',
)


def main() -> None:
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
        default=Path('data/real_market/binance'),
    )

    parser.add_argument(
        '--download-timeout-seconds',
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    )

    parser.add_argument(
        '--download-attempts',
        type=int,
        default=DEFAULT_DOWNLOAD_ATTEMPTS,
    )

    parser.add_argument(
        '--retry-backoff-seconds',
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
    )

    arguments = parser.parse_args()

    for symbol in arguments.symbols:
        spec = BinanceAggTradeArchiveSpec(
            symbol=symbol,
            trade_date=arguments.date,
        )

        print()
        print(
            f'Downloading '
            f'{spec.symbol} '
            f'{spec.trade_date}'
        )

        downloaded = (
            download_binance_agg_trades_archive(
                spec=spec,
                output_directory=arguments.data_directory,
                timeout_seconds=arguments.download_timeout_seconds,
                download_attempts=arguments.download_attempts,
                retry_backoff_seconds=arguments.retry_backoff_seconds,
            )
        )

        summary = summarize_binance_agg_trades(
            trades=(
                iter_binance_spot_agg_trades(
                    archive_path=downloaded.archive_path,
                    spec=spec,
                )
            ),
            spec=spec,
            archive_sha256=downloaded.actual_sha256,
        )

        print(
            json.dumps(
                asdict(summary),
                ensure_ascii=False,
                indent=2,
                default=_json_default,
            )
        )


def _json_default(
    value: object,
) -> str:
    if isinstance(value, Decimal):
        return format(value, 'f')

    if isinstance(value, date):
        return value.isoformat()

    raise TypeError(
        f'Cannot serialize {type(value)!r}'
    )


if __name__ == '__main__':
    main()
