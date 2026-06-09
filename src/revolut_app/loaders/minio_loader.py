import json
from typing import Any

from airflow.providers.amazon.aws.hooks.s3 import S3Hook

from revolut_app.core.constants import BUCKET_RAW


class MinioRawLoader:
    def __init__(self, conn_id='minio_conn', bucket_name=BUCKET_RAW):
        self.hook = S3Hook(aws_conn_id=conn_id)
        self.bucket_name = bucket_name

    def load_json(self, key: str, payload: Any) -> str:
        if not self.hook.check_for_bucket(self.bucket_name):
            self.hook.create_bucket(bucket_name=self.bucket_name)

        self.hook.load_string(
            string_data=json.dumps(payload),
            key=key,
            bucket_name=self.bucket_name,
            replace=True
        )
        return key
