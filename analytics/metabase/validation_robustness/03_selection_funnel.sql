SELECT
    symbol AS Market,
    stage AS Stage,
    horizon_seconds AS "Horizon, sec",
    candidates_recorded AS "Leaderboard Rows Stored",
    accepted_among_recorded AS "Accepted Among Stored",
    selected_candidates AS "Selected",
    selected_model_preset AS "Selected Model",
    round(selected_budget_fraction * 100, 1) AS "Budget, %",
    round(selected_margin_bps, 2) AS "Margin, bps",
    round(selected_break_even_probability * 100, 1) AS "Min P(BE), %",
    round(selected_mean_daily_value, 2) AS "Mean Daily Value / $1M",
    round(selected_robust_score, 2) AS "Robust Score / $1M",
    round(selected_positive_day_fraction * 100, 1) AS "Positive Days, %"
FROM gold.v_validation_selection_funnel
WHERE stage IN ('development', 'validation')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, stage_order, horizon_seconds;
