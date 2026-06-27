CREATE DATABASE IF NOT EXISTS silver;

DROP VIEW IF EXISTS
    silver.v_real_market_unified_events;

CREATE VIEW
    silver.v_real_market_unified_events
AS
SELECT
    row_number() OVER
    (
        PARTITION BY trade_date
        ORDER BY
            timestamp_us,
            multiIf(
                symbol = 'BTCUSDT', 1,
                symbol = 'ETHUSDT', 2,
                symbol = 'ETHBTC', 3,
                99
            ),
            aggregate_trade_id
    ) AS event_index,

    venue,
    market_type,
    trade_date,

    symbol,
    aggregate_trade_id,

    event_timestamp,
    timestamp_us,

    price,
    base_quantity,
    quote_quantity,

    aggressor_side,

    buyer_was_maker,
    best_price_match,

    source_archive_sha256

FROM raw.fact_real_market_agg_trades

WHERE venue = 'binance'
  AND market_type = 'spot'
  AND symbol IN
  (
      'BTCUSDT',
      'ETHUSDT',
      'ETHBTC'
  );