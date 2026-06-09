import json
from typing import Iterable, List

from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values


class PostgresLoader:
    def __init__(self, conn_id='postgres_main'):
        self.hook = PostgresHook(postgres_conn_id=conn_id)

    def get_account_ids(self):
        records = self.hook.get_records(
            "SELECT account_id FROM silver.v_accounts"
        )
        return [r[0] for r in records]

    def load_raw_transactions(self, data_list: Iterable[dict]):
        self._load_jsonb_rows(
            table='bronze.revolut_transactions_raw',
            data_list=data_list
        )

    def load_raw_accounts(self, data_list: Iterable[dict]):
        self._load_jsonb_rows(
            table='bronze.revolut_accounts_raw',
            data_list=data_list
        )

    def _load_jsonb_rows(self, table: str, data_list: Iterable[dict]):
        data = list(data_list)
        if not data:
            return

        rows = [(json.dumps(row),) for row in data]
        conn = self.hook.get_conn()

        try:
            with conn.cursor() as cursor:
                execute_values(
                    cursor,
                    f"INSERT INTO {table} (payload) VALUES %s",
                    rows,
                    template='(%s::jsonb)',
                    page_size=5000
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def load_raw_transactions_in_batches(
        self,
        data_list: List[dict],
        batch_size: int = 50000
    ):
        if not data_list:
            return

        for start in range(0, len(data_list), batch_size):
            self.load_raw_transactions(data_list[start:start + batch_size])

    def load_raw_accounts_in_batches(
        self,
        data_list: List[dict],
        batch_size: int = 50000
    ):
        if not data_list:
            return

        for start in range(0, len(data_list), batch_size):
            self.load_raw_accounts(data_list[start:start + batch_size])
