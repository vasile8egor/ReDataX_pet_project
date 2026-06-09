from airflow import DAG
from airflow.operators.python import PythonOperator

from revolut_app.core.constants import DEFAULT_ARGS_W_RETRIES
from revolut_app.etl.pipelines.extract import (
    run_accounts_extract_pipeline,
    run_transactions_extract_pipeline,
)

with DAG(
    dag_id='revolut_extract_api',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=['production', 'revolut']
) as dag:

    task_accounts = PythonOperator(
        task_id='extract_accounts',
        python_callable=run_accounts_extract_pipeline,
        op_kwargs={'target_date_str': '{{ ds }}'}
    )

    task_transactions = PythonOperator(
        task_id='extract_transactions',
        python_callable=run_transactions_extract_pipeline,
        op_kwargs={
            'account_ids': task_accounts.output,
            'target_date_str': '{{ ds }}'
        }
    )

    task_accounts >> task_transactions