from airflow import DAG
from airflow.operators.python import PythonOperator
from revolut_app.core.constants import DEFAULT_ARGS_W_RETRIES
from revolut_app.etl.pipelines.history import run_history_bootstrap_pipeline

with DAG(
    'revolut_bootstrap_history',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False
) as dag:
    PythonOperator(
        task_id='bootstrap_history_to_bronze',
        python_callable=run_history_bootstrap_pipeline
    )