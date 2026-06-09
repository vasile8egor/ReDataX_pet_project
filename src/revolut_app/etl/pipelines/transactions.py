from datetime import datetime

from revolut_app.etl.support.bootstrap import run_db_bootstrap_pipeline
from revolut_app.generators.transactions_gen import (
    MetropolisTransactionGenerator
)
from revolut_app.loaders.postgres_loader import PostgresLoader


def run_transaction_generation_pipeline(target_date_str: str):
    run_db_bootstrap_pipeline()

    loader = PostgresLoader()
    gen = MetropolisTransactionGenerator()

    target_dt = datetime.strptime(target_date_str, '%Y-%m-%d').date()

    account_ids = loader.get_account_ids()
    gen.run_mcmc()
    raw_tx_list = gen.generate_all(account_ids, target_dt)

    if raw_tx_list:
        loader.load_raw_transactions(raw_tx_list)

    return len(raw_tx_list)
