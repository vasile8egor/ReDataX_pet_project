from airflow import DAG
from airflow.operators.python import PythonOperator
from revolut_app.core.constants import DEFAULT_ARGS_W_RETRIES
from revolut_app.etl.pipelines.transactions import (
    run_transaction_generation_pipeline
)

with DAG(
    'revolut_generate_transactions',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False
) as dag:
    PythonOperator(
        task_id='generate_and_load_raw_transactions',
        python_callable=run_transaction_generation_pipeline,
        op_kwargs={'target_date_str': '{{ ds }}'},
    )
