import os
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from clickhouse_driver import Client

from revolut_app.fx_lab.risk.rg import (
    PressureObservation,
)

from revolut_app.loaders.queries import (
    INSERT_RG_ANALYSIS_RUN_Q,
    INSERT_RG_CURRENCY_OBSERVABLES_Q,
    INSERT_RG_SCALE_OBSERVABLES_Q,
    INSERT_RG_VARIANCE_SCALING_Q,
    RG_ANALYSIS_RUNS_Q,
    RG_CURRENCY_OBSERVABLES_Q,
    RG_SCALE_OBSERVABLES_Q,
    RG_VARIANCE_SCALING_Q,
    SELECT_EXISTING_RG_ANALYSIS_Q,
    SELECT_RG_PRESSURE_OBSERVATIONS_Q,
    SELECT_RG_SOURCE_RUNS_Q,
)


@dataclass(frozen=True)
class RgSourceRun:
    run_id: UUID
    event_dataset_id: UUID
    pricing_policy: str
    generated_requests: int


@dataclass(frozen=True)
class RgAnalysisRunRecord:
    analysis_id: UUID
    analysis_version: str

    source_model_version: str
    hamiltonian_preset: str

    block_sizes: tuple[int, ...]
    stress_pressure_threshold: float

    source_run_count: int
    source_frame_count: int

    parameters_json: str

    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True)
class RgScaleObservablesRecord:
    analysis_id: UUID
    analysis_version: str

    source_run_id: UUID
    event_dataset_id: UUID
    source_model_version: str
    pricing_policy: str

    block_size: int
    block_count: int

    frames_used: int
    frames_dropped: int

    trace_coarse_covariance: float
    mean_coarse_norm_squared: float
    mean_internal_variance_total: float

    mean_max_abs_coarse_pressure: float
    coarse_stress_fraction: float

    mean_micro_h_total: float | None
    mean_coarse_h_total: float | None
    mean_unresolved_h_total: float | None


@dataclass(frozen=True)
class RgCurrencyObservablesRecord:
    analysis_id: UUID
    analysis_version: str

    source_run_id: UUID
    event_dataset_id: UUID
    source_model_version: str
    pricing_policy: str

    block_size: int
    currency: str

    mean_coarse_pressure: float
    coarse_second_moment: float
    coarse_fourth_moment: float
    coarse_variance: float

    mean_micro_second_moment: float
    mean_internal_variance: float

    second_moment_decomposition_error: float


@dataclass(frozen=True)
class RgVarianceScalingRecord:
    analysis_id: UUID
    analysis_version: str

    source_run_id: UUID
    event_dataset_id: UUID
    source_model_version: str
    pricing_policy: str

    dimension: str

    from_block_size: int
    to_block_size: int

    variance_from: float
    variance_to: float

    scaling_exponent: float | None


