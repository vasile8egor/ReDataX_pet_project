CREATE_RAW_DATABASE_Q = '''
CREATE DATABASE IF NOT EXISTS raw
'''


CREATE_SILVER_DATABASE_Q = '''
CREATE DATABASE IF NOT EXISTS silver
'''


CREATE_REAL_MARKET_AGG_TRADES_Q = '''
CREATE TABLE IF NOT EXISTS
    raw.fact_real_market_agg_trades
(
    venue LowCardinality(String),

    market_type LowCardinality(String),

    symbol LowCardinality(String),

    trade_date Date,

    aggregate_trade_id UInt64,

    event_timestamp DateTime64(6, 'UTC'),

    timestamp_us UInt64,

    price Decimal(38, 18),

    base_quantity Decimal(38, 18),

    quote_quantity Decimal(38, 18),

    first_trade_id UInt64,

    last_trade_id UInt64,

    buyer_was_maker UInt8,

    best_price_match UInt8,

    aggressor_side Enum8(
        'buy_base' = 1,
        'sell_base' = -1
    ),

    source_archive_sha256 FixedString(64),

    ingested_at DateTime64(
        6,
        'UTC'
    ) DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(
    ingested_at
)
PARTITION BY
    toYYYYMM(trade_date)
ORDER BY (
    venue,
    market_type,
    symbol,
    aggregate_trade_id
)
'''


INSERT_REAL_MARKET_AGG_TRADES_Q = '''
INSERT INTO raw.fact_real_market_agg_trades (
    venue,
    market_type,
    symbol,
    trade_date,
    aggregate_trade_id,
    event_timestamp,
    timestamp_us,
    price,
    base_quantity,
    quote_quantity,
    first_trade_id,
    last_trade_id,
    buyer_was_maker,
    best_price_match,
    aggressor_side,
    source_archive_sha256
)
VALUES
'''

DELETE_REAL_MARKET_DAY_Q = '''
ALTER TABLE raw.fact_real_market_agg_trades
DELETE WHERE
    venue = %(venue)s
    AND market_type = %(market_type)s
    AND trade_date = %(trade_date)s
    AND symbol IN %(symbols)s
'''

CREATE_REAL_MARKET_INVENTORY_EVENTS_Q = '''
CREATE TABLE IF NOT EXISTS
    silver.fact_real_market_inventory_events
(
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

    delta_btc Decimal(38, 18),
    delta_eth Decimal(38, 18),
    delta_usdt Decimal(38, 18),

    inventory_btc Decimal(38, 18),
    inventory_eth Decimal(38, 18),
    inventory_usdt Decimal(38, 18),

    replay_model_version LowCardinality(String),

    inserted_at DateTime64(
        6,
        'UTC'
    ) DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(
    inserted_at
)
PARTITION BY toYYYYMM(trade_date)
ORDER BY
(
    replay_model_version,
    trade_date,
    event_index
)
'''

INSERT_REAL_MARKET_INVENTORY_EVENTS_Q = '''
INSERT INTO
    silver.fact_real_market_inventory_events
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
    delta_btc,
    delta_eth,
    delta_usdt,
    inventory_btc,
    inventory_eth,
    inventory_usdt,
    replay_model_version
)
VALUES
'''
