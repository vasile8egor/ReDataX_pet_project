from clickhouse_driver import Client
from datetime import datetime


class GoldLayerLoader:
    def __init__(self, ch_host='clickhouse'):
        self.ch_client = Client(
            host=ch_host,
            port=9000,
            user='default',
            password='default'
        )

    def ensure_schema(self) -> None:
        self.ch_client.execute('CREATE DATABASE IF NOT EXISTS gold')
        self.ch_client.execute(
            '''
            CREATE TABLE IF NOT EXISTS gold.fact_transactions (
                transaction_id String,
                account_id String,
                tx_timestamp DateTime64(3, 'UTC'),
                amount Decimal(18, 4),
                currency String,
                merchant_name Nullable(String),
                bronze_loaded_at DateTime64(3, 'UTC'),
                gold_loaded_at DateTime DEFAULT now()
            )
            ENGINE = ReplacingMergeTree(gold_loaded_at)
            ORDER BY (tx_timestamp, transaction_id)
            '''
        )

    def truncate_transactions(self) -> None:
        self.ensure_schema()
        self.ch_client.execute('TRUNCATE TABLE gold.fact_transactions')

    def delete_transactions_for_date(self, target_date_str: str) -> None:
        datetime.strptime(target_date_str, '%Y-%m-%d')

        self.ensure_schema()
        self.ch_client.execute(
            '''
            ALTER TABLE gold.fact_transactions
            DELETE WHERE toDate(tx_timestamp) = toDate(%(target_date)s)
            SETTINGS mutations_sync = 1
            ''',
            {'target_date': target_date_str}
        )

    def load_transactions(self, rows: list[tuple]) -> int:
        if not rows:
            return 0

        self.ensure_schema()
        self.ch_client.execute(
            '''
            INSERT INTO gold.fact_transactions (
                transaction_id,
                account_id,
                tx_timestamp,
                amount,
                currency,
                merchant_name,
                bronze_loaded_at
            )
            VALUES
            ''',
            rows
        )
        return len(rows)
