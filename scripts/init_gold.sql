CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_transactions (
    transaction_id UInt64,
    account_id String,
    amount Decimal(18, 4),
    currency String,
    timestamp DateTime64(3, 'UTC')
) 
ENGINE = MergeTree() 
ORDER BY (timestamp, transaction_id);