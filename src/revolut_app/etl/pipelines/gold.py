from airflow.providers.postgres.hooks.postgres import PostgresHook

from revolut_app.etl.support.bootstrap import (
    read_sql_file,
    run_db_bootstrap_pipeline,
)
from revolut_app.loaders.gold_loader import GoldLayerLoader


def run_gold_transactions_load(target_date_str: str) -> int:
    run_db_bootstrap_pipeline()

    hook = PostgresHook(postgres_conn_id='postgres_main')
    rows = hook.get_records(
        read_sql_file('gold/load_fact_transactions.sql'),
        parameters={'target_date': target_date_str}
    )

    loader = GoldLayerLoader()
    return loader.load_transactions(rows)
