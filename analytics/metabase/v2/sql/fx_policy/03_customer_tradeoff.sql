SELECT
    pricing_policy AS policy,
    toString(comparison_id) AS comparison_id,
    round(average_accepted_spread_bps, 2) AS customer_spread_bps,
    round(acceptance_rate * 100, 2) AS acceptance_rate_pct,
    round(net_pnl_usd, 2) AS net_pnl_usd
FROM gold.fact_simulation_runs
WHERE 1 = 1
[[AND model_version = {{model_version}}]]
[[AND physics_mode = {{physics_mode}}]]
ORDER BY comparison_id, policy;
