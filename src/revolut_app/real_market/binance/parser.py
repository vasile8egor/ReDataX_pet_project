import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from pathlib import Path
from typing import Iterator
from zipfile import BadZipFile, ZipFile

from revolut_app.real_market.models import (
    AggressorSide,
    BinanceAggTrade,
    BinanceAggTradeArchiveSpec,
)


MICROSECOND_ARCHIVE_START_DATE = date(2025, 1, 1)

EXPECTED_SPOT_AGG_TRADE_COLUMNS = 8


def iter_binance_spot_agg_trades(
    *,
    archive_path: Path,
    spec: BinanceAggTradeArchiveSpec,
):
    try:
        archive = ZipFile(
            archive_path,
            mode='r',
        )
    except BadZipFile as error:
        raise ValueError(
            f'Invalid Binance ZIP archive: {archive_path}'
        ) from error

    with archive:
        csv_members = [
            member
            for member in archive.infolist()
            if not member.is_dir()
            and member.filename.lower().endswith(
                '.csv'
            )
        ]

        if len(csv_members) != 1:
            raise ValueError(
                'Expected exactly one CSV file '
                f'inside Binance archive: path={archive_path},'
                f'members={[m.filename for m in csv_members]}'
            )

        member = csv_members[0]

        with archive.open(
            member,
            mode='r',
        ) as binary_stream:
            with TextIOWrapper(
                binary_stream,
                encoding='utf-8-sig',
                newline='',
            ) as text_stream:
                reader = csv.reader(
                    text_stream
                )

                previous_aggregate_trade_id: (
                    int | None
                ) = None

                previous_timestamp_us: (
                    int | None
                ) = None

                first_non_empty_row = True

                for line_number, raw_row in enumerate(
                    reader,
                    start=1,
                ):
                    row = [
                        value.strip()
                        for value in raw_row
                    ]

                    if not row or not any(row):
                        continue

                    if first_non_empty_row:
                        first_non_empty_row = False

                        if _is_header_row(row):
                            continue

                    trade = _parse_row(
                        row=row,
                        line_number=line_number,
                        spec=spec,
                    )

                    if (
                        previous_aggregate_trade_id
                        is not None
                        and trade.aggregate_trade_id
                        <= previous_aggregate_trade_id
                    ):
                        raise ValueError(
                            'Aggregate trade IDs must be strictly increasing:'
                            f'line={line_number}, '
                            f'previous={previous_aggregate_trade_id},'
                            f'current={trade.aggregate_trade_id}'
                        )

                    if (
                        previous_timestamp_us
                        is not None
                        and trade.timestamp_us
                        < previous_timestamp_us
                    ):
                        raise ValueError(
                            'Trade timestamps must be non-decreasing: '
                            f'line={line_number}, '
                            f'previous={previous_timestamp_us},'
                            f'current={trade.timestamp_us}'
                        )

                    previous_aggregate_trade_id = (
                        trade.aggregate_trade_id
                    )

                    previous_timestamp_us = (
                        trade.timestamp_us
                    )

                    yield trade


def _parse_row(
    *,
    row: list[str],
    line_number: int,
    spec: BinanceAggTradeArchiveSpec,
):
    if len(row) != (
        EXPECTED_SPOT_AGG_TRADE_COLUMNS
    ):
        raise ValueError(
            'Unexpected Binance spot aggTrades column count: '
            f'line={line_number}, '
            f'expected={EXPECTED_SPOT_AGG_TRADE_COLUMNS}, '
            f'actual={len(row)}, '
            f'row={row!r}'
        )

    try:
        aggregate_trade_id = int(row[0])
        price = Decimal(row[1])
        quantity = Decimal(row[2])
        first_trade_id = int(row[3])
        last_trade_id = int(row[4])
        raw_timestamp = int(row[5])

        buyer_was_maker = _parse_boolean(
            row[6]
        )

        best_price_match = _parse_boolean(
            row[7]
        )
    except (
        ValueError,
        InvalidOperation,
    ) as error:
        raise ValueError(
            'Cannot parse Binance aggTrade row: '
            f'line={line_number}, '
            f'row={row!r}'
        ) from error

    if aggregate_trade_id < 0:
        raise ValueError(
            'aggregate_trade_id cannot '
            f'be negative: line={line_number}'
        )

    if price <= 0:
        raise ValueError(
            'price must be positive: '
            f'line={line_number}, '
            f'price={price}'
        )

    if quantity <= 0:
        raise ValueError(
            'quantity must be positive: '
            f'line={line_number}, '
            f'quantity={quantity}'
        )

    if first_trade_id > last_trade_id:
        raise ValueError(
            'first_trade_id cannot exceed last_trade_id: '
            f'line={line_number}, '
            f'first={first_trade_id}, '
            f'last={last_trade_id}'
        )

    timestamp_us = _normalize_timestamp_us(
        raw_timestamp=raw_timestamp,
        trade_date=spec.trade_date,
    )

    actual_date = datetime.fromtimestamp(
        timestamp_us / 1_000_000,
        tz=timezone.utc,
    ).date()

    if actual_date != spec.trade_date:
        raise ValueError(
            'Trade timestamp is outside the requested UTC date: '
            f'line={line_number}, '
            f'expected={spec.trade_date}, '
            f'actual={actual_date}, '
            f'timestamp_us={timestamp_us}'
        )

    aggressor_side = (
        AggressorSide.SELL_BASE
        if buyer_was_maker
        else AggressorSide.BUY_BASE
    )

    return BinanceAggTrade(
        symbol=spec.symbol,
        aggregate_trade_id=(
            aggregate_trade_id
        ),
        price=price,
        quantity=quantity,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        timestamp_us=timestamp_us,
        buyer_was_maker=(
            buyer_was_maker
        ),
        best_price_match=(
            best_price_match
        ),
        aggressor_side=aggressor_side,
    )


def _normalize_timestamp_us(
    *,
    raw_timestamp: int,
    trade_date: date,
):
    if trade_date >= (
        MICROSECOND_ARCHIVE_START_DATE
    ):
        if not (
            10**15
            <= raw_timestamp
            < 10**17
        ):
            raise ValueError(
                'Expected microsecond timestamp '
                'for Binance spot archive from 2025-01-01 onwards: '
                f'date={trade_date}, '
                f'value={raw_timestamp}'
            )

        return raw_timestamp

    if not (
        10**12
        <= raw_timestamp
        < 10**15
    ):
        raise ValueError(
            'Expected millisecond timestamp '
            'for Binance spot archive before 2025-01-01: '
            f'date={trade_date}, '
            f'value={raw_timestamp}'
        )

    return raw_timestamp * 1_000


def _parse_boolean(
    value: str,
):
    normalized = value.strip().lower()

    if normalized in {
        'true',
        '1',
    }:
        return True

    if normalized in {
        'false',
        '0',
    }:
        return False

    raise ValueError(
        f'Unsupported boolean value: {value!r}'
    )


def _is_header_row(
    row: list[str],
):
    first_value = ''.join(
        character
        for character in row[0].lower()
        if character.isalnum()
    )

    return first_value in {
        'aggtradeid',
        'aggregatetradeid',
    }
