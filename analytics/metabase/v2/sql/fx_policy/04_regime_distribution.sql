WITH regime_counts AS
(
    SELECT
        pricing_policy,
        regime,
        uniqExact((run_id, event_index)) AS sampled_events
    FROM gold.fact_inventory_snapshots
    WHERE event_index > 0
    [[AND model_version = {{model_version}}]]
    [[AND physics_mode = {{physics_mode}}]]
    GROUP BY pricing_policy, regime
)
SELECT
    pricing_policy AS policy,
    regime,
    round(
        sampled_events
        / sum(sampled_events) OVER (PARTITION BY pricing_policy)
        * 100,
        2
    ) AS regime_pct
FROM regime_counts
ORDER BY policy, regime;
