SELECT
    symbol,
    model,
    round(roc_auc, 6) AS roc_auc,
    round(average_precision, 6) AS average_precision,
    round(brier_score, 6) AS brier_score,
    round(top_decile_lift, 4) AS top_decile_lift,
    observations
FROM gold.fact_model_validation_metrics FINAL
WHERE experiment_id = 'coupled_rg_final_v1'
  AND experiment_stage = 'final_test'
  AND metric_scope = 'pooled'
[[AND symbol = {{symbol}}]]
ORDER BY symbol, average_precision DESC;
