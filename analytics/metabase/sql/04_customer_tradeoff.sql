SELECT
	pricing_policy as policy,
	toString(comparison_id) as comparison_id,
	round(average_accepted_spread_bps, 2) as customer_spread_bps,
	round(acceptance_rate * 100, 2) as acceptance_rate_pct
FROM gold.v_fx_policy_run_summary
WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
