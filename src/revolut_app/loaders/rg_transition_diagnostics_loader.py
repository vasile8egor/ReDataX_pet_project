import os
from dataclasses import dataclass
from uuid import UUID

from clickhouse_driver import Client

from revolut_app.loaders.queries import (
    INSERT_RG_TRANSITION_DIAGNOSTICS_Q,
    RG_TRANSITION_DIAGNOSTICS_Q,
)


@dataclass(frozen=True)
class RgTransitionDiagnosticRecord:
    run_id: UUID
    event_dataset_id: UUID

    model_version: str
    pricing_policy: str

    event_index: int
    block_size: int

    history_ready: bool
    request_accepted: bool

    local_h_before: float
    local_projected_h_after: float
    local_delta_h: float

    coarse_h_before: float

    coarse_temporal_drift_delta_h: float
    normalized_coarse_temporal_drift_delta_h: float

    coarse_request_delta_h: float
    normalized_coarse_request_delta_h: float

    coarse_total_accepted_delta_h: float
    normalized_coarse_total_accepted_delta_h: float

    local_sign: str
    coarse_sign: str
    sign_agreement: bool


class RgTransitionDiagnosticsLoader:
    def __init__(self) -> None:
        self.client = Client(
            host=os.getenv(
                "CLICKHOUSE_HOST",
                "clickhouse",
            ),
            port=int(
                os.getenv(
                    "CLICKHOUSE_PORT",
                    "9000",
                )
            ),
            user=os.getenv(
                "CLICKHOUSE_USER",
                "default",
            ),
            password=os.getenv(
                "CLICKHOUSE_PASSWORD",
                "default",
            ),
        )

    def ensure_schema(self) -> None:
        self.client.execute(
            "CREATE DATABASE IF NOT EXISTS gold"
        )

        self.client.execute(
            RG_TRANSITION_DIAGNOSTICS_Q
        )

        for column_name in (
            "coarse_temporal_drift_delta_h",
            "normalized_coarse_temporal_drift_delta_h",
            "coarse_request_delta_h",
            "normalized_coarse_request_delta_h",
            "coarse_total_accepted_delta_h",
            "normalized_coarse_total_accepted_delta_h",
        ):
            self.client.execute(
                "ALTER TABLE gold.fact_rg_transition_diagnostics "
                f"ADD COLUMN IF NOT EXISTS {column_name} Float64"
            )

    def persist(
        self,
        records: list[
            RgTransitionDiagnosticRecord
        ],
    ) -> None:
        if not records:
            return

        self.ensure_schema()

        rows = [
            (
                item.run_id,
                item.event_dataset_id,
                item.model_version,
                item.pricing_policy,
                item.event_index,
                item.block_size,
                int(item.history_ready),
                int(item.request_accepted),
                item.local_h_before,
                item.local_projected_h_after,
                item.local_delta_h,
                item.coarse_h_before,
                item.coarse_temporal_drift_delta_h,
                item.normalized_coarse_temporal_drift_delta_h,
                item.coarse_request_delta_h,
                item.normalized_coarse_request_delta_h,
                item.coarse_total_accepted_delta_h,
                item.normalized_coarse_total_accepted_delta_h,
                item.local_sign,
                item.coarse_sign,
                int(item.sign_agreement),
            )
            for item in records
        ]

        self.client.execute(
            INSERT_RG_TRANSITION_DIAGNOSTICS_Q,
            rows,
        )
