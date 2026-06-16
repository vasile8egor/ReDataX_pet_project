idempotency_key_query = '''
    SELECT
        event_id,
        idempotency_key,
        transaction_id,
        account_id,
        payload,
        risk_score,
        risk_level,
        loaded_at
    FROM
        bronze.transaction_events_raw
    WHERE
        idempotency_key = %s;
'''

transaction_id_query = '''
    SELECT
        event_id,
        idempotency_key,
        transaction_id,
        account_id,
        payload,
        risk_score,
        risk_level,
        loaded_at
    FROM
        bronze.transaction_events_raw
    WHERE
        transaction_id = %s
    ORDER BY
        loaded_at DESC
    LIMIT 1;
'''

insert_query = '''
    INSERT INTO bronze.transaction_events_raw (
        event_id,
        idempotency_key,
        transaction_id,
        account_id,
        payload,
        risk_score,
        risk_level
    )
    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
'''
