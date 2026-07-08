import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid5

from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.risk.rg import (
    MultiscaleAnalysisParameters,
    TrajectoryExtractionParameters,
    analyze_multiscale_trajectory,
    extract_pressure_trajectories,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)
from revolut_app.loaders.rg_analysis_loader import (
    RgAnalysisClickHouseLoader,
    RgAnalysisRunRecord,
    RgCurrencyObservablesRecord,
    RgScaleObservablesRecord,
    RgVarianceScalingRecord,
)


RG_ANALYSIS_NAMESPACE = UUID(
    '3a2da11a-f173-4724-b809-7395be0d3794'
)


@dataclass(frozen=True)
class RgAnalysisParameters:
    analysis_version: str
    source_model_version: str

    hamiltonian_preset: HamiltonianPreset

    block_sizes: tuple[int, ...]
    stress_pressure_threshold: float

    expected_source_runs: int | None = None


@dataclass(frozen=True)
class RgAnalysisSummary:
    analysis_id: UUID

    source_runs: int
    source_frames: int

    scale_rows: int
    currency_rows: int
    scaling_rows: int


def build_rg_analysis_id(
    *,
    parameters: RgAnalysisParameters,
    source_run_ids: list[UUID],
):
    payload = json.dumps(
        {
            'analysis_version':
                parameters.analysis_version,
            'source_model_version':
                parameters.source_model_version,
            'hamiltonian_preset':
                parameters.hamiltonian_preset.value,
            'block_sizes':
                list(parameters.block_sizes),
            'stress_pressure_threshold':
                parameters.stress_pressure_threshold,
            'source_run_ids':
                sorted(
                    str(run_id)
                    for run_id in source_run_ids
                ),
        },
        sort_keys=True,
        separators=(',', ':'),
    )

    return uuid5(
        RG_ANALYSIS_NAMESPACE,
        payload,
    )


