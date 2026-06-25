from __future__ import annotations

from math import sqrt
from typing import Iterable

import numpy as np

from revolut_app.fx_lab.risk.rg.models import (
    CoarsePressureBlock,
    EffectiveHamiltonianFitParameters,
    EffectiveHamiltonianFitResult,
    EffectiveHamiltonianObservation,
)


def build_effective_hamiltonian_observations(
    *,
    trajectory_id: str,
    block_size: int,
    blocks: Iterable[CoarsePressureBlock],
) -> list[EffectiveHamiltonianObservation]:
    if not trajectory_id:
        raise ValueError(
            "trajectory_id cannot be empty"
        )

    if block_size <= 0:
        raise ValueError(
            "block_size must be positive"
        )

    observations: list[
        EffectiveHamiltonianObservation
    ] = []

    for block in blocks:
        if block.mean_h_total is None:
            raise ValueError(
                "Effective Hamiltonian fitting "
                "requires mean_h_total"
            )

        quadratic_invariant = sum(
            value**2
            for value
            in block.mean_pressures.values()
        )

        quartic_invariant = sum(
            value**4
            for value
            in block.mean_pressures.values()
        )

        observations.append(
            EffectiveHamiltonianObservation(
                trajectory_id=trajectory_id,
                block_size=block_size,
                quadratic_invariant=(
                    quadratic_invariant
                ),
                quartic_invariant=(
                    quartic_invariant
                ),
                target_mean_h=(
                    block.mean_h_total
                ),
            )
        )

    if not observations:
        raise ValueError(
            "No coarse blocks provided"
        )

    return observations


def fit_effective_hamiltonian(
    *,
    observations: Iterable[
        EffectiveHamiltonianObservation
    ],
    parameters: EffectiveHamiltonianFitParameters = (
        EffectiveHamiltonianFitParameters()
    ),
) -> EffectiveHamiltonianFitResult:
    resolved = list(observations)

    if not resolved:
        raise ValueError(
            "observations cannot be empty"
        )

    block_sizes = {
        item.block_size
        for item in resolved
    }

    if len(block_sizes) != 1:
        raise ValueError(
            "All observations must have "
            "the same block_size"
        )

    block_size = next(iter(block_sizes))

    trajectory_ids = sorted(
        {
            item.trajectory_id
            for item in resolved
        }
    )

    if len(trajectory_ids) < (
        parameters.minimum_trajectories_for_cv
    ):
        raise ValueError(
            "Not enough trajectories for "
            "leave-one-trajectory-out validation"
        )

    design, targets = _build_design(
        resolved
    )

    coefficients, rank = _fit_linear_model(
        design=design,
        targets=targets,
    )

    if (
        parameters.require_full_rank
        and rank != design.shape[1]
    ):
        raise ValueError(
            "Effective Hamiltonian design "
            "matrix is rank deficient: "
            f"rank={rank}, "
            f"columns={design.shape[1]}"
        )

    predictions = design @ coefficients

    train_rmse, train_mae, train_r_squared = (
        _calculate_metrics(
            targets=targets,
            predictions=predictions,
        )
    )

    cv_targets: list[float] = []
    cv_predictions: list[float] = []

    for held_out_id in trajectory_ids:
        train_items = [
            item
            for item in resolved
            if item.trajectory_id
            != held_out_id
        ]

        test_items = [
            item
            for item in resolved
            if item.trajectory_id
            == held_out_id
        ]

        train_design, train_targets = (
            _build_design(train_items)
        )

        test_design, test_targets = (
            _build_design(test_items)
        )

        fold_coefficients, fold_rank = (
            _fit_linear_model(
                design=train_design,
                targets=train_targets,
            )
        )

        if (
            parameters.require_full_rank
            and fold_rank
            != train_design.shape[1]
        ):
            raise ValueError(
                "Cross-validation design "
                "matrix is rank deficient: "
                f"held_out={held_out_id}, "
                f"rank={fold_rank}"
            )

        fold_predictions = (
            test_design @ fold_coefficients
        )

        cv_targets.extend(
            test_targets.tolist()
        )

        cv_predictions.extend(
            fold_predictions.tolist()
        )

    cv_rmse, cv_mae, cv_r_squared = (
        _calculate_metrics(
            targets=np.asarray(
                cv_targets,
                dtype=float,
            ),
            predictions=np.asarray(
                cv_predictions,
                dtype=float,
            ),
        )
    )

    return EffectiveHamiltonianFitResult(
        block_size=block_size,
        intercept=float(coefficients[0]),
        quadratic_coefficient=float(
            coefficients[1]
        ),
        quartic_coefficient=float(
            coefficients[2]
        ),
        observation_count=len(resolved),
        trajectory_count=len(
            trajectory_ids
        ),
        design_rank=int(rank),
        standardized_condition_number=(
            _standardized_condition_number(
                observations=resolved
            )
        ),
        train_rmse=train_rmse,
        train_mae=train_mae,
        train_r_squared=train_r_squared,
        cv_rmse=cv_rmse,
        cv_mae=cv_mae,
        cv_r_squared=cv_r_squared,
    )


def _build_design(
    observations: list[
        EffectiveHamiltonianObservation
    ],
) -> tuple[np.ndarray, np.ndarray]:
    design = np.asarray(
        [
            [
                1.0,
                item.quadratic_invariant,
                item.quartic_invariant,
            ]
            for item in observations
        ],
        dtype=float,
    )

    targets = np.asarray(
        [
            item.target_mean_h
            for item in observations
        ],
        dtype=float,
    )

    return design, targets


def _fit_linear_model(
    *,
    design: np.ndarray,
    targets: np.ndarray,
) -> tuple[np.ndarray, int]:
    coefficients, _, rank, _ = (
        np.linalg.lstsq(
            design,
            targets,
            rcond=None,
        )
    )

    return coefficients, int(rank)


def _calculate_metrics(
    *,
    targets: np.ndarray,
    predictions: np.ndarray,
) -> tuple[float, float, float | None]:
    residuals = (
        targets - predictions
    )

    rmse = sqrt(
        float(np.mean(residuals**2))
    )

    mae = float(
        np.mean(np.abs(residuals))
    )

    centered = (
        targets - np.mean(targets)
    )

    total_sum_squares = float(
        np.sum(centered**2)
    )

    if total_sum_squares <= 0.0:
        r_squared = None
    else:
        residual_sum_squares = float(
            np.sum(residuals**2)
        )

        r_squared = (
            1.0
            - residual_sum_squares
            / total_sum_squares
        )

    return rmse, mae, r_squared


def _standardized_condition_number(
    *,
    observations: list[
        EffectiveHamiltonianObservation
    ],
) -> float:
    features = np.asarray(
        [
            [
                item.quadratic_invariant,
                item.quartic_invariant,
            ]
            for item in observations
        ],
        dtype=float,
    )

    means = np.mean(
        features,
        axis=0,
    )

    standard_deviations = np.std(
        features,
        axis=0,
    )

    if np.any(
        standard_deviations <= 1e-15
    ):
        return float("inf")

    standardized = (
        features - means
    ) / standard_deviations

    standardized_design = (
        np.column_stack(
            [
                np.ones(
                    standardized.shape[0]
                ),
                standardized,
            ]
        )
    )

    return float(
        np.linalg.cond(
            standardized_design
        )
    )
