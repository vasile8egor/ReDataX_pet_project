import json

import psycopg
from psycopg.rows import dict_row

from revolut_app.api_service.core.config import settings
from .queries import (
    idempotency_key_query,
    transaction_id_query,
    insert_query
)


class TransactionEventRepository:

    def _connect(self):
        return psycopg.connect(settings.postgres_dsn, row_factory=dict_row)

    def find_by_idempotency_key(self, idempotency_key: str):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(idempotency_key_query, (idempotency_key,))
                row = cur.fetchone()

        return dict(row) if row else None

    def find_by_transaction_id(self, transaction_id):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(transaction_id_query, (transaction_id,))
                row = cur.fetchone()

        return dict(row) if row else None

    def insert_event(
            self,
            *,
            event_id,
            idempotency_key,
            transaction_id,
            account_id,
            payload,
            risk_score,
            risk_level,
    ):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_query,
                    (
                        event_id,
                        idempotency_key,
                        transaction_id,
                        account_id,
                        json.dumps(payload, default=str),
                        risk_score,
                        risk_level,
                    )
                )


TrasnasctionEventRepository = TransactionEventRepository
