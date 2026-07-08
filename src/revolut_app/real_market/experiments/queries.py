SELECT_SYMBOL_TRADES_Q = '''
SELECT
    unified.aggregate_trade_id,
    unified.timestamp_us,
    toFloat64(unified.price) AS price,

    if(
        unified.aggressor_side = 'buy_base',
        toInt8(1),
        toInt8(-1)
    ) AS aggressor_sign,

    if(
        unified.symbol = 'ETHBTC',

        toFloat64(unified.quote_quantity)
            * assumeNotNull(marks.btcusdt_mark),

        toFloat64(unified.quote_quantity)
    ) AS notional_usdt

FROM silver.fact_real_market_unified_events
    AS unified

ANY LEFT JOIN
(
    SELECT
        trade_date,
        event_index,
        btcusdt_mark

    FROM silver.fact_real_market_inventory_mtm

    WHERE replay_model_version =
        %(replay_model_version)s

      AND prices_ready = 1
) AS marks
    ON unified.trade_date = marks.trade_date
   AND unified.event_index = marks.event_index

WHERE unified.trade_date = %(trade_date)s
  AND unified.symbol = %(symbol)s

ORDER BY
    unified.timestamp_us,
    unified.aggregate_trade_id
'''

TRADES_SQL = '''
SELECT
    toUnixTimestamp64Micro(event_timestamp) AS timestamp_us,
    toFloat64(price) AS price,
    toFloat64(base_quantity) AS base_quantity,
    toFloat64(quote_quantity) AS quote_quantity,
    if(aggressor_side = 'buy_base', toInt8(1), toInt8(-1)) AS aggressor_sign
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol = %(symbol)s
ORDER BY timestamp_us, aggregate_trade_id
'''

BTC_REF_SQL = '''
SELECT
    toUnixTimestamp64Micro(event_timestamp) AS timestamp_us,
    toFloat64(price) AS price
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol = 'BTCUSDT'
ORDER BY timestamp_us, aggregate_trade_id
'''

SECONDLY_FLOW_SQL = '''
SELECT
    toUInt32(
        intDiv(
            timestamp_us - %(day_start_us)s,
            1000000
        )
    ) AS second_index,
    symbol,
    sumIf(
        toFloat64(quote_quantity),
        aggressor_side = 'buy_base'
    ) AS buy_quote_quantity,
    sumIf(
        toFloat64(quote_quantity),
        aggressor_side = 'sell_base'
    ) AS sell_quote_quantity,
    sum(toFloat64(quote_quantity))
        / sum(toFloat64(base_quantity))
        AS vwap
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol IN %(symbols)s
GROUP BY
    second_index,
    symbol
ORDER BY
    second_index,
    symbol
'''

SECONDLY_NOTIONAL_SQL = '''
SELECT
    toUInt32(
        intDiv(
            timestamp_us - %(day_start_us)s,
            1000000
        )
    ) AS second_index,
    symbol,
    sum(toFloat64(quote_quantity)) AS quote_notional_usdt
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol IN %(symbols)s
GROUP BY
    second_index,
    symbol
ORDER BY
    second_index,
    symbol
'''
