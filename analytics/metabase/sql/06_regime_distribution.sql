WITH latest_comparison as (
	SELECT argMax(comparison_id, loaded_at) as comparison_id
	FROM gold.fact_simulation_runs
	WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
),
regime_counts AS (
	SELECT
		pricing_policy,
		regime,
		uniqExact(event_index) as sampled_events
	FROM gold.fact_inventory_snapshots
	WHERE comparison_id = (
		SELECT comparison_id
		FROM latest_comparison
	) AND (event_index > 0)
	GROUP BY pricing_policy, regime
)

SELECT
	pricing_policy,
	regime,
	round(
		sampled_events
		/ sum(sampled_events)
		OVER (PARTITION BY pricing_policy)
		* 100,
		2
	) as regime_pct
FROM regime_counts
ORDER BY pricing_policy, regime
