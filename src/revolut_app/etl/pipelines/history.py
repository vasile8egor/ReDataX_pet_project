import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from revolut_app.etl.support.bootstrap import run_db_bootstrap_pipeline
from revolut_app.generators.accounts_gen import AccountGenerator
from revolut_app.generators.transactions_gen import MetropolisTransactionGenerator
from revolut_app.loaders.postgres_loader import PostgresLoader


logger = logging.getLogger(__name__)


def run_history_bootstrap_pipeline(
    months_back=6,
    account_sample_size=350,
    flush_batch_size=100000,
    transaction_base_lambda=35
):
    run_db_bootstrap_pipeline()

    loader = PostgresLoader()
    account_generator = AccountGenerator()
    transaction_generator = MetropolisTransactionGenerator(
        base_lambda=transaction_base_lambda
    )
    transaction_generator.run_mcmc()

    current_date = (
        datetime.utcnow() - relativedelta(months=months_back)
    ).date()
    end_date = datetime.utcnow().date()
    total_days = (end_date - current_date).days + 1

    account_ids = []
    account_buffer = []
    transaction_buffer = []
    loaded_accounts = 0
    loaded_transactions = 0
    processed_days = 0

    logger.info(
        'Starting history bootstrap: months_back=%s, start_date=%s, '
        'end_date=%s, account_sample_size=%s, flush_batch_size=%s, '
        'transaction_base_lambda=%s',
        months_back,
        current_date,
        end_date,
        account_sample_size,
        flush_batch_size,
        transaction_base_lambda
    )

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
            logger.info('Flushed %s raw accounts', len(account_buffer))
            account_buffer = []

        if len(transaction_buffer) >= flush_batch_size:
            loader.load_raw_transactions_in_batches(transaction_buffer)
            loaded_transactions += len(transaction_buffer)
            logger.info(
                'Flushed %s raw transactions; total loaded transactions=%s',
                len(transaction_buffer),
                loaded_transactions
            )
            transaction_buffer = []

        processed_days += 1
        if processed_days % 7 == 0 or current_date == end_date:
            logger.info(
                'History bootstrap progress: %s/%s days processed; '
                'known_accounts=%s',
                processed_days,
                total_days,
                len(account_ids)
            )

        current_date += timedelta(days=1)

    if account_buffer:
        loader.load_raw_accounts_in_batches(account_buffer)
        loaded_accounts += len(account_buffer)
        logger.info('Flushed final %s raw accounts', len(account_buffer))

    if transaction_buffer:
        loader.load_raw_transactions_in_batches(transaction_buffer)
        loaded_transactions += len(transaction_buffer)
        logger.info(
            'Flushed final %s raw transactions; total loaded transactions=%s',
            len(transaction_buffer),
            loaded_transactions
        )

    logger.info(
        'History bootstrap finished: loaded_accounts=%s, '
        'loaded_transactions=%s, months_back=%s, transaction_base_lambda=%s',
        loaded_accounts,
        loaded_transactions,
        months_back,
        transaction_base_lambda
    )

    return {
        'loaded_accounts': loaded_accounts,
        'loaded_transactions': loaded_transactions,
        'months_back': months_back,
        'transaction_base_lambda': transaction_base_lambda,
    }
