CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.transaction_events_raw (
	event_id TEXT PRIMARY KEY,
	idempotency_key 			TEXT NOT NULL UNIQUE,
	transaction_id 				TEXT NOT NULL,
	account_id 					TEXT NOT NULL,
	payload						JSONB NOT NULL,
	risk_score 					NUMERIC(5, 4) NOT NULL,
	risk_level					TEXT NOT NULL,
	source						TEXT NOT NULL DEFAULT 'api',
	loaded_at					TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transaction_events_raw_transaction_id
	ON bronze.transaction_events_raw(transaction_id);

CREATE INDEX IF NOT EXISTS idx_transaction_events_raw_account_id
	ON bronze.transaction_events_raw(account_id);

CREATE INDEX IF NOT EXISTS idx_transaction_events_raw_loaded_at
	ON bronze.transaction_events_raw(loaded_at);

CREATE INDEX if NOT EXISTS idx_transaction_events_raw_payload_gin
	ON bronze.transaction_events_raw USING GIN (payload);
