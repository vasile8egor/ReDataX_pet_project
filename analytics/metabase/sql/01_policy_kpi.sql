SELECT
	pricing_policy as policy,
	count() as runs,
	round(avg(net_pnl_usd), 2) as avg_net_pnl_usd,
	round(stddevPop(net_pnl_usd), 2) as pnl_std_usd,
	round(avg(acceptance_rate) * 100, 2) as acceptance_rate_pct,
	round(avg(average_accepted_spread_bps), 2) as avg_customer_spread_bps,
	round(avg(stress_time_fraction) * 100, 2) as stress_time_pct,
	round(avg(max_abs_pressure), 3) as avg_max_abs_pressure
FROM gold.v_fx_policy_run_summary
WHERE model_version = 'baseline-v2' AND physics_mode = 'none'
GROUP BY pricing_policy
ORDER BY avg_net_pnl_usd DESC
