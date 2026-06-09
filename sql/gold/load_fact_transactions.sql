WITH daily_transactions AS (
    SELECT
        transaction_id,
        account_id,
        tx_timestamp,
        amount,
        currency,
        merchant_name,
        bronze_loaded_at,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id
            ORDER BY bronze_loaded_at DESC
        ) AS row_num
    FROM silver.v_transactions
    WHERE tx_timestamp::DATE = %(target_date)s::DATE
)
SELECT
    transaction_id,
    account_id,
    tx_timestamp,
    amount,
    currency,
    merchant_name,
    bronze_loaded_at
FROM daily_transactions
WHERE row_num = 1;
