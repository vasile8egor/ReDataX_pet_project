SELECT
    symbol,
    comparison,
    round(mean_delta, 6) AS mean_delta_ap,
    round(ci_lower, 6) AS ci_lower,
    round(ci_upper, 6) AS ci_upper,
    round(positive_day_fraction * 100, 2) AS positive_days_pct
FROM gold.fact_model_comparison_bootstrap FINAL
WHERE experiment_id = 'coupled_rg_final_v1'
  AND experiment_stage = 'final_test'
  AND metric = 'average_precision'
[[AND symbol = {{symbol}}]]
ORDER BY symbol, comparison;
