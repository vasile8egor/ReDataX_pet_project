CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.revolut_accounts_raw (
    raw_id SERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_revolut_accounts_raw_payload_gin
ON bronze.revolut_accounts_raw
USING GIN (payload jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_revolut_accounts_raw_account_id
ON bronze.revolut_accounts_raw ((payload->>'AccountId'));
