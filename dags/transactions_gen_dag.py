from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from src.revolut_app.core.constants import (
    TRANSACTIONS_DB_FIELDS,
    DEFAULT_ARGS_W_RETRIES
)

with DAG(
    dag_id='revolut_generate_transactions',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False,
    max_active_runs=1
) as dag:

    def generate_and_load(**context):
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        from revolut_app.generators.transactions_gen import MetropolisTransactionGenerator

        pg_hook = PostgresHook(postgres_conn_id='postgres_main')

        target_date = context['ds']
        target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()

        records = pg_hook.get_records(
            "SELECT account_id FROM silver.dim_accounts")
        account_ids = [r[0] for r in records]

        if not account_ids:
            dag.log.info("No accounts found in silver.dim_accounts")
            return

        gen = MetropolisTransactionGenerator()
        gen.run_mcmc()

        all_tx = []

        for acc_id in account_ids:
            for tx in gen.generate_for_account(acc_id, target_dt):
                all_tx.append([tx[f] for f in TRANSACTIONS_DB_FIELDS])

                if len(all_tx) >= 500:
                    pg_hook.insert_rows(
                        table='silver.fact_transactions',
                        rows=all_tx,
                        target_fields=TRANSACTIONS_DB_FIELDS,
                        replace=True,
                        replace_index=['transaction_id']
                    )
                    all_tx = []

        if all_tx:
            pg_hook.insert_rows(
                table='silver.fact_transactions',
                rows=all_tx,
                target_fields=TRANSACTIONS_DB_FIELDS,
                replace=True,
                replace_index=['transaction_id']
            )

    task_generate = PythonOperator(
        task_id='generate_and_load_transactions',
        python_callable=generate_and_load
    )
