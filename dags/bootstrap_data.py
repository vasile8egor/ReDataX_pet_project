import io
import pandas as pd
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from src.revolut_app.core.constants import (
    DEFAULT_ARGS,
    ACCOUNTS_DB_FIELDS,
    TRANSACTIONS_DB_FIELDS
)


def upload_via_copy(df, table_name, pg_hook):
    if df.empty:
        return

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, sep='\t')
    buffer.seek(0)

    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SET search_path TO silver, public;")
        only_table_name = table_name.split('.')[-1]

        cursor.copy_from(
            buffer,
            only_table_name,
            sep='\t',
            columns=list(df.columns)
        )
        conn.commit()
        print(f"Successfully loaded {len(df)} rows into {table_name}")
    except Exception as e:
        conn.rollback()
        print(f"Error loading into {table_name}: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()


def bootstrap_history(**context):
    from revolut_app.generators.new_accounts_gen import NewAccountGenerator
    from revolut_app.generators.transactions_gen import MetropolisTransactionGenerator
    from dateutil.relativedelta import relativedelta
    import pandas as pd

    pg_hook = PostgresHook(postgres_conn_id='postgres_main')
    pg_hook.run(
        "TRUNCATE silver.fact_transactions, silver.dim_accounts CASCADE;", autocommit=True)

    acc_gen = NewAccountGenerator()
    tx_gen = MetropolisTransactionGenerator()

    current_date = (datetime.now() - relativedelta(months=6)).date()
    end_date = datetime.now().date()

    local_account_ids = []
    acc_buffer = []
    tx_buffer = []

    print(f"Starting bootstrap from {current_date}...")

    while current_date <= end_date:

        n_new = acc_gen.get_daily_count(current_date)
        for _ in range(n_new):
            acc, _ = acc_gen.generate_new_client(current_date)
            local_account_ids.append(acc['account_id'])

            acc_buffer.append({f: acc.get(f) for f in ACCOUNTS_DB_FIELDS})

        if local_account_ids:
            tx_gen.run_mcmc()
            sample_ids = local_account_ids[-500:]
            for acc_id in sample_ids:
                for tx in tx_gen.generate_for_account(acc_id, current_date):
                    tx_buffer.append({f: tx.get(f)
                                     for f in TRANSACTIONS_DB_FIELDS})

        if current_date.day == 1:
            if acc_buffer:
                upload_via_copy(pd.DataFrame(acc_buffer),
                                'silver.dim_accounts', pg_hook)
                acc_buffer = []
            if tx_buffer:
                upload_via_copy(pd.DataFrame(tx_buffer),
                                'silver.fact_transactions', pg_hook)
                tx_buffer = []
            print(f"Intermediate flush at {current_date} done.")

        current_date += timedelta(days=1)

    if acc_buffer:
        upload_via_copy(pd.DataFrame(acc_buffer),
                        'silver.dim_accounts', pg_hook)

    if tx_buffer:
        upload_via_copy(pd.DataFrame(tx_buffer),
                        'silver.fact_transactions', pg_hook)

    print("Bootstrap finished successfully!")


with DAG(
    dag_id='revolut_bootstrap_history',
    default_args=DEFAULT_ARGS,
    schedule_interval=None,
    catchup=False
) as dag:
    PythonOperator(
        task_id='run_optimized_bootstrap',
        python_callable=bootstrap_history
    )
