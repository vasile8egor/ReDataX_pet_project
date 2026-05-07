from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
}

with DAG(
    dag_id='revolut_load_gold',
    default_args=default_args,
    schedule_interval=None,
    catchup=False
) as dag:

    def move_silver_to_gold(**context):
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        from revolut_app.loaders.gold_loader import GoldLayerLoader

        pg_hook = PostgresHook(postgres_conn_id='postgres_main')
        target_date = context['ds']

        sql = f"""
            SELECT 
                transaction_id, account_id, booking_datetime, 
                amount, currency, merchant_name
            FROM silver.fact_transactions
            WHERE DATE(booking_datetime) = '{target_date}'
        """
        df = pg_hook.get_pandas_df(sql)

        if df.empty:
            dag.log.info(
                f'No data found for date {target_date}. Skipping load.')
            return 'No data'

        loader = GoldLayerLoader()
        result = loader.load_transactions(df)
        dag.log.info(result)

    task_load = PythonOperator(
        task_id='load_silver_to_gold',
        python_callable=move_silver_to_gold
    )
