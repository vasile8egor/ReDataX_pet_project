import json
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID, uuid5

from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.risk.rg import (
    EffectiveHamiltonianFitParameters,
    EffectiveHamiltonianObservation,
    TemporalCoarseGrainingParameters,
    TrajectoryExtractionParameters,
    build_effective_hamiltonian_observations,
    coarse_grain_pressure_trajectory,
    extract_pressure_trajectories,
    fit_effective_hamiltonian,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)
from revolut_app.loaders.rg_analysis_loader import (
    RgAnalysisClickHouseLoader,
    RgEffectiveHamiltonianFitRecord,
)


RG_EFFECTIVE_FIT_NAMESPACE = UUID(
    '3ca1444d-095a-4873-8cf2-d556125cf021'
)


@dataclass(frozen=True)
class RgEffectiveHamiltonianParameters:
    fit_version: str

    source_analysis_version: str
    source_model_version: str

    hamiltonian_preset: HamiltonianPreset

    block_sizes: tuple[int, ...]

    expected_policies: tuple[str, ...] = (
        'inventory_aware',
        'naive',
        'platform',
    )

    expected_trajectories_per_policy: int = 10

    operator_basis: str = (
        'isotropic-local-q2-q4-v1'
    )


@dataclass(frozen=True)
class RgEffectiveHamiltonianSummary:
    fit_analysis_id: UUID

    policies: int
    block_sizes: int
    fit_rows: int

    total_observations: int


def build_effective_fit_analysis_id(
    *,
    source_analysis_id: UUID,
    parameters: RgEffectiveHamiltonianParameters,
):
    payload = json.dumps(
        {
            'source_analysis_id':
                str(source_analysis_id),
            'fit_version':
                parameters.fit_version,
            'source_model_version':
                parameters.source_model_version,
            'hamiltonian_preset':
                parameters.hamiltonian_preset.value,
            'block_sizes':
                list(parameters.block_sizes),
            'expected_policies':
                list(parameters.expected_policies),
            'operator_basis':
                parameters.operator_basis,
        },
        sort_keys=True,
        separators=(',', ':'),
    )

    return uuid5(
        RG_EFFECTIVE_FIT_NAMESPACE,
        payload,
    )


