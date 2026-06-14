from datetime import datetime


# dags/*.py: shared Airflow DAG defaults.
DEFAULT_ARGS = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
}

DEFAULT_ARGS_W_RETRIES = {
    **DEFAULT_ARGS,
    'retries': 1,
}


# api/client.py: Revolut Open Banking sandbox endpoints.
REVOLUT_BASE_API = 'https://sandbox-oba-auth.revolut.com'
REVOLUT_AUTH_URL = 'https://sandbox-oba-auth.revolut.com/token'
REVOLUT_UI_URL = 'https://sandbox-oba.revolut.com/ui/index.html'


# loaders/minio_loader.py: MinIO raw landing zone.
BUCKET_RAW = 'raw'


# generators/accounts_gen.py: Faker locales and account volume.
LOCATIONS = [
    'az_AZ', 'bg_BG', 'bn_BD', 'cs_CZ', 'da_DK', 'de_AT', 'de_CH', 'de_DE',
    'el_GR', 'en_PH', 'en_US', 'es_CL', 'es_ES', 'es_MX', 'fa_IR', 'fi_FI',
    'fil_PH', 'fr_CH', 'fr_FR', 'hr_HR', 'hu_HU', 'hy_AM', 'id_ID', 'it_IT',
    'ja_JP', 'ko_KR', 'nl_BE', 'nl_NL', 'no_NO', 'pl_PL', 'pt_BR', 'pt_PT',
    'ro_RO', 'ru_RU', 'sk_SK', 'sl_SI', 'sv_SE', 'th_TH', 'tl_PH', 'tr_TR',
    'vi_VN', 'zh_CN', 'zh_TW'
]

NUM_ACCOUNTS_STARTPACK = 500


# generators/accounts_gen.py: customer demographics.
DOMAINS = [
    'gmail.com',
    'outlook.com',
    'yahoo.com',
    'revolut.com',
    'protonmail.com',
]

MIN_AGE_CLIENT = 18
MAX_AGE_CLIENT = 75


# generators/accounts_gen.py: account and currency distributions.
CURRENCIES = {
    'GBP': 0.70,
    'EUR': 0.20,
    'USD': 0.10,
}

ACCOUNT_TYPES = {
    'Personal': 0.7,
    'Business': 0.15,
    'Premium': 0.10,
    'Metal': 0.05,
}


# generators/accounts_gen.py: acquisition channel metadata.
CUSTOMER_CATEGORIES = {
    'organic': {
        'name': 'Organic Search',
        'prob': 0.4,
        'avg_initial_deposit': 150.0,
        'churn_risk': 'Low',
        'lifetime_value': 'High',
    },
    'referral': {
        'name': 'Referral Program',
        'prob': 0.3,
        'avg_initial_deposit': 250.0,
        'churn_risk': 'Medium',
        'lifetime_value': 'Medium',
    },
    'paid_ads': {
        'name': 'Paid Advertising',
        'prob': 0.3,
        'avg_initial_deposit': 100.0,
        'churn_risk': 'High',
        'lifetime_value': 'Low',
    },
}


# generators/accounts_gen.py: synthetic account scoring config.
SCORING_CONFIG = {
    'churn_risk': {
        'Low': 0.10,
        'Medium': 0.50,
        'High': 0.90,
    },
    'lifetime_value': {
        'Low': 100.0,
        'Medium': 500.0,
        'High': 1000.0,
    },
}


# generators/transactions_gen.py: transaction activity simulation.
ACTIVITY_DISTRIBUTION = [
    0.05, 0.03, 0.02, 0.01, 0.01, 0.02,
    0.10, 0.25, 0.55, 0.85, 0.90, 0.80,
    0.65, 0.55, 0.50, 0.55, 0.65, 0.75,
    0.85, 0.70, 0.50, 0.35, 0.20, 0.10,
]

ITERATIONS_QUANTITY = 8000

TRANSACTION_TYPES = {
    'card_payment': 0.45,
    'internal_transfer': 0.20,
    'bank_transfer_out': 0.12,
    'bank_transfer_in': 0.10,
    'salary': 0.05,
    'cash_withdrawal': 0.04,
    'fee': 0.02,
    'refund': 0.02,
}


# legacy generated-row constants: kept for backward-compatible imports only.
BANK_NAMES = [
    'Barclays', 'HSBC', 'Lloyds', 'NatWest', 'Santander',
    'Nationwide', 'RBS', 'Standard Chartered', 'Monzo', 'Starling',
]

INITIAL_MERCHANTS = [
    'Starbucks', 'Amazon', 'Apple', 'Uber', 'Netflix',
    'Tesco', "Sainsbury's", "McDonald's", 'Zara',
]

ACCOUNTS_DB_FIELDS = [
    'account_id',
    'first_name',
    'last_name',
    'email',
    'phone',
    'date_of_birth',
    'currency',
    'account_type',
    'account_sub_type',
    'acquisition_channel',
    'acquisition_channel_name',
    'initial_deposit',
    'registration_datetime',
    'updated_at',
]

TRANSACTIONS_DB_FIELDS = [
    'transaction_id',
    'account_id',
    'booking_datetime',
    'value_datetime',
    'amount',
    'currency',
    'credit_debit_indicator',
    'status',
    'transaction_information',
    'merchant_name',
    'load_ts',
]

SILVER_ACC_TABLE = 'silver.v_accounts'
SILVER_TX_TABLE = 'silver.v_transactions'
