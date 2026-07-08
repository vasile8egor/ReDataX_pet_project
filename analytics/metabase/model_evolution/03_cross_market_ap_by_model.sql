SELECT symbol, model_name, average_precision
FROM gold.v_model_evolution_predictive
WHERE experiment_family = 'cross_market'
  AND experiment_stage = 'final_test'
  AND metric_scope = 'pooled'
  AND horizon_seconds = 5
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, model_order;
