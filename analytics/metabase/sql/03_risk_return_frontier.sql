SELECT
	pricing_policy as policy,
	toString(comparison_id) as comparison_id,
	round(avg(stress_time_fraction) * 100, 2) as stress_time_pct,
	round(avg(net_pnl_usd), 2) as avg_net_pnl_usd
FROM gold.v_fx_policy_run_summary
WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
GROUP BY pricing_policy, comparison_id
