SELECT
    symbol,
    model,
    round(average_precision, 6) AS average_precision
FROM gold.fact_model_validation_metrics FINAL
WHERE experiment_id = 'coupled_rg_final_v1'
  AND experiment_stage = 'final_test'
  AND metric_scope = 'pooled'
[[AND symbol = {{symbol}}]]
ORDER BY symbol, average_precision;
