from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from revolut_app.etl.support.bootstrap import run_db_bootstrap_pipeline
from revolut_app.generators.accounts_gen import AccountGenerator
from revolut_app.generators.transactions_gen import MetropolisTransactionGenerator
from revolut_app.loaders.postgres_loader import PostgresLoader


def run_history_bootstrap_pipeline(
    months_back=6,
    account_sample_size=500,
    flush_batch_size=50000
):
    run_db_bootstrap_pipeline()

    loader = PostgresLoader()
    account_generator = AccountGenerator()
    transaction_generator = MetropolisTransactionGenerator()
    transaction_generator.run_mcmc()

    current_date = (
        datetime.utcnow() - relativedelta(months=months_back)
    ).date()
    end_date = datetime.utcnow().date()

    account_ids = []
    account_buffer = []
    transaction_buffer = []
    loaded_accounts = 0
    loaded_transactions = 0

    while current_date <= end_date:
        daily_accounts = account_generator.generate_daily_batch(current_date)
        account_buffer.extend(daily_accounts)
        account_ids.extend(account['AccountId'] for account in daily_accounts)

        for account_id in account_ids[-account_sample_size:]:
            transaction_buffer.extend(
                transaction_generator.generate_for_account(
                    account_id,
                    current_date
                )
            )

        if len(account_buffer) >= flush_batch_size:
            loader.load_raw_accounts_in_batches(account_buffer)
            loaded_accounts += len(account_buffer)
            account_buffer = []

        if len(transaction_buffer) >= flush_batch_size:
            loader.load_raw_transactions_in_batches(transaction_buffer)
            loaded_transactions += len(transaction_buffer)
            transaction_buffer = []

        current_date += timedelta(days=1)

    if account_buffer:
        loader.load_raw_accounts_in_batches(account_buffer)
        loaded_accounts += len(account_buffer)

    if transaction_buffer:
        loader.load_raw_transactions_in_batches(transaction_buffer)
        loaded_transactions += len(transaction_buffer)

    return {
        'loaded_accounts': loaded_accounts,
        'loaded_transactions': loaded_transactions,
        'months_back': months_back,
    }
