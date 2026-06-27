CREATE DATABASE IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS
    silver.fact_real_market_inventory_mtm
(
    trade_date Date,
    event_index UInt64,

    event_timestamp DateTime64(6, 'UTC'),
    timestamp_us UInt64,

    replay_model_version LowCardinality(String),

    inventory_btc Decimal(38, 18),
    inventory_eth Decimal(38, 18),
    inventory_usdt Decimal(38, 18),

    btcusdt_mark Nullable(Float64),
    ethusdt_mark Nullable(Float64),

    exposure_btc_usdt Nullable(Float64),
    exposure_eth_usdt Nullable(Float64),
    exposure_usdt Float64,

    net_liquidation_value_usdt Nullable(Float64),
    gross_exposure_usdt Nullable(Float64),

    prices_ready UInt8,

    mark_method LowCardinality(String),

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
);


ALTER TABLE
    silver.fact_real_market_inventory_mtm
DELETE WHERE
    trade_date = '2025-01-06'
    AND replay_model_version =
        'passive-market-maker-unhedged-v1';


INSERT INTO
    silver.fact_real_market_inventory_mtm
(
    trade_date,
    event_index,
    event_timestamp,
    timestamp_us,
    replay_model_version,

    inventory_btc,
    inventory_eth,
    inventory_usdt,

    btcusdt_mark,
    ethusdt_mark,

    exposure_btc_usdt,
    exposure_eth_usdt,
    exposure_usdt,

    net_liquidation_value_usdt,
    gross_exposure_usdt,

    prices_ready,
    mark_method
)
WITH marks_raw AS
(
    SELECT
        trade_date,
        event_index,

        countIf(
            symbol = 'BTCUSDT'
        ) OVER marks_window
            AS btc_price_count,

        countIf(
            symbol = 'ETHUSDT'
        ) OVER marks_window
            AS eth_price_count,

        argMaxIf(
            toFloat64(price),
            event_index,
            symbol = 'BTCUSDT'
        ) OVER marks_window
            AS btcusdt_mark_raw,

        argMaxIf(
            toFloat64(price),
            event_index,
            symbol = 'ETHUSDT'
        ) OVER marks_window
            AS ethusdt_mark_raw

    FROM
        silver.fact_real_market_unified_events

    WHERE trade_date = '2025-01-06'

    WINDOW marks_window AS
    (
        PARTITION BY trade_date
        ORDER BY event_index
        ROWS BETWEEN
            UNBOUNDED PRECEDING
            AND CURRENT ROW
    )
),
marks AS
(
    SELECT
        trade_date,
        event_index,

        if(
            btc_price_count > 0,
            btcusdt_mark_raw,
            NULL
        ) AS btcusdt_mark,

        if(
            eth_price_count > 0,
            ethusdt_mark_raw,
            NULL
        ) AS ethusdt_mark

    FROM marks_raw
),
valued AS
(
    SELECT
        inventory.trade_date,
        inventory.event_index,
        inventory.event_timestamp,
        inventory.timestamp_us,
        inventory.replay_model_version,

        inventory.inventory_btc,
        inventory.inventory_eth,
        inventory.inventory_usdt,

        marks.btcusdt_mark,
        marks.ethusdt_mark,

        if(
            isNotNull(marks.btcusdt_mark),
            toFloat64(
                inventory.inventory_btc
            ) * marks.btcusdt_mark,
            NULL
        ) AS exposure_btc_usdt,

        if(
            isNotNull(marks.ethusdt_mark),
            toFloat64(
                inventory.inventory_eth
            ) * marks.ethusdt_mark,
            NULL
        ) AS exposure_eth_usdt,

        toFloat64(
            inventory.inventory_usdt
        ) AS exposure_usdt,

        (
            isNotNull(marks.btcusdt_mark)
            AND isNotNull(marks.ethusdt_mark)
        ) AS prices_ready

    FROM
        silver.fact_real_market_inventory_events
            AS inventory

    INNER JOIN marks
        ON inventory.trade_date =
           marks.trade_date
       AND inventory.event_index =
           marks.event_index

    WHERE inventory.trade_date =
        '2025-01-06'

      AND inventory.replay_model_version =
        'passive-market-maker-unhedged-v1'
)

SELECT
    trade_date,
    event_index,
    event_timestamp,
    timestamp_us,
    replay_model_version,

    inventory_btc,
    inventory_eth,
    inventory_usdt,

    btcusdt_mark,
    ethusdt_mark,

    exposure_btc_usdt,
    exposure_eth_usdt,
    exposure_usdt,

    if(
        prices_ready,
        exposure_btc_usdt
            + exposure_eth_usdt
            + exposure_usdt,
        NULL
    ) AS net_liquidation_value_usdt,

    if(
        prices_ready,
        abs(exposure_btc_usdt)
            + abs(exposure_eth_usdt)
            + abs(exposure_usdt),
        NULL
    ) AS gross_exposure_usdt,

    prices_ready,

    'last-trade-carry-forward-v1'
        AS mark_method

FROM valued
ORDER BY event_index;
