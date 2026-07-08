SELECT
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    aggregate_net_value_per_million_usdt,
    mean_daily_uplift_per_million_usdt,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    acted_notional_fraction,
    capture_rate,
    benefit_cost_ratio,
    oracle_capture_fraction,
    action_cost_bps,
    break_even_action_cost_bps
FROM gold.v_research_final_summary
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol;
