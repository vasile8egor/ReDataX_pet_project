import csv
from datetime import date, datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from revolut_app.real_market.binance.parser import (
    iter_binance_spot_agg_trades,
)
from revolut_app.real_market.models import (
    AggressorSide,
    BinanceAggTradeArchiveSpec,
)


def _timestamp_us(year: int, month: int, day: int, hour: int = 0):
    value = datetime(year, month, day, hour, tzinfo=timezone.utc)

    return int(value.timestamp() * 1_000_000)


def _write_zip(
    *,
    path: Path,
    rows: list[list[object]],
):
    csv_path = path.with_suffix('.csv')

    with csv_path.open(
        'w',
        encoding='utf-8',
        newline='',
    ) as output:
        writer = csv.writer(output)
        writer.writerows(rows)

    with ZipFile(
        path,
        mode='w',
        compression=ZIP_DEFLATED,
    ) as archive:
        archive.write(csv_path, arcname=csv_path.name)


def test_parses_microsecond_spot_archive(tmp_path: Path):
    timestamp = _timestamp_us(2025, 1, 6)

    archive_path = (tmp_path / 'BTCUSDT.zip')

    _write_zip(
        path=archive_path,
        rows=[
            [
                100, '100000.5', '0.01', 1000,
                1000, timestamp, 'false', 'true',
            ],
            [
                101, '100001.0', '0.02', 1001,
                1002, timestamp + 100, 'true', 'true',
            ],
        ],
    )

    spec = BinanceAggTradeArchiveSpec(
        symbol='BTCUSDT',
        trade_date=date(2025, 1, 6),
    )

    trades = list(
        iter_binance_spot_agg_trades(
            archive_path=archive_path,
            spec=spec,
        )
    )

    assert len(trades) == 2

    assert trades[0].aggressor_side == (
        AggressorSide.BUY_BASE
    )

    assert trades[1].aggressor_side == (
        AggressorSide.SELL_BASE
    )

    assert trades[0].timestamp_us == (
        timestamp
    )


def test_skips_supported_header(tmp_path: Path):
    timestamp = _timestamp_us(2025, 1, 6)

    archive_path = tmp_path / 'data.zip'

    _write_zip(
        path=archive_path,
        rows=[
            [
                'agg_trade_id',
                'price',
                'quantity',
                'first_trade_id',
                'last_trade_id',
                'timestamp',
                'is_buyer_maker',
                'is_best_match',
            ],
            [
                1,
                '10.0',
                '2.0',
                1,
                1,
                timestamp,
                'false',
                'true',
            ],
        ],
    )

    spec = BinanceAggTradeArchiveSpec(
        symbol='ETHUSDT',
        trade_date=date(2025, 1, 6),
    )

    trades = list(
        iter_binance_spot_agg_trades(
            archive_path=archive_path,
            spec=spec,
        )
    )

    assert len(trades) == 1


def test_rejects_duplicate_aggregate_trade_id(tmp_path: Path):
    timestamp = _timestamp_us(2025, 1, 6)

    archive_path = tmp_path / 'data.zip'

    _write_zip(
        path=archive_path,
        rows=[
            [
                1,
                '10',
                '1',
                1,
                1,
                timestamp,
                'false',
                'true',
            ],
            [
                1,
                '11',
                '1',
                2,
                2,
                timestamp + 1,
                'true',
                'true',
            ],
        ],
    )

    spec = BinanceAggTradeArchiveSpec(
        symbol='ETHUSDT',
        trade_date=date(2025, 1, 6),
    )

    with pytest.raises(
        ValueError,
        match='strictly increasing',
    ):
        list(
            iter_binance_spot_agg_trades(
                archive_path=archive_path,
                spec=spec,
            )
        )


def test_rejects_timestamp_from_another_date(tmp_path: Path):
    timestamp = _timestamp_us(2025, 1, 7)

    archive_path = tmp_path / 'data.zip'

    _write_zip(
        path=archive_path,
        rows=[
            [
                1,
                '10',
                '1',
                1,
                1,
                timestamp,
                'false',
                'true',
            ],
        ],
    )

    spec = BinanceAggTradeArchiveSpec(
        symbol='ETHUSDT',
        trade_date=date(2025, 1, 6),
    )

    with pytest.raises(
        ValueError,
        match='outside',
    ):
        list(
            iter_binance_spot_agg_trades(
                archive_path=archive_path,
                spec=spec,
            )
        )


def test_rejects_millisecond_timestamp_after_2025(tmp_path: Path):
    timestamp_ms = _timestamp_us(2025, 1, 6) // 1_000

    archive_path = tmp_path / 'data.zip'

    _write_zip(
        path=archive_path,
        rows=[
            [
                1,
                '10',
                '1',
                1,
                1,
                timestamp_ms,
                'false',
                'true',
            ],
        ],
    )

    spec = BinanceAggTradeArchiveSpec(
        symbol='ETHUSDT',
        trade_date=date(2025, 1, 6),
    )

    with pytest.raises(
        ValueError,
        match='microsecond timestamp',
    ):
        list(
            iter_binance_spot_agg_trades(
                archive_path=archive_path,
                spec=spec,
            )
        )
