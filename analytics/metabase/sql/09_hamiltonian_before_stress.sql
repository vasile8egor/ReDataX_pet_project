WITH numbered AS (
    SELECT
        *,

        row_number() OVER (
            PARTITION BY run_id
            ORDER BY event_index
        ) AS snapshot_number,

        lagInFrame(
            regime,
            1,
            'calm'
        ) OVER (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN
                UNBOUNDED PRECEDING
                AND UNBOUNDED FOLLOWING
        ) AS previous_regime

    FROM gold.v_fx_hamiltonian_state

    WHERE model_version =
        'hamiltonian-observer-v1-normal'
),

onsets AS (
    SELECT
        run_id,
        pricing_policy,
        snapshot_number AS onset_snapshot
    FROM numbered
    WHERE regime = 'stress'
      AND previous_regime != 'stress'
),

aligned AS (
    SELECT
        states.pricing_policy,

        states.snapshot_number
            - onsets.onset_snapshot
            AS relative_snapshot,

        states.h_total,
        states.max_abs_phi

    FROM numbered AS states

    INNER JOIN onsets
        ON states.run_id = onsets.run_id

    WHERE states.snapshot_number
          BETWEEN
              onsets.onset_snapshot - 10
              AND onsets.onset_snapshot + 3
)

SELECT
    pricing_policy,
    relative_snapshot,

    count() AS observations,

    round(avg(h_total), 4)
        AS avg_h,

    round(avg(max_abs_phi), 4)
        AS avg_max_abs_phi

FROM aligned

GROUP BY
    pricing_policy,
    relative_snapshot

ORDER BY
    pricing_policy,
    relative_snapshot;