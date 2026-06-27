CREATE DATABASE IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS
    silver.fact_real_market_unified_events
(
    venue LowCardinality(String),
    market_type LowCardinality(String),

    trade_date Date,
    event_index UInt64,

    symbol LowCardinality(String),
    aggregate_trade_id UInt64,

    event_timestamp DateTime64(6, 'UTC'),
    timestamp_us UInt64,

    price Decimal(38, 18),
    base_quantity Decimal(38, 18),
    quote_quantity Decimal(38, 18),

    aggressor_side Enum8(
        'buy_base' = 1,
        'sell_base' = -1
    ),

    buyer_was_maker UInt8,
    best_price_match UInt8,

    source_archive_sha256 FixedString(64),

    materialized_at DateTime64(
        6,
        'UTC'
    ) DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(
    materialized_at
)
PARTITION BY toYYYYMM(trade_date)
ORDER BY
(
    trade_date,
    event_index
);

INSERT INTO
    silver.fact_real_market_unified_events
(
    venue,
    market_type,
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
    buyer_was_maker,
    best_price_match,
    source_archive_sha256
)
SELECT
    venue,
    market_type,
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
    buyer_was_maker,
    best_price_match,
    source_archive_sha256
FROM silver.v_real_market_unified_events
WHERE trade_date = '2025-01-06'
ORDER BY event_index;