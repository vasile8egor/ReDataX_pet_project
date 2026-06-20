WITH latest_comparison as (
	SELECT argMax(comparison_id, loaded_at) as comparison_id
	FROM gold.fact_simulation_runs
	WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
)

SELECT
	event_index,
	anyIf(phi, pricing_policy = 'naive') as naive,
	anyIf(phi, pricing_policy = 'inventory_aware') as inventory_aware,
	anyIf(phi, pricing_policy = 'platform') as platform
FROM gold.v_fx_inventory_trajectory
WHERE comparison_id = (
	SELECT comparison_id
	FROM latest_comparison
) AND (currency = 'EUR')
GROUP BY event_index
ORDER BY event_index
