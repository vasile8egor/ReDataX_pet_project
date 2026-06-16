import os

from pydantic import BaseModel


class Settings(BaseModel):
    postgres_host: str = os.getenv('POSTGRES_HOST', 'postgres_main')
    postgres_port: int = int(os.getenv('POSTGRES_PORT', '5432'))
    postgres_db: str = os.getenv('POSTGRES_DB', 'airflow')
    postgres_user: str = os.getenv('POSTGRES_USER', 'airflow')
    postgres_password: str = os.getenv('POSTGRES_PASSWORD', 'airflow')

    @property
    def postgres_dsn(self):
        return (
            f'host={self.postgres_host} '
            f'port={self.postgres_port} '
            f'dbname={self.postgres_db} '
            f'user={self.postgres_user} '
            f'password={self.postgres_password}'
        )


settings = Settings()
