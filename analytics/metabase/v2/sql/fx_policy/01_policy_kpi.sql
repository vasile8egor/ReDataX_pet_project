SELECT
    pricing_policy AS policy,
    count() AS runs,
    round(avg(net_pnl_usd), 2) AS avg_net_pnl_usd,
    round(stddevPop(net_pnl_usd), 2) AS pnl_std_usd,
    round(avg(acceptance_rate) * 100, 2) AS acceptance_rate_pct,
    round(avg(average_accepted_spread_bps), 2) AS avg_customer_spread_bps,
    round(avg(stress_time_fraction) * 100, 2) AS stress_time_pct,
    round(avg(max_abs_pressure), 3) AS avg_max_abs_pressure
FROM gold.fact_simulation_runs
WHERE 1 = 1
[[AND model_version = {{model_version}}]]
[[AND physics_mode = {{physics_mode}}]]
GROUP BY pricing_policy
ORDER BY avg_net_pnl_usd DESC;
