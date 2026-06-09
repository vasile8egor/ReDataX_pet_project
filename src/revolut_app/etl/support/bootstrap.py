import os
from pathlib import Path
from typing import Iterable

from airflow.providers.postgres.hooks.postgres import PostgresHook

from revolut_app.core.config import PROJECT_ROOT


SQL_BOOTSTRAP_ORDER = (
    'bronze/accounts_raw.sql',
    'bronze/transactions_raw.sql',
    'silver/v_accounts.sql',
    'silver/v_transactions.sql',
)


def _sql_root() -> Path:
    mounted_sql_root = Path(os.getenv('REVOLUT_SQL_ROOT', '/opt/airflow/sql'))
    if mounted_sql_root.exists():
        return mounted_sql_root

    local_sql_root = PROJECT_ROOT / 'sql'
    if local_sql_root.exists():
        return local_sql_root

    raise FileNotFoundError(
        'SQL directory not found. Mount ./sql to /opt/airflow/sql or set '
        'REVOLUT_SQL_ROOT.'
    )


def read_sql_file(relative_path: str) -> str:
    root = _sql_root()
    sql_path = root / relative_path
    if not sql_path.exists():
        raise FileNotFoundError(f'Missing SQL file: {sql_path}')

    return sql_path.read_text(encoding='utf-8')


def _read_sql_files(relative_paths: Iterable[str]) -> list[str]:
    statements = []

    for relative_path in relative_paths:
        statements.append(read_sql_file(relative_path))

    return statements


def run_db_bootstrap_pipeline() -> None:
    hook = PostgresHook(postgres_conn_id='postgres_main')
    for statement in _read_sql_files(SQL_BOOTSTRAP_ORDER):
        hook.run(statement)
