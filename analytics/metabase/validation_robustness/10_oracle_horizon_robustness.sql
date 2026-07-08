SELECT
    symbol AS Market,
    horizon_seconds AS "Horizon, sec",
    round(notional_budget_fraction * 100, 1) AS "Budget, %",
    round(mean_daily_net_value_per_million_usdt, 2)
        AS "Oracle Mean / $1M",
    round(robust_score, 2) AS "Robust Score / $1M",
    concat(
        '[',
        toString(round(bootstrap_ci_lower, 2)),
        '; ',
        toString(round(bootstrap_ci_upper, 2)),
        ']'
    ) AS "95% CI",
    round(positive_day_fraction * 100, 1) AS "Positive Days, %",
    round(above_break_even_event_fraction * 100, 1) AS "Events Above BE, %",
    if(is_best_by_robust_score = 1, 'Yes', 'No') AS "Best Robust Score",
    if(is_capital_efficient = 1, 'Yes', 'No') AS "Capital Efficient"
FROM gold.v_validation_oracle_horizon_best
WHERE horizon_seconds IN (120, 300, 600)
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, horizon_seconds, notional_budget_fraction;