class RgEffectiveHamiltonianRunner:
    def __init__(
        self,
        *,
        loader: RgAnalysisClickHouseLoader,
    ):
        self.loader = loader

    def run(
        self,
        *,
        parameters: RgEffectiveHamiltonianParameters,
    ):
        source_analysis = (
            self.loader.load_source_analysis(
                analysis_version=(
                    parameters
                    .source_analysis_version
                ),
                source_model_version=(
                    parameters
                    .source_model_version
                ),
            )
        )

        if tuple(parameters.block_sizes) != tuple(
            source_analysis.block_sizes
        ):
            raise ValueError(
                'Fit block sizes do not match '
                'source RG analysis: '
                f'''fit={parameters.block_sizes}, '''
                f'''source='''
                f'''{source_analysis.block_sizes}'''
            )

        source_runs = (
            self.loader.load_source_runs(
                source_model_version=(
                    parameters
                    .source_model_version
                )
            )
        )

        expected_run_count = (
            len(parameters.expected_policies)
            * parameters
            .expected_trajectories_per_policy
        )

        if len(source_runs) != expected_run_count:
            raise ValueError(
                'Unexpected source run count: '
                f'''expected={expected_run_count}, '''
                f'''actual={len(source_runs)}'''
            )

        runs_by_policy = defaultdict(list)

        for source_run in source_runs:
            runs_by_policy[
                source_run.pricing_policy
            ].append(source_run)

        actual_policies = set(
            runs_by_policy
        )

        expected_policies = set(
            parameters.expected_policies
        )

        if actual_policies != expected_policies:
            raise ValueError(
                'Source policies do not match: '
                f'''expected='''
                f'''{sorted(expected_policies)}, '''
                f'''actual='''
                f'''{sorted(actual_policies)}'''
            )

        for policy_name, policy_runs in (
            runs_by_policy.items()
        ):
            if len(policy_runs) != (
                parameters
                .expected_trajectories_per_policy
            ):
                raise ValueError(
                    'Unexpected trajectories '
                    'for policy: '
                    f'''policy={policy_name}, '''
                    f'''expected='''
                    f'''{parameters.expected_trajectories_per_policy}, '''
                    f'''actual={len(policy_runs)}'''
                )

        fit_analysis_id = (
            build_effective_fit_analysis_id(
                source_analysis_id=(
                    source_analysis.analysis_id
                ),
                parameters=parameters,
            )
        )

        self.loader.ensure_effective_fit_not_persisted(
            fit_analysis_id=fit_analysis_id
        )

        fit_parameters = (
            EffectiveHamiltonianFitParameters(
                require_full_rank=True,
                minimum_trajectories_for_cv=2,
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

        records: list[
            RgEffectiveHamiltonianFitRecord
        ] = []

        total_observations = 0

        for policy_index, policy_name in enumerate(
            parameters.expected_policies,
            start=1,
        ):
            policy_runs = runs_by_policy[
                policy_name
            ]

            observations_by_scale: dict[
                int,
                list[
                    EffectiveHamiltonianObservation
                ],
            ] = {
                block_size: []
                for block_size
                in parameters.block_sizes
            }

            print()
            print(
                f'''[{policy_index}/'''
                f'''{len(parameters.expected_policies)}] '''
                f'''policy={policy_name}'''
            )

            for run_index, source_run in enumerate(
                policy_runs,
                start=1,
            ):
                print(
                    f'''  [{run_index}/'''
                    f'''{len(policy_runs)}] '''
                    f'''run={source_run.run_id}'''
                )

                raw_observations = (
                    self.loader
                    .load_pressure_observations(
                        source_run=source_run
                    )
                )

                trajectories = (
                    extract_pressure_trajectories(
                        observations=(
                            raw_observations
                        ),
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
                        f'''run_id={source_run.run_id}, '''
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
                        'Trajectory frame count '
                        'does not match requests: '
                        f'''run_id='''
                        f'''{source_run.run_id}, '''
                        f'''frames={len(frames)}, '''
                        f'''requests='''
                        f'''{source_run.generated_requests}'''
                    )

                for block_size in (
                    parameters.block_sizes
                ):
                    blocks = (
                        coarse_grain_pressure_trajectory(
                            frames=frames,
                            parameters=(
                                TemporalCoarseGrainingParameters(
                                    block_size=block_size,
                                    drop_incomplete_block=True,
                                )
                            ),
                        )
                    )

                    block_observations = (
                        build_effective_hamiltonian_observations(
                            trajectory_id=trajectory_id,
                            block_size=block_size,
                            blocks=blocks,
                        )
                    )

                    observations_by_scale[
                        block_size
                    ].extend(
                        block_observations
                    )

            for block_size in (
                parameters.block_sizes
            ):
                observations = (
                    observations_by_scale[
                        block_size
                    ]
                )

                result = fit_effective_hamiltonian(
                    observations=observations,
                    parameters=fit_parameters,
                )

                _validate_fit_result(
                    policy_name=policy_name,
                    result=result,
                    hamiltonian_preset=(
                        parameters
                        .hamiltonian_preset
                    ),
                )

                parameters_json = json.dumps(
                    {
                        'fit_version':
                            parameters.fit_version,
                        'source_analysis_version':
                            parameters
                            .source_analysis_version,
                        'source_model_version':
                            parameters
                            .source_model_version,
                        'hamiltonian_preset':
                            parameters
                            .hamiltonian_preset.value,
                        'operator_basis':
                            parameters.operator_basis,
                        'block_size':
                            block_size,
                    },
                    sort_keys=True,
                )

                records.append(
                    RgEffectiveHamiltonianFitRecord(
                        fit_analysis_id=(
                            fit_analysis_id
                        ),
                        fit_version=(
                            parameters.fit_version
                        ),
                        source_analysis_id=(
                            source_analysis.analysis_id
                        ),
                        source_model_version=(
                            parameters
                            .source_model_version
                        ),
                        pricing_policy=(
                            policy_name
                        ),
                        block_size=block_size,
                        operator_basis=(
                            parameters.operator_basis
                        ),
                        intercept=result.intercept,
                        quadratic_coefficient=(
                            result
                            .quadratic_coefficient
                        ),
                        quartic_coefficient=(
                            result
                            .quartic_coefficient
                        ),
                        observation_count=(
                            result.observation_count
                        ),
                        trajectory_count=(
                            result.trajectory_count
                        ),
                        design_rank=(
                            result.design_rank
                        ),
                        standardized_condition_number=(
                            result
                            .standardized_condition_number
                        ),
                        train_rmse=result.train_rmse,
                        train_mae=result.train_mae,
                        train_r_squared=(
                            result.train_r_squared
                        ),
                        cv_rmse=result.cv_rmse,
                        cv_mae=result.cv_mae,
                        cv_r_squared=(
                            result.cv_r_squared
                        ),
                        parameters_json=(
                            parameters_json
                        ),
                    )
                )

                total_observations += (
                    result.observation_count
                )

                print(
                    '    '
                    f'''B={block_size:<2} '''
                    f'''c={result.intercept:.8f} '''
                    f'''a={result.quadratic_coefficient:.8f} '''
                    f'''b={result.quartic_coefficient:.8f} '''
                    f'''CV_R2={result.cv_r_squared}'''
                )

            del observations_by_scale

        expected_fit_rows = (
            len(parameters.expected_policies)
            * len(parameters.block_sizes)
        )

        if len(records) != expected_fit_rows:
            raise ValueError(
                'Unexpected effective fit row count: '
                f'''expected={expected_fit_rows}, '''
                f'''actual={len(records)}'''
            )

        self.loader.persist_effective_hamiltonian_fits(
            records=records
        )

        return RgEffectiveHamiltonianSummary(
            fit_analysis_id=fit_analysis_id,
            policies=len(
                parameters.expected_policies
            ),
            block_sizes=len(
                parameters.block_sizes
            ),
            fit_rows=len(records),
            total_observations=(
                total_observations
            ),
        )


def _derive_local_hamiltonian_coefficients(
    hamiltonian_preset: HamiltonianPreset,
):
    engine = build_hamiltonian_engine(
        hamiltonian_preset
    )

    pressure_1 = {
        'EUR': 1.0,
        'GBP': 0.0,
        'USD': 0.0,
    }

    pressure_2 = {
        'EUR': 2.0,
        'GBP': 0.0,
        'USD': 0.0,
    }

    h_1 = engine.evaluate(
        pressure_1
    ).total

    h_2 = engine.evaluate(
        pressure_2
    ).total

    # h(1) = a + b
    # h(2) = 4a + 16b
    quartic = (
        h_2 - 4.0 * h_1
    ) / 12.0

    quadratic = (
        h_1 - quartic
    )

    return quadratic, quartic


def _validate_fit_result(
    policy_name: str,
    result,
    hamiltonian_preset: HamiltonianPreset,
):
    if result.design_rank != 3:
        raise ValueError(
            'Effective Hamiltonian fit '
            'must have full rank: '
            f'''policy={policy_name}, '''
            f'''block_size={result.block_size}, '''
            f'''rank={result.design_rank}'''
        )

    if result.block_size != 1:
        return

    expected_a, expected_b = (
        _derive_local_hamiltonian_coefficients(
            hamiltonian_preset=(
                hamiltonian_preset
            )
        )
    )

    tolerance = 1e-8

    if abs(result.intercept) > tolerance:
        raise ValueError(
            'B=1 intercept recovery failed: '
            f'''policy={policy_name}, '''
            f'''intercept={result.intercept}'''
        )

    if abs(
        result.quadratic_coefficient
        - expected_a
    ) > tolerance:
        raise ValueError(
            'B=1 quadratic coefficient '
            'recovery failed: '
            f'''policy={policy_name}, '''
            f'''expected={expected_a}, '''
            f'''actual='''
            f'''{result.quadratic_coefficient}'''
        )

    if abs(
        result.quartic_coefficient
        - expected_b
    ) > tolerance:
        raise ValueError(
            'B=1 quartic coefficient '
            'recovery failed: '
            f'''policy={policy_name}, '''
            f'''expected={expected_b}, '''
            f'''actual='''
            f'''{result.quartic_coefficient}'''
        )

    if (
        result.cv_r_squared is None
        or abs(
            result.cv_r_squared - 1.0
        ) > 1e-10
    ):
        raise ValueError(
            'B=1 CV R-squared recovery failed: '
            f'''policy={policy_name}, '''
            f'''cv_r_squared='''
            f'''{result.cv_r_squared}'''
        )
