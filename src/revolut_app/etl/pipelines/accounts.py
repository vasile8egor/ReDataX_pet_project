from datetime import datetime

from revolut_app.etl.support.bootstrap import run_db_bootstrap_pipeline
from revolut_app.generators.accounts_gen import AccountGenerator
from revolut_app.loaders.postgres_loader import PostgresLoader


def run_accounts_generation_pipeline(target_date_str: str):
    run_db_bootstrap_pipeline()

    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()

    generator = AccountGenerator()
    loader = PostgresLoader()

    raw_accounts = generator.generate_daily_batch(target_date)
    loader.load_raw_accounts(raw_accounts)

    return len(raw_accounts)
