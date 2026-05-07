from datetime import datetime
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
}

with DAG(
    dag_id='revolut_master_pipeline',
    default_args=default_args,
    schedule_interval='0 2 * * *',
    catchup=False,
    max_active_runs=1,
    tags=['master', 'orchestration']
) as dag:

    start_pipeline = EmptyOperator(task_id='start_pipeline')

    # trigger_extract = TriggerDagRunOperator(
    #     task_id='trigger_extract_api',
    #     trigger_dag_id='revolut_extract_api',
    #     wait_for_completion=True,
    #     poke_interval=30,
    #     reset_dag_run=True,
    #     execution_date="{{ execution_date }}"
    # )

    trigger_gen_accounts = TriggerDagRunOperator(
        task_id='trigger_generate_accounts',
        trigger_dag_id='revolut_generate_new_accounts',
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        execution_date="{{ execution_date }}"
    )

    trigger_gen_transactions = TriggerDagRunOperator(
        task_id='trigger_generate_transactions',
        trigger_dag_id='revolut_generate_transactions',
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        execution_date="{{ execution_date }}"
    )

    trigger_load_gold = TriggerDagRunOperator(
        task_id='trigger_load_gold',
        trigger_dag_id='revolut_load_gold',
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        execution_date="{{ execution_date }}"
    )

    end_pipeline = EmptyOperator(task_id='end_pipeline')

    start_pipeline >> trigger_gen_accounts >> trigger_gen_transactions >> trigger_load_gold >> end_pipeline
