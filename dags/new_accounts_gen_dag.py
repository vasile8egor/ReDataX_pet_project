from airflow import DAG
from airflow.operators.python import PythonOperator
from revolut_app.core.constants import DEFAULT_ARGS_W_RETRIES
from revolut_app.etl.pipelines.accounts import run_accounts_generation_pipeline

with DAG(
    'revolut_generate_new_accounts',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False
) as dag:
    PythonOperator(
        task_id='generate_and_load_raw_accounts',
        python_callable=run_accounts_generation_pipeline,
        op_kwargs={'target_date_str': '{{ ds }}'},
    )
