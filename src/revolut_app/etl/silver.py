import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from revolut_app.core.config import (
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY,
    get_postgres_jdbc_url, POSTGRES_USER, POSTGRES_PASSWORD
)


def get_db_engine():
    from revolut_app.core.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
    url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    return create_engine(url)


def load_accounts_to_silver(s3_path: str):
    storage_options = {
        "key": MINIO_ACCESS_KEY,
        "secret": MINIO_SECRET_KEY,
        "client_kwargs": {"endpoint_url": MINIO_ENDPOINT}
    }

    path_corrected = s3_path.replace("s3a://", "s3://")
    df_raw = pd.read_json(path_corrected, storage_options=storage_options)

    accounts_list = df_raw.loc['Account', 'Data']
    df_accounts = pd.DataFrame(accounts_list)

    df_silver = df_accounts[[
        'AccountId', 'Currency', 'AccountType', 'AccountSubType'
    ]].copy()

    df_silver.columns = [
        'account_id', 'currency', 'account_type', 'account_sub_type'
    ]

    df_silver['inserted_at'] = datetime.now()
    df_silver = df_silver.drop_duplicates(subset=['account_id'])

    print(f"Transformed {len(df_silver)} accounts.")

    engine = get_db_engine()

    with engine.connect() as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        conn.commit()

    df_silver.to_sql(
        name='dim_accounts',
        con=engine,
        schema='silver',
        if_exists='append',
        index=False
    )

    print('Successfully loaded accounts into silver.dim_accounts')


if __name__ == "__main__":
    pass
