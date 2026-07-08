import logging
import os
from typing import Any, Dict, List, Optional

from airflow.models import Variable

from revolut_app.api import RevolutClient
from revolut_app.etl.support.bootstrap import run_db_bootstrap_pipeline
from revolut_app.loaders.minio_loader import MinioRawLoader
from revolut_app.loaders.postgres_loader import PostgresLoader

logger = logging.getLogger(__name__)


REVOLUT_VARIABLE_NAMES = (
    'REVOLUT_CLIENT_ID',
    'REVOLUT_FINANCIAL_ID',
    'REVOLUT_PRIVATE_KEY_PATH',
    'REVOLUT_TRANSPORT_CERT_PATH',
    'REVOLUT_KID',
    'REVOLUT_REDIRECT_URL',
    'REVOLUT_REFRESH_TOKEN',
)


def _get_airflow_or_env_value(name: str):
    return Variable.get(name, default_var=os.getenv(name))


def _build_client():
    values = {
        name: _get_airflow_or_env_value(name)
        for name in REVOLUT_VARIABLE_NAMES
    }

    client = RevolutClient(
        client_id=values['REVOLUT_CLIENT_ID'],
        financial_id=values['REVOLUT_FINANCIAL_ID'],
        private_key_path=values['REVOLUT_PRIVATE_KEY_PATH'],
        transport_cert_path=values['REVOLUT_TRANSPORT_CERT_PATH'],
        kid=values['REVOLUT_KID'],
        redirect_url=values['REVOLUT_REDIRECT_URL'],
    )
    client.set_refresh_token(values['REVOLUT_REFRESH_TOKEN'])
    return client


def _extract_accounts_from_response(response: Dict[str, Any]):
    return response.get('Data', {}).get('Account', [])


def _extract_transactions_from_response(
    response: Dict[str, Any]
):
    return response.get('Data', {}).get('Transaction', [])


def _with_source_account_id(
    transactions: List[Dict[str, Any]],
    account_id: str
):
    return [
        {**transaction, 'source_account_id': account_id}
        for transaction in transactions
    ]


def run_accounts_extract_pipeline(target_date_str: str):
    run_db_bootstrap_pipeline()

    client = _build_client()
    minio_loader = MinioRawLoader()
    loader = PostgresLoader()

    accounts_response = client.get_accounts()
    minio_loader.load_json(
        f'accounts/{target_date_str}/accounts.json',
        accounts_response
    )
    accounts = _extract_accounts_from_response(accounts_response)
    loader.load_raw_accounts(accounts)

    logger.info(
        'Loaded %s raw Revolut accounts for %s',
        len(accounts),
        target_date_str
    )
    return [account['AccountId'] for account in accounts if account.get('AccountId')]


def run_transactions_extract_pipeline(
    account_ids: List[str],
    target_date_str: str
):
    run_db_bootstrap_pipeline()

    client = _build_client()
    minio_loader = MinioRawLoader()
    loader = PostgresLoader()
    loaded_count = 0

    for account_id in account_ids:
        try:
            transactions_response = client.get_transactions(account_id)
            minio_loader.load_json(
                f'transactions/{target_date_str}/{account_id}.json',
                transactions_response
            )
            transactions = _extract_transactions_from_response(
                transactions_response
            )
            loader.load_raw_transactions(
                _with_source_account_id(transactions, account_id)
            )
            loaded_count += len(transactions)
        except Exception:
            logger.exception(
                'Failed to extract transactions for account %s',
                account_id
            )

    logger.info(
        'Loaded %s raw Revolut transactions for %s',
        loaded_count,
        target_date_str
    )
    return loaded_count
