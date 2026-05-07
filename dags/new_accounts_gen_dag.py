from airflow import DAG
from airflow.operators.python import PythonOperator

from src.revolut_app.core.constants import (
    ACCOUNTS_DB_FIELDS,
    TRANSACTIONS_DB_FIELDS,
    DEFAULT_ARGS_W_RETRIES
)

with DAG(
    dag_id='revolut_generate_new_accounts',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False,
    tags=['generation', 'accounts']
) as dag:

    def generate_and_insert(**context):
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        from revolut_app.generators.new_accounts_gen import NewAccountGenerator

        pg_hook = PostgresHook(postgres_conn_id='postgres_main')
        target_date = context['dag_run'].logical_date.date()

        generator = NewAccountGenerator()
        n_new = generator.get_daily_count(target_date)

        if n_new == 0:
            dag.log.info(f"No new accounts to generate for {target_date}")
            return

        accounts = []
        transactions = []

        for _ in range(n_new):
            acc, tx = generator.generate_new_client(target_date)

            accounts.append([acc.get(field) for field in ACCOUNTS_DB_FIELDS])
            transactions.append([tx.get(field)
                                for field in TRANSACTIONS_DB_FIELDS])

        pg_hook.insert_rows(
            table='silver.dim_accounts',
            rows=accounts,
            target_fields=ACCOUNTS_DB_FIELDS,
            replace=True,
            replace_index=['account_id']
        )

        pg_hook.insert_rows(
            table='silver.fact_transactions',
            rows=transactions,
            target_fields=TRANSACTIONS_DB_FIELDS,
            replace=True,
            replace_index=['transaction_id']
        )

    generate_task = PythonOperator(
        task_id='generate_new_accounts_task',
        python_callable=generate_and_insert
    )
