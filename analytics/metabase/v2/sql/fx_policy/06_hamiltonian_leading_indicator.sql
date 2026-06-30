WITH latest_physics_comparison AS
(
    SELECT argMax(comparison_id, loaded_at) AS comparison_id
    FROM gold.fact_simulation_runs
    WHERE physics_mode != 'none'
),
event_state AS
(
    SELECT
        run_id,
        pricing_policy,
        event_index,
        any(h_total) AS h_total,
        any(regime) AS regime
    FROM gold.fact_inventory_snapshots
    WHERE comparison_id = (
        SELECT comparison_id
        FROM latest_physics_comparison
    )
      AND event_index > 0
      AND h_total IS NOT NULL
    GROUP BY run_id, pricing_policy, event_index
),
future_labeled AS
(
    SELECT
        *,
        max(toUInt8(regime = 'stress')) OVER
        (
            PARTITION BY run_id
            ORDER BY event_index
            ROWS BETWEEN 1 FOLLOWING AND 10 FOLLOWING
        ) AS stress_within_10_events
    FROM event_state
)
SELECT
    pricing_policy AS policy,
    stress_within_10_events,
    round(avg(h_total), 4) AS avg_h_total,
    round(quantileExact(0.5)(h_total), 4) AS median_h_total,
    count() AS observations
FROM future_labeled
GROUP BY pricing_policy, stress_within_10_events
ORDER BY policy, stress_within_10_events;
