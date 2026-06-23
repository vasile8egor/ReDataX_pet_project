WITH labeled AS(
    SELECT
        run_id,
        pricing_policy,
        regime,

        h_total,
        max_abs_phi,

        max(regime = 'stress') OVER (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN
                1 FOLLOWING
                AND 5 FOLLOWING
        ) AS future_stress_5,

        count(event_index) OVER (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN
                1 FOLLOWING
                AND 5 FOLLOWING
        ) AS future_points

    FROM gold.v_fx_hamiltonian_state

    WHERE model_version =
        'hamiltonian-observer-v1-normal'
)

SELECT
    pricing_policy,

    count() AS observations,

    round(
        corr(h_total, future_stress_5),
        4
    ) AS h_future_stress_correlation,

    round(
        corr(max_abs_phi, future_stress_5),
        4
    ) AS pressure_future_stress_correlation,

    round(
        corr(h_total, max_abs_phi),
        4
    ) AS h_pressure_correlation

FROM labeled

WHERE regime != 'stress'
  AND future_points = 5

GROUP BY pricing_policy

ORDER BY pricing_policy;