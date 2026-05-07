from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
}

with DAG(
    dag_id='revolut_extract_api_v2',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=['production', 'revolut']
) as dag:

    def get_client_instance():
        import os
        from revolut_app.api import RevolutClient
        from airflow.models import Variable

        return RevolutClient(
            client_id=Variable.get(
                "REVOLUT_CLIENT_ID",
                default_var=os.getenv("REVOLUT_CLIENT_ID")
            ),
            financial_id=Variable.get(
                "REVOLUT_FINANCIAL_ID",
                default_var=os.getenv("REVOLUT_FINANCIAL_ID")
            ),
            private_key_path=Variable.get(
                "REVOLUT_PRIVATE_KEY_PATH",
                "/opt/airflow/certs/private.key"
            ),
            transport_cert_path=Variable.get(
                "REVOLUT_TRANSPORT_CERT_PATH",
                "/opt/airflow/certs/transport.pem"
            ),
            kid=Variable.get(
                "REVOLUT_KID",
                default_var=os.getenv("REVOLUT_KID")
            ),
            redirect_url=Variable.get(
                "REVOLUT_REDIRECT_URL",
                default_var=os.getenv("REVOLUT_REDIRECT_URL")
            )
        )

    def extract_accounts(**context):
        import json
        import os
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook
        from airflow.models import Variable
        from revolut_app.core.constants import BUCKET_RAW

        refresh_token = Variable.get(
            "REVOLUT_REFRESH_TOKEN",
            default_var=os.getenv("REVOLUT_REFRESH_TOKEN")
        )
        client = get_client_instance()
        client.refresh_token = refresh_token

        accounts = client.get_accounts()

        s3 = S3Hook(aws_conn_id='minio_conn')
        execution_date = context['ds']
        object_name = f"accounts/{execution_date}/accounts.json"

        s3.load_string(
            string_data=json.dumps(accounts),
            key=object_name,
            bucket_name=BUCKET_RAW,
            replace=True
        )
        return object_name

    def extract_transactions(**context):
        import json
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook
        from airflow.models import Variable
        from revolut_app.core.constants import BUCKET_RAW

        accounts_path = context['ti'].xcom_pull(task_ids='extract_accounts')

        s3 = S3Hook(aws_conn_id='minio_conn')
        client = get_client_instance()
        client.refresh_token = Variable.get("REVOLUT_REFRESH_TOKEN")

        content = s3.read_key(accounts_path, bucket_name=BUCKET_RAW)
        account_list = json.loads(content).get("Data", {}).get("Account", [])

        execution_date = context['ds']

        for acc in account_list:
            acc_id = acc['AccountId']
            try:
                transactions = client.get_transactions(acc_id)

                s3.load_string(
                    string_data=json.dumps(transactions),
                    key=f"transactions/{execution_date}/{acc_id}.json",
                    bucket_name=BUCKET_RAW,
                    replace=True
                )
            except Exception as e:
                dag.log.error(
                    f"Failed to extract transactions for {acc_id}: {e}")

    task_accounts = PythonOperator(
        task_id='extract_accounts',
        python_callable=extract_accounts
    )

    task_transactions = PythonOperator(
        task_id='extract_transactions',
        python_callable=extract_transactions
    )

    task_accounts >> task_transactions
