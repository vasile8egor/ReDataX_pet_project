SELECT
	pricing_policy as policy,
	round(avg(net_pnl_usd), 2) as avg_net_pnl_usd
FROM gold.v_fx_policy_run_summary
WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
GROUP BY pricing_policy
ORDER BY avg_net_pnl_usd DESC
