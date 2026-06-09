CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE VIEW silver.v_transactions AS
SELECT
    payload->>'transaction_id' AS transaction_id,
    COALESCE(
        payload->>'account_id',
        payload->>'source_account_id'
    ) AS account_id,
    (payload->>'amount')::NUMERIC(15, 4) AS amount,
    payload->>'currency' AS currency,
    (payload->>'created_at')::TIMESTAMP AS tx_timestamp,
    payload->>'credit_debit_indicator' AS credit_debit_indicator,
    payload->>'status' AS status,
    payload->>'transaction_information' AS transaction_information,
    payload->>'merchant_name' AS merchant_name,
    loaded_at AS bronze_loaded_at
FROM bronze.revolut_transactions_raw;
