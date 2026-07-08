import os
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from clickhouse_driver import Client


MODEL_VERSION = (
    'hamiltonian-observer-v1-'
    'rg-diagnostic-b16-v3'
)

BOOTSTRAP_ITERATIONS = 20_000
RANDOM_SEED = 20260626


QUERY = '''
WITH
    0.9 AS stress_threshold,

base AS
(
    SELECT
        *,

        multiIf(
            local_sign = 'positive'
            AND coarse_sign = 'positive',
            'both_positive',

            local_sign != 'positive'
            AND coarse_sign = 'positive',
            'macro_only',

            local_sign = 'positive'
            AND coarse_sign != 'positive',
            'local_only',

            'both_non_increasing'
        ) AS signal_group

    FROM gold.v_rg_b16_future_stress_features_v1

    WHERE model_version = %(model_version)s
      AND request_accepted = 1
      AND pre_event_max_abs_pressure
          < stress_threshold
),

expanded AS
(
    SELECT
        *,

        tupleElement(
            horizon_record,
            1
        ) AS horizon,

        tupleElement(
            horizon_record,
            2
        ) AS future_max_abs_pressure

    FROM base

    ARRAY JOIN
    [
        tuple(
            toUInt32(16),
            future_max_abs_pressure_16
        ),
        tuple(
            toUInt32(32),
            future_max_abs_pressure_32
        ),
        tuple(
            toUInt32(64),
            future_max_abs_pressure_64
        )
    ] AS horizon_record
),

eligible AS
(
    SELECT
        *,

        future_max_abs_pressure
            >= stress_threshold
            AS future_stress

    FROM expanded

    WHERE event_index + horizon - 1
        <= max_event_index
)

SELECT
    event_dataset_id,
    pricing_policy,
    horizon,
    signal_group,

    count() AS observations,
    countIf(future_stress)
        AS stress_events

FROM eligible

GROUP BY
    event_dataset_id,
    pricing_policy,
    horizon,
    signal_group

ORDER BY
    pricing_policy,
    horizon,
    event_dataset_id,
    signal_group
'''


@dataclass(frozen=True)
class GroupCounts:
    observations: int
    stress_events: int


@dataclass(frozen=True)
class LiftResult:
    estimate: float
    ci_low: float
    ci_high: float
    probability_positive: float
    leave_one_out_min: float
    leave_one_out_max: float


def rate(counts: GroupCounts):
    if counts.observations == 0:
        return float('nan')

    return (
        counts.stress_events
        / counts.observations
    )


def calculate_lift(
    *,
    counts: dict[str, GroupCounts],
    left_group: str,
    right_group: str,
):
    return (
        rate(counts[left_group])
        - rate(counts[right_group])
    )


def combine_datasets(
    *,
    dataset_ids: list[str],
    dataset_counts: dict[
        str,
        dict[str, GroupCounts],
    ],
):
    observations = defaultdict(int)
    stress_events = defaultdict(int)

    for dataset_id in dataset_ids:
        for group, counts in (
            dataset_counts[dataset_id].items()
        ):
            observations[group] += (
                counts.observations
            )
            stress_events[group] += (
                counts.stress_events
            )

    return {
        group: GroupCounts(
            observations=observations[group],
            stress_events=stress_events[group],
        )
        for group in observations
    }


