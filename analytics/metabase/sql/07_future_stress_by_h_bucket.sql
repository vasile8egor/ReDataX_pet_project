WITH labeled AS (
    SELECT
        run_id,
        event_dataset_id,
        pricing_policy,
        event_index,
        snapshot_ts,
        regime,

        h_total,
        max_abs_phi,

        max(regime = 'stress') OVER
        (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN
                1 FOLLOWING
                AND 5 FOLLOWING
        ) AS future_stress_5,

        count(event_index) OVER
        (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN
                1 FOLLOWING
                AND 5 FOLLOWING
        ) AS future_points

    FROM gold.v_fx_hamiltonian_state

    WHERE model_version =
        'hamiltonian-observer-v1-normal'
),

eligible AS (
    SELECT
        *
    FROM labeled
    WHERE regime != 'stress'
      AND future_points = 5
),

ranked AS (
    SELECT
        *,

        row_number() OVER
        (
            PARTITION BY pricing_policy
            ORDER BY h_total
        ) AS score_rank,

        count() OVER
        (
            PARTITION BY pricing_policy
        ) AS score_count

    FROM eligible
),

bucketed AS (
    SELECT
        *,

        least(
            10,
            intDiv(
                (score_rank - 1) * 10,
                score_count
            ) + 1
        ) AS h_decile

    FROM ranked
)

SELECT
    pricing_policy,
    h_decile,

    count() AS observations,

    round(avg(h_total), 4)
        AS avg_h,

    round(avg(max_abs_phi), 4)
        AS avg_max_abs_phi,

    round(avg(future_stress_5) * 100, 2)
        AS future_stress_rate_pct

FROM bucketed

GROUP BY
    pricing_policy,
    h_decile

ORDER BY
    pricing_policy,
    h_decile;