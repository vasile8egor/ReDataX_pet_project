CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.revolut_transactions_raw (
    raw_id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_revolut_transactions_raw_payload_gin
ON bronze.revolut_transactions_raw
USING GIN (payload jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_revolut_transactions_raw_account_id
ON bronze.revolut_transactions_raw ((payload->>'account_id'));

CREATE INDEX IF NOT EXISTS idx_revolut_transactions_raw_created_at
ON bronze.revolut_transactions_raw ((payload->>'created_at'));

CREATE INDEX IF NOT EXISTS idx_revolut_transactions_raw_loaded_at
ON bronze.revolut_transactions_raw (loaded_at);
