CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE VIEW silver.v_accounts AS
SELECT
    payload->>'AccountId' AS account_id,
    payload->>'Currency' AS currency,
    payload->>'AccountType' AS account_type,
    payload->>'AccountSubType' AS account_sub_type,
    payload->'Customer'->>'FirstName' AS first_name,
    payload->'Customer'->>'LastName' AS last_name,
    payload->'Customer'->>'Email' AS email,
    payload->'Customer'->>'Phone' AS phone,
    (payload->'Customer'->>'DateOfBirth')::DATE AS date_of_birth,
    payload->'Acquisition'->>'Channel' AS acquisition_channel,
    payload->'Acquisition'->>'ChannelName' AS acquisition_channel_name,
    (payload->'Acquisition'->>'InitialDeposit')::NUMERIC(15, 4)
        AS initial_deposit,
    (payload->'Acquisition'->>'RegistrationDatetime')::TIMESTAMP
        AS registration_datetime,
    payload->'Scoring'->>'ChurnRisk' AS churn_risk,
    (payload->'Scoring'->>'ChurnRiskScore')::NUMERIC(5, 2)
        AS churn_risk_score,
    payload->'Scoring'->>'LifetimeValue' AS lifetime_value,
    (payload->'Scoring'->>'LifetimeValueAmount')::NUMERIC(18, 2)
        AS ltv_amount,
    (payload->>'UpdatedAt')::TIMESTAMP AS updated_at,
    loaded_at AS bronze_loaded_at
FROM bronze.revolut_accounts_raw;