def bootstrap_lift(
    *,
    dataset_counts: dict[
        str,
        dict[str, GroupCounts],
    ],
    left_group: str,
    right_group: str,
    iterations: int,
    seed: int,
):
    dataset_ids = sorted(dataset_counts)

    full_counts = combine_datasets(
        dataset_ids=dataset_ids,
        dataset_counts=dataset_counts,
    )

    estimate = calculate_lift(
        counts=full_counts,
        left_group=left_group,
        right_group=right_group,
    )

    rng = np.random.default_rng(seed)

    bootstrap_values = np.empty(
        iterations,
        dtype=float,
    )

    for index in range(iterations):
        sampled_indices = rng.integers(
            low=0,
            high=len(dataset_ids),
            size=len(dataset_ids),
        )

        sampled_dataset_ids = [
            dataset_ids[item]
            for item in sampled_indices
        ]

        sampled_counts = combine_datasets(
            dataset_ids=sampled_dataset_ids,
            dataset_counts=dataset_counts,
        )

        bootstrap_values[index] = (
            calculate_lift(
                counts=sampled_counts,
                left_group=left_group,
                right_group=right_group,
            )
        )

    leave_one_out_values = []

    for excluded_dataset_id in dataset_ids:
        included = [
            dataset_id
            for dataset_id in dataset_ids
            if dataset_id
            != excluded_dataset_id
        ]

        counts = combine_datasets(
            dataset_ids=included,
            dataset_counts=dataset_counts,
        )

        leave_one_out_values.append(
            calculate_lift(
                counts=counts,
                left_group=left_group,
                right_group=right_group,
            )
        )

    return LiftResult(
        estimate=estimate,
        ci_low=float(
            np.quantile(
                bootstrap_values,
                0.025,
            )
        ),
        ci_high=float(
            np.quantile(
                bootstrap_values,
                0.975,
            )
        ),
        probability_positive=float(
            np.mean(
                bootstrap_values > 0.0
            )
        ),
        leave_one_out_min=min(
            leave_one_out_values
        ),
        leave_one_out_max=max(
            leave_one_out_values
        ),
    )


def main():
    client = Client(
        host=os.getenv(
            'CLICKHOUSE_HOST',
            'clickhouse',
        ),
        port=int(
            os.getenv(
                'CLICKHOUSE_PORT',
                '9000',
            )
        ),
        user=os.getenv(
            'CLICKHOUSE_USER',
            'default',
        ),
        password=os.getenv(
            'CLICKHOUSE_PASSWORD',
            'default',
        ),
    )

    rows = client.execute(
        QUERY,
        {
            'model_version': MODEL_VERSION,
        },
    )

    data = defaultdict(
        lambda: defaultdict(dict)
    )

    for (
        event_dataset_id,
        pricing_policy,
        horizon,
        signal_group,
        observations,
        stress_events,
    ) in rows:
        data[
            (pricing_policy, horizon)
        ][str(event_dataset_id)][
            signal_group
        ] = GroupCounts(
            observations=observations,
            stress_events=stress_events,
        )

    comparisons = (
        (
            'macro_increment',
            'macro_only',
            'both_non_increasing',
        ),
        (
            'coarse_confirmation',
            'both_positive',
            'local_only',
        ),
    )

    for (
        pricing_policy,
        horizon,
    ), dataset_counts in sorted(
        data.items()
    ):
        print()
        print(
            f'''policy={pricing_policy} '''
            f'''horizon={horizon}'''
        )

        if len(dataset_counts) != 10:
            raise ValueError(
                'Expected 10 datasets: '
                f'''actual={len(dataset_counts)}'''
            )

        for (
            comparison_name,
            left_group,
            right_group,
        ) in comparisons:
            result = bootstrap_lift(
                dataset_counts=dataset_counts,
                left_group=left_group,
                right_group=right_group,
                iterations=(
                    BOOTSTRAP_ITERATIONS
                ),
                seed=(
                    RANDOM_SEED
                    + horizon
                    + sum(
                        ord(character)
                        for character
                        in pricing_policy
                    )
                ),
            )

            print(
                f'''  {comparison_name}: '''
                f'''estimate_pp='''
                f'''{100 * result.estimate:.5f} '''
                f'''ci95_pp=['''
                f'''{100 * result.ci_low:.5f}, '''
                f'''{100 * result.ci_high:.5f}] '''
                f'''p_positive='''
                f'''{result.probability_positive:.4f} '''
                f'''loo_pp=['''
                f'''{100 * result.leave_one_out_min:.5f}, '''
                f'''{100 * result.leave_one_out_max:.5f}]'''
            )


if __name__ == '__main__':
    main()
