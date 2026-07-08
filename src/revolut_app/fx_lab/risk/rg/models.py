from dataclasses import dataclass
from math import isfinite
from typing import Mapping
from enum import Enum


class TransitionRiskSign(str, Enum):
    NEGATIVE = 'negative'
    ZERO = 'zero'
    POSITIVE = 'positive'


@dataclass(frozen=True)
class ScaleAwareTransitionDiagnostic:
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

    local_sign: TransitionRiskSign
    coarse_sign: TransitionRiskSign
    sign_agreement: bool


@dataclass(frozen=True)
class EffectiveHamiltonianCoefficients:
    block_size: int

    intercept: float
    quadratic: float
    quartic: float

    def __post_init__(self):
        if self.block_size <= 0:
            raise ValueError(
                'block_size must be positive'
            )

        for label, value in (
            ('intercept', self.intercept),
            ('quadratic', self.quadratic),
            ('quartic', self.quartic),
        ):
            if not isfinite(value):
                raise ValueError(
                    'Effective Hamiltonian '
                    'coefficient must be finite: '
                    f'''{label}={value}'''
                )


@dataclass(frozen=True)
class ScaleAwareTransition:
    block_size: int
    history_ready: bool

    coarse_pressure_before: dict[str, float]

    coarse_pressure_after_if_rejected: dict[str, float]
    coarse_pressure_after_if_accepted: dict[str, float]

    coarse_h_before: float
    coarse_h_after_if_rejected: float
    coarse_h_after_if_accepted: float

    temporal_drift_delta_h: float
    request_delta_h: float
    total_accepted_delta_h: float

    normalized_temporal_drift_delta_h: float
    normalized_request_delta_h: float
    normalized_total_accepted_delta_h: float


@dataclass(frozen=True)
class EffectiveHamiltonianObservation:
    trajectory_id: str
    block_size: int

    quadratic_invariant: float
    quartic_invariant: float

    target_mean_h: float


@dataclass(frozen=True)
class EffectiveHamiltonianFitResult:
    block_size: int

    intercept: float
    quadratic_coefficient: float
    quartic_coefficient: float

    observation_count: int
    trajectory_count: int

    design_rank: int
    standardized_condition_number: float

    train_rmse: float
    train_mae: float
    train_r_squared: float | None

    cv_rmse: float
    cv_mae: float
    cv_r_squared: float | None


@dataclass(frozen=True)
class EffectiveHamiltonianFitParameters:
    require_full_rank: bool = True
    minimum_trajectories_for_cv: int = 2

    def __post_init__(self):
        if self.minimum_trajectories_for_cv < 2:
            raise ValueError(
                'minimum_trajectories_for_cv '
                'must be at least 2'
            )


@dataclass(frozen=True)
class CurrencyScaleObservables:
    currency: str

    mean_coarse_pressure: float
    coarse_second_moment: float
    coarse_fourth_moment: float
    coarse_variance: float

    mean_micro_second_moment: float
    mean_internal_variance: float

    second_moment_decomposition_error: float


@dataclass(frozen=True)
class ScaleObservables:
    block_size: int
    block_count: int

    frames_used: int
    frames_dropped: int

    currencies: dict[
        str,
        CurrencyScaleObservables,
    ]

    trace_coarse_covariance: float
    mean_coarse_norm_squared: float
    mean_internal_variance_total: float

    mean_max_abs_coarse_pressure: float
    coarse_stress_fraction: float

    mean_micro_h_total: float | None
    mean_coarse_h_total: float | None
    mean_unresolved_h_total: float | None


@dataclass(frozen=True)
class VarianceScalingExponent:
    dimension: str

    from_block_size: int
    to_block_size: int

    variance_from: float
    variance_to: float

    exponent: float | None


@dataclass(frozen=True)
class MultiscaleTrajectoryObservables:
    trajectory_id: str
    frame_count: int

    scales: tuple[ScaleObservables, ...]
    variance_scaling: tuple[VarianceScalingExponent, ...]


@dataclass(frozen=True)
class MultiscaleAnalysisParameters:
    block_sizes: tuple[int, ...] = (
        1, 2, 4, 8, 16, 32, 64
    )
    stress_pressure_threshold: float = 0.9

    def __post_init__(self):
        if not self.block_sizes:
            raise ValueError(
                'block_sizes cannot be empty'
            )

        if any(
            block_size <= 0
            for block_size in self.block_sizes
        ):
            raise ValueError(
                'Every block size must be positive'
            )

        if len(set(self.block_sizes)) != len(
            self.block_sizes
        ):
            raise ValueError(
                'block_sizes must be unique'
            )

        if tuple(sorted(self.block_sizes)) != (
            self.block_sizes
        ):
            raise ValueError(
                'block_sizes must be increasing'
            )

        if (
            not isfinite(self.stress_pressure_threshold)
            or self.stress_pressure_threshold <= 0.0
        ):
            raise ValueError(
                'stress_pressure_threshold '
                'must be positive'
            )


@dataclass(frozen=True)
class PressureObservation:
    trajectory_id: str
    event_index: int
    currency: str
    pressure: float
    h_total: float | None


@dataclass(frozen=True)
class TrajectoryExtractionParameters:
    expected_currencies: tuple[str, ...] | None = None
    include_initial_frame: bool = False
    require_contiguous_event_indices: bool = True

    hamiltonian_tolerance: float = 1e-10

    def __post_init__(self):
        if (
            self.expected_currencies is not None
            and not self.expected_currencies
        ):
            raise ValueError(
                'expected_currencies cannot be empty'
            )

        if len(
            set(self.expected_currencies or ())
        ) != len(self.expected_currencies or ()):
            raise ValueError(
                'expected_currencies must be unique'
            )

        if (
            not isfinite(self.hamiltonian_tolerance)
            or self.hamiltonian_tolerance < 0.0
        ):
            raise ValueError(
                'hamiltonian_tolerance must be non-negative'
            )


@dataclass(frozen=True)
class PressureFrame:
    event_index: int
    pressures: Mapping[str, float]
    h_total: float | None = None


@dataclass(frozen=True)
class CoarsePressureBlock:
    block_index: int

    start_event_index: int
    end_event_index: int
    event_count: int

    mean_pressures: dict[str, float]
    second_moments: dict[str, float]
    fourth_moments: dict[str, float]
    variances: dict[str, float]

    mean_h_total: float | None


@dataclass(frozen=True)
class TemporalCoarseGrainingParameters:
    block_size: int
    drop_incomplete_block: bool = True

    def __post_init__(self):
        if self.block_size <= 0:
            raise ValueError(
                'block_size must be positive'
            )


@dataclass
class RGFlowPoint:
    window_size: int
    currency: str
    mean_phi: float
    var_phi: float
    autocorr_lag1: float
    stress_probability: float
