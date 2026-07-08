SELECT
    symbol,
    stage,
    horizon_seconds,
    model_preset,
    notional_budget_fraction,
    min_expected_net_margin_bps,
    min_break_even_probability,
    prediction_multiplier,
    mean_daily_net_value_per_million_usdt,
    robust_score,
    positive_day_fraction,
    accepted,
    is_selected
FROM gold.v_research_model_selection_path
WHERE is_selected = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY
    symbol,
    multiIf(stage = 'development', 1, stage = 'validation', 2, 3),
    horizon_seconds;
