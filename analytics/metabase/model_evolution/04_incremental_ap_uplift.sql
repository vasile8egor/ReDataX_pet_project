SELECT
    symbol,
    comparison_name,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    statistically_positive,
    statistically_negative
FROM gold.v_model_evolution_bootstrap
WHERE metric = 'average_precision'
  AND horizon_seconds = 5
  AND (
        (experiment_family = 'local_oos' AND experiment_stage = 'test')
        OR
        (experiment_family = 'cross_market' AND experiment_stage = 'final_test')
      )
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, comparison_order;
