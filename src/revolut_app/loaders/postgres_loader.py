import json
from typing import Iterable, List

from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

from revolut_app.loaders.queries import (
    INSERT_JSONB_PAYLOAD_Q_TEMPLATE,
    SELECT_SILVER_ACCOUNT_IDS_Q,
)

POSTGRES_INSERT_PAGE_SIZE = 5000
RAW_TRANSACTION_BATCH_SIZE = 50000


class PostgresLoader:
    def __init__(self, conn_id='postgres_main'):
        self.hook = PostgresHook(postgres_conn_id=conn_id)

    def get_account_ids(self):
        records = self.hook.get_records(SELECT_SILVER_ACCOUNT_IDS_Q)
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
                    INSERT_JSONB_PAYLOAD_Q_TEMPLATE.format(table=table),
                    rows,
                    template='(%s::jsonb)',
                    page_size=POSTGRES_INSERT_PAGE_SIZE
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
        batch_size: int = RAW_TRANSACTION_BATCH_SIZE
    ):
        if not data_list:
            return

        for start in range(0, len(data_list), batch_size):
            self.load_raw_transactions(data_list[start:start + batch_size])

    def load_raw_accounts_in_batches(
        self,
        data_list: List[dict],
        batch_size: int = RAW_TRANSACTION_BATCH_SIZE
    ):
        if not data_list:
            return

        for start in range(0, len(data_list), batch_size):
            self.load_raw_accounts(data_list[start:start + batch_size])
