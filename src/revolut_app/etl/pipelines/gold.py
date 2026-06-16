from airflow.providers.postgres.hooks.postgres import PostgresHook

from revolut_app.etl.support.bootstrap import (
    read_sql_file,
    run_db_bootstrap_pipeline,
)
from revolut_app.loaders.gold_loader import GoldLayerLoader


def run_gold_transactions_load(
    target_date_str: str | None = None,
    load_mode: str = 'full',
) -> int:
    run_db_bootstrap_pipeline()

    mode = (load_mode or 'daily').lower()
    hook = PostgresHook(postgres_conn_id='postgres_main')
    loader = GoldLayerLoader()

    if mode == 'full':
        rows = hook.get_records(read_sql_file('gold/load_fact_transactions.sql'))
        loader.truncate_transactions()
        return loader.load_transactions(rows)

    if mode == 'daily':
        if not target_date_str:
            raise ValueError('target_date_str is required for daily gold load')

        rows = hook.get_records(
            read_sql_file('gold/load_fact_transactions_daily.sql'),
            parameters={'target_date': target_date_str}
        )
        loader.delete_transactions_for_date(target_date_str)
        return loader.load_transactions(rows)

    raise ValueError(f'Unsupported gold load mode: {load_mode}')
