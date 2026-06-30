SELECT
    symbol,
    horizon_seconds,
    round(capacity_fraction * 100, 0) AS capacity_pct,
    model,
    round(capture_rate * 100, 4) AS capture_rate_pct,
    round(selected_notional_fraction * 100, 4) AS selected_notional_pct
FROM gold.fact_adverse_selection_capture FINAL
WHERE experiment_id = 'adverse_selection_capture_v1'
  AND metric_scope = 'aggregate'
[[AND symbol = {{symbol}}]]
[[AND horizon_seconds = {{horizon_seconds}}]]
ORDER BY symbol, horizon_seconds, capacity_fraction, model;
