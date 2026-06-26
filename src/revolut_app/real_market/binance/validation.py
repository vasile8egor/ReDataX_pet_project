from decimal import Decimal
from typing import Iterable

from revolut_app.real_market.models import (
    AggressorSide,
    BinanceAggTrade,
    BinanceAggTradeArchiveSpec,
    BinanceAggTradeArchiveSummary,
)


def summarize_binance_agg_trades(
    *,
    trades: Iterable[BinanceAggTrade],
    spec: BinanceAggTradeArchiveSpec,
    archive_sha256: str,
) -> BinanceAggTradeArchiveSummary:
    row_count = 0

    first_id: int | None = None
    last_id: int | None = None

    first_timestamp_us: int | None = None
    last_timestamp_us: int | None = None

    previous_id: int | None = None
    missing_ids = 0

    buy_count = 0
    sell_count = 0

    total_base_quantity = Decimal('0')
    total_quote_notional = Decimal('0')

    for trade in trades:
        if trade.symbol != spec.symbol:
            raise ValueError(
                'Trade symbol does not match archive specification:'
                f'expected={spec.symbol}, '
                f'actual={trade.symbol}'
            )

        if first_id is None:
            first_id = trade.aggregate_trade_id

            first_timestamp_us = trade.timestamp_us

        if (
            previous_id is not None
            and trade.aggregate_trade_id > previous_id + 1
        ):
            missing_ids += (
                trade.aggregate_trade_id - previous_id - 1
            )

        previous_id = trade.aggregate_trade_id

        last_id = trade.aggregate_trade_id
        last_timestamp_us = trade.timestamp_us

        if trade.aggressor_side == AggressorSide.BUY_BASE:
            buy_count += 1
        else:
            sell_count += 1

        total_base_quantity += trade.quantity

        total_quote_notional += trade.quote_quantity

        row_count += 1

    if row_count == 0:
        raise ValueError(
            'Binance archive contains no aggTrades'
        )

    assert first_id is not None
    assert last_id is not None
    assert first_timestamp_us is not None
    assert last_timestamp_us is not None

    if buy_count + sell_count != row_count:
        raise AssertionError(
            'Aggressor-side counts do not match row count'
        )

    return BinanceAggTradeArchiveSummary(
        symbol=spec.symbol,
        trade_date=spec.trade_date,
        row_count=row_count,
        first_aggregate_trade_id=first_id,
        last_aggregate_trade_id=last_id,
        first_timestamp_us=first_timestamp_us,
        last_timestamp_us=last_timestamp_us,
        buy_aggressor_count=buy_count,
        sell_aggressor_count=sell_count,
        missing_aggregate_trade_ids=missing_ids,
        total_base_quantity=total_base_quantity,
        total_quote_notional=total_quote_notional,
        archive_sha256=archive_sha256,
    )
