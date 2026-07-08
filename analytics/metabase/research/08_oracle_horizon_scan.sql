SELECT
    symbol,
    horizon_seconds,
    notional_budget_fraction,
    mean_daily_net_value_per_million_usdt,
    robust_score,
    bootstrap_ci_lower,
    bootstrap_ci_upper,
    positive_day_fraction,
    above_break_even_event_fraction,
    strictly_feasible
FROM gold.fact_research_oracle_horizon FINAL
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, horizon_seconds, notional_budget_fraction;
