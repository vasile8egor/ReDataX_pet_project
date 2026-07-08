from datetime import datetime

from clickhouse_driver import Client

from revolut_app.loaders.queries import (
    CREATE_GOLD_DATABASE_Q,
    CREATE_GOLD_FACT_TRANSACTIONS_Q,
    DELETE_GOLD_FACT_TRANSACTIONS_FOR_DATE_Q,
    INSERT_GOLD_FACT_TRANSACTIONS_Q,
    TRUNCATE_GOLD_FACT_TRANSACTIONS_Q,
)

CLICKHOUSE_DEFAULT_PORT = 9000


class GoldLayerLoader:
    def __init__(self, ch_host='clickhouse'):
        self.ch_client = Client(
            host=ch_host,
            port=CLICKHOUSE_DEFAULT_PORT,
            user='default',
            password='default'
        )

    def ensure_schema(self):
        self.ch_client.execute(CREATE_GOLD_DATABASE_Q)
        self.ch_client.execute(CREATE_GOLD_FACT_TRANSACTIONS_Q)

    def truncate_transactions(self):
        self.ensure_schema()
        self.ch_client.execute(TRUNCATE_GOLD_FACT_TRANSACTIONS_Q)

    def delete_transactions_for_date(self, target_date_str: str):
        datetime.strptime(target_date_str, '%Y-%m-%d')

        self.ensure_schema()
        self.ch_client.execute(
            DELETE_GOLD_FACT_TRANSACTIONS_FOR_DATE_Q,
            {'target_date': target_date_str}
        )

    def load_transactions(self, rows: list[tuple]):
        if not rows:
            return 0

        self.ensure_schema()
        self.ch_client.execute(
            INSERT_GOLD_FACT_TRANSACTIONS_Q,
            rows
        )
        return len(rows)
