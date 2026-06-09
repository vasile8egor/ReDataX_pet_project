CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_transactions (
    transaction_id String,
    account_id String,
    tx_timestamp DateTime64(3, 'UTC'),
    amount Decimal(18, 4),
    currency String,
    merchant_name Nullable(String),
    bronze_loaded_at DateTime64(3, 'UTC'),
    gold_loaded_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(gold_loaded_at)
ORDER BY (tx_timestamp, transaction_id);