class RgMultiscaleAnalysisRunner:
    def __init__(
        self,
        *,
        loader: RgAnalysisClickHouseLoader,
    ):
        self.loader = loader

    def run(
        self, *,
        parameters: RgAnalysisParameters,
    ):
        started_at = datetime.now(
            timezone.utc
        )

        source_runs = (
            self.loader.load_source_runs(
                source_model_version=(
                    parameters
                    .source_model_version
                )
            )
        )

        if not source_runs:
            raise ValueError(
                'No RG source runs found'
            )

        if (
            parameters.expected_source_runs
            is not None
            and len(source_runs)
            != parameters.expected_source_runs
        ):
            raise ValueError(
                'Unexpected RG source run count: '
                f'''expected='''
                f'''{parameters.expected_source_runs}, '''
                f'''actual={len(source_runs)}'''
            )

        analysis_id = build_rg_analysis_id(
            parameters=parameters,
            source_run_ids=[
                run.run_id
                for run in source_runs
            ],
        )

        self.loader.ensure_analysis_not_persisted(
            analysis_id=analysis_id
        )

        engine = build_hamiltonian_engine(
            parameters.hamiltonian_preset
        )

        multiscale_parameters = (
            MultiscaleAnalysisParameters(
                block_sizes=(
                    parameters.block_sizes
                ),
                stress_pressure_threshold=(
                    parameters
                    .stress_pressure_threshold
                ),
            )
        )

        extraction_parameters = (
            TrajectoryExtractionParameters(
                expected_currencies=(
                    'EUR',
                    'GBP',
                    'USD',
                ),
                include_initial_frame=False,
                require_contiguous_event_indices=True,
            )
        )

        scale_records = []
        currency_records = []
        scaling_records = []

        source_frame_count = 0

        for index, source_run in enumerate(
            source_runs,
            start=1,
        ):
            print(
                f'''[{index}/{len(source_runs)}] '''
                f'''policy={source_run.pricing_policy} '''
                f'''run={source_run.run_id}'''
            )

            observations = (
                self.loader
                .load_pressure_observations(
                    source_run=source_run
                )
            )

            trajectories = (
                extract_pressure_trajectories(
                    observations=observations,
                    parameters=(
                        extraction_parameters
                    ),
                )
            )

            trajectory_id = str(
                source_run.run_id
            )

            if set(trajectories) != {
                trajectory_id
            }:
                raise ValueError(
                    'Unexpected trajectory IDs: '
                    f'''expected={trajectory_id}, '''
                    f'''actual='''
                    f'''{sorted(trajectories)}'''
                )

            frames = trajectories[
                trajectory_id
            ]

            if len(frames) != (
                source_run.generated_requests
            ):
                raise ValueError(
                    'Event-level trajectory size '
                    'does not match generated requests: '
                    f'''run_id={source_run.run_id}, '''
                    f'''frames={len(frames)}, '''
                    f'''requests='''
                    f'''{source_run.generated_requests}'''
                )

            source_frame_count += len(frames)

            result = (
                analyze_multiscale_trajectory(
                    trajectory_id=trajectory_id,
                    frames=frames,
                    parameters=(
                        multiscale_parameters
                    ),
                    hamiltonian_engine=engine,
                )
            )

            self._validate_result(
                result=result
            )

            for scale in result.scales:
                scale_records.append(
                    RgScaleObservablesRecord(
                        analysis_id=analysis_id,
                        analysis_version=(
                            parameters
                            .analysis_version
                        ),
                        source_run_id=(
                            source_run.run_id
                        ),
                        event_dataset_id=(
                            source_run
                            .event_dataset_id
                        ),
                        source_model_version=(
                            parameters
                            .source_model_version
                        ),
                        pricing_policy=(
                            source_run
                            .pricing_policy
                        ),
                        block_size=(
                            scale.block_size
                        ),
                        block_count=(
                            scale.block_count
                        ),
                        frames_used=(
                            scale.frames_used
                        ),
                        frames_dropped=(
                            scale.frames_dropped
                        ),
                        trace_coarse_covariance=(
                            scale
                            .trace_coarse_covariance
                        ),
                        mean_coarse_norm_squared=(
                            scale
                            .mean_coarse_norm_squared
                        ),
                        mean_internal_variance_total=(
                            scale
                            .mean_internal_variance_total
                        ),
                        mean_max_abs_coarse_pressure=(
                            scale
                            .mean_max_abs_coarse_pressure
                        ),
                        coarse_stress_fraction=(
                            scale
                            .coarse_stress_fraction
                        ),
                        mean_micro_h_total=(
                            scale.mean_micro_h_total
                        ),
                        mean_coarse_h_total=(
                            scale.mean_coarse_h_total
                        ),
                        mean_unresolved_h_total=(
                            scale
                            .mean_unresolved_h_total
                        ),
                    )
                )

                for currency, item in (
                    scale.currencies.items()
                ):
                    currency_records.append(
                        RgCurrencyObservablesRecord(
                            analysis_id=analysis_id,
                            analysis_version=(
                                parameters
                                .analysis_version
                            ),
                            source_run_id=(
                                source_run.run_id
                            ),
                            event_dataset_id=(
                                source_run
                                .event_dataset_id
                            ),
                            source_model_version=(
                                parameters
                                .source_model_version
                            ),
                            pricing_policy=(
                                source_run
                                .pricing_policy
                            ),
                            block_size=(
                                scale.block_size
                            ),
                            currency=currency,
                            mean_coarse_pressure=(
                                item
                                .mean_coarse_pressure
                            ),
                            coarse_second_moment=(
                                item
                                .coarse_second_moment
                            ),
                            coarse_fourth_moment=(
                                item
                                .coarse_fourth_moment
                            ),
                            coarse_variance=(
                                item.coarse_variance
                            ),
                            mean_micro_second_moment=(
                                item
                                .mean_micro_second_moment
                            ),
                            mean_internal_variance=(
                                item
                                .mean_internal_variance
                            ),
                            second_moment_decomposition_error=(
                                item
                                .second_moment_decomposition_error
                            ),
                        )
                    )

            for item in result.variance_scaling:
                scaling_records.append(
                    RgVarianceScalingRecord(
                        analysis_id=analysis_id,
                        analysis_version=(
                            parameters
                            .analysis_version
                        ),
                        source_run_id=(
                            source_run.run_id
                        ),
                        event_dataset_id=(
                            source_run
                            .event_dataset_id
                        ),
                        source_model_version=(
                            parameters
                            .source_model_version
                        ),
                        pricing_policy=(
                            source_run
                            .pricing_policy
                        ),
                        dimension=item.dimension,
                        from_block_size=(
                            item.from_block_size
                        ),
                        to_block_size=(
                            item.to_block_size
                        ),
                        variance_from=(
                            item.variance_from
                        ),
                        variance_to=(
                            item.variance_to
                        ),
                        scaling_exponent=(
                            item.exponent
                        ),
                    )
                )

        finished_at = datetime.now(
            timezone.utc
        )

        parameters_json = json.dumps(
            {
                'analysis_version':
                    parameters.analysis_version,
                'source_model_version':
                    parameters.source_model_version,
                'hamiltonian_preset':
                    parameters
                    .hamiltonian_preset.value,
                'block_sizes':
                    list(parameters.block_sizes),
                'stress_pressure_threshold':
                    parameters
                    .stress_pressure_threshold,
            },
            sort_keys=True,
        )

        analysis_record = (
            RgAnalysisRunRecord(
                analysis_id=analysis_id,
                analysis_version=(
                    parameters.analysis_version
                ),
                source_model_version=(
                    parameters
                    .source_model_version
                ),
                hamiltonian_preset=(
                    parameters
                    .hamiltonian_preset.value
                ),
                block_sizes=(
                    parameters.block_sizes
                ),
                stress_pressure_threshold=(
                    parameters
                    .stress_pressure_threshold
                ),
                source_run_count=len(
                    source_runs
                ),
                source_frame_count=(
                    source_frame_count
                ),
                parameters_json=(
                    parameters_json
                ),
                started_at=started_at,
                finished_at=finished_at,
            )
        )

        self.loader.persist_analysis(
            analysis=analysis_record,
            scales=scale_records,
            currencies=currency_records,
            scaling=scaling_records,
        )

        return RgAnalysisSummary(
            analysis_id=analysis_id,
            source_runs=len(source_runs),
            source_frames=source_frame_count,
            scale_rows=len(scale_records),
            currency_rows=len(
                currency_records
            ),
            scaling_rows=len(
                scaling_records
            ),
        )

    def _validate_result(
        self,
        *,
        result,
    ):
        decomposition_tolerance = 1e-10
        identity_tolerance = 1e-9

        for scale in result.scales:
            for item in scale.currencies.values():
                if abs(
                    item
                    .second_moment_decomposition_error
                ) > decomposition_tolerance:
                    raise ValueError(
                        'Second-moment decomposition '
                        'failed: '
                        f'''trajectory='''
                        f'''{result.trajectory_id}, '''
                        f'''block_size='''
                        f'''{scale.block_size}, '''
                        f'''currency={item.currency}, '''
                        f'''error='''
                        f'''{item.second_moment_decomposition_error}'''
                    )

            if scale.block_size == 1:
                unresolved = (
                    scale.mean_unresolved_h_total
                )

                if (
                    unresolved is None
                    or abs(unresolved)
                    > identity_tolerance
                ):
                    raise ValueError(
                        'Hamiltonian identity failed '
                        'at block_size=1: '
                        f'''trajectory='''
                        f'''{result.trajectory_id}, '''
                        f'''unresolved={unresolved}'''
                    )
