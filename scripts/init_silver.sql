CREATE SCHEMA IF NOT EXISTS silver;

SET search_path TO silver, public;

CREATE TABLE IF NOT EXISTS silver.dim_accounts (
    account_id                  VARCHAR(40) PRIMARY KEY,
    first_name                  VARCHAR(50),
    last_name                   VARCHAR(50),
    email                       VARCHAR(100),
    phone                       VARCHAR(20),
    date_of_birth               DATE,
    currency                    VARCHAR(3),
    account_type                VARCHAR(50),
    account_sub_type            VARCHAR(50),
    acquisition_channel         VARCHAR(50),
    acquisition_channel_name    VARCHAR(100),
    initial_deposit             NUMERIC(15,4),
    registration_datetime       TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    churn_risk                  VARCHAR(20),
    churn_risk_score            DECIMAL(5, 2),
    lifetime_value              VARCHAR(20),
    ltv_amount                  DECIMAL(18, 2)
);

CREATE TABLE IF NOT EXISTS silver.fact_transactions (
    transaction_id              VARCHAR(100) PRIMARY KEY,
    account_id                  VARCHAR(40),
    booking_datetime            TIMESTAMP NOT NULL,
    value_datetime              TIMESTAMP, 
    amount                      NUMERIC(15,4) NOT NULL,
    currency                    VARCHAR(3) NOT NULL,
    credit_debit_indicator      TEXT,
    status                      TEXT,
    transaction_information     TEXT,
    merchant_name               TEXT,
    load_ts                     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$ 
BEGIN 
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'silver' AND table_name = 'fact_transactions') THEN
        RAISE NOTICE 'Table silver.fact_transactions created successfully';
    ELSE
        RAISE WARNING 'Table silver.fact_transactions MISSING';
    END IF;
END $$;