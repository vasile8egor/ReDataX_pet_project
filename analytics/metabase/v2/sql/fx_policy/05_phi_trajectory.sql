WITH latest_comparison AS
(
    SELECT argMax(comparison_id, loaded_at) AS comparison_id
    FROM gold.fact_simulation_runs
    WHERE 1 = 1
    [[AND model_version = {{model_version}}]]
    [[AND physics_mode = {{physics_mode}}]]
)
SELECT
    event_index,
    anyIf(phi, pricing_policy = 'naive') AS naive,
    anyIf(phi, pricing_policy = 'inventory_aware') AS inventory_aware,
    anyIf(phi, pricing_policy = 'platform') AS platform
FROM gold.fact_inventory_snapshots
WHERE comparison_id = (SELECT comparison_id FROM latest_comparison)
  AND currency = {{currency}}
GROUP BY event_index
ORDER BY event_index;