class RgAnalysisClickHouseLoader:
    def __init__(
        self, *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.client = Client(
            host=host or os.getenv(
                "CLICKHOUSE_HOST",
                "clickhouse",
            ),
            port=port or int(
                os.getenv(
                    "CLICKHOUSE_PORT",
                    "9000",
                )
            ),
            user=user or os.getenv(
                "CLICKHOUSE_USER",
                "default",
            ),
            password=(
                password
                if password is not None
                else os.getenv(
                    "CLICKHOUSE_PASSWORD",
                    "default",
                )
            ),
            database=os.getenv(
                "CLICKHOUSE_DATABASE",
                "gold",
            ),
        )

    def ensure_schema(self) -> None:
        self.client.execute(
            "CREATE DATABASE IF NOT EXISTS gold"
        )

        self.client.execute(
            RG_ANALYSIS_RUNS_Q
        )
        self.client.execute(
            RG_SCALE_OBSERVABLES_Q
        )
        self.client.execute(
            RG_CURRENCY_OBSERVABLES_Q
        )
        self.client.execute(
            RG_VARIANCE_SCALING_Q
        )

    def load_source_runs(
        self, *,
        source_model_version: str,
    ) -> list[RgSourceRun]:
        self.ensure_schema()

        rows = self.client.execute(
            SELECT_RG_SOURCE_RUNS_Q,
            {
                "source_model_version":
                    source_model_version,
            },
        )

        return [
            RgSourceRun(
                run_id=row[0],
                event_dataset_id=row[1],
                pricing_policy=row[2],
                generated_requests=row[3],
            )
            for row in rows
        ]

    def load_pressure_observations(
        self,
        *,
        source_run: RgSourceRun,
    ) -> list[PressureObservation]:
        rows = self.client.execute(
            SELECT_RG_PRESSURE_OBSERVATIONS_Q,
            {
                "run_id": source_run.run_id,
            },
        )

        return [
            PressureObservation(
                trajectory_id=str(
                    source_run.run_id
                ),
                event_index=row[0],
                currency=row[1],
                pressure=row[2],
                h_total=row[3],
            )
            for row in rows
        ]

    def ensure_analysis_not_persisted(
        self,
        *,
        analysis_id: UUID,
    ) -> None:
        counts = self.client.execute(
            SELECT_EXISTING_RG_ANALYSIS_Q,
            {
                "analysis_id": analysis_id,
            },
        )[0]

        labels = (
            "analysis",
            "scale",
            "currency",
            "scaling",
        )

        existing = {
            label: count
            for label, count
            in zip(labels, counts)
            if count > 0
        }

        if existing:
            raise ValueError(
                "RG analysis already contains "
                "persisted rows: "
                f"analysis_id={analysis_id}, "
                f"counts={existing}"
            )

    def persist_analysis(
        self,
        *,
        analysis: RgAnalysisRunRecord,
        scales: list[
            RgScaleObservablesRecord
        ],
        currencies: list[
            RgCurrencyObservablesRecord
        ],
        scaling: list[
            RgVarianceScalingRecord
        ],
    ) -> None:
        self.ensure_schema()

        self.ensure_analysis_not_persisted(
            analysis_id=analysis.analysis_id
        )

        scale_rows = [
            (
                item.analysis_id,
                item.analysis_version,
                item.source_run_id,
                item.event_dataset_id,
                item.source_model_version,
                item.pricing_policy,
                item.block_size,
                item.block_count,
                item.frames_used,
                item.frames_dropped,
                item.trace_coarse_covariance,
                item.mean_coarse_norm_squared,
                item.mean_internal_variance_total,
                item.mean_max_abs_coarse_pressure,
                item.coarse_stress_fraction,
                item.mean_micro_h_total,
                item.mean_coarse_h_total,
                item.mean_unresolved_h_total,
            )
            for item in scales
        ]

        currency_rows = [
            (
                item.analysis_id,
                item.analysis_version,
                item.source_run_id,
                item.event_dataset_id,
                item.source_model_version,
                item.pricing_policy,
                item.block_size,
                item.currency,
                item.mean_coarse_pressure,
                item.coarse_second_moment,
                item.coarse_fourth_moment,
                item.coarse_variance,
                item.mean_micro_second_moment,
                item.mean_internal_variance,
                item.second_moment_decomposition_error,
            )
            for item in currencies
        ]

        scaling_rows = [
            (
                item.analysis_id,
                item.analysis_version,
                item.source_run_id,
                item.event_dataset_id,
                item.source_model_version,
                item.pricing_policy,
                item.dimension,
                item.from_block_size,
                item.to_block_size,
                item.variance_from,
                item.variance_to,
                item.scaling_exponent,
            )
            for item in scaling
        ]

        analysis_row = [
            (
                analysis.analysis_id,
                analysis.analysis_version,
                analysis.source_model_version,
                analysis.hamiltonian_preset,
                list(analysis.block_sizes),
                analysis.stress_pressure_threshold,
                analysis.source_run_count,
                analysis.source_frame_count,
                analysis.parameters_json,
                analysis.started_at,
                analysis.finished_at,
            )
        ]

        self.client.execute(
            INSERT_RG_SCALE_OBSERVABLES_Q,
            scale_rows,
        )

        self.client.execute(
            INSERT_RG_CURRENCY_OBSERVABLES_Q,
            currency_rows,
        )

        self.client.execute(
            INSERT_RG_VARIANCE_SCALING_Q,
            scaling_rows,
        )

        self.client.execute(
            INSERT_RG_ANALYSIS_RUN_Q,
            analysis_row,
        )
