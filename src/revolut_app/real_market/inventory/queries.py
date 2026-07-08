SELECT_EVENTS_Q = '''
SELECT
    trade_date,
    event_index,
    symbol,
    aggregate_trade_id,
    event_timestamp,
    timestamp_us,
    price,
    base_quantity,
    quote_quantity,
    toString(aggressor_side)
FROM silver.fact_real_market_unified_events
WHERE trade_date = %(trade_date)s
ORDER BY event_index
'''
