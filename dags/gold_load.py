from airflow import DAG
from airflow.operators.python import PythonOperator
from revolut_app.core.constants import DEFAULT_ARGS_W_RETRIES
from revolut_app.etl.pipelines.gold import run_gold_transactions_load

with DAG(
    'revolut_load_gold',
    default_args=DEFAULT_ARGS_W_RETRIES,
    schedule_interval=None,
    catchup=False
) as dag:
    PythonOperator(
        task_id='load_gold_transactions',
        python_callable=run_gold_transactions_load,
        op_kwargs={'target_date_str': '{{ ds }}'},
    )
