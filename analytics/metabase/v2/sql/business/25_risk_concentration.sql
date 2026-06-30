SELECT
    round(capacity_fraction * 100, 0) AS capacity_pct,
    model,
    round(capture_rate * 100, 4) AS capture_rate_pct,
    round(selected_notional_fraction * 100, 4)
        AS selected_notional_pct,
    round(risk_concentration, 4)
        AS risk_concentration
FROM gold.fact_business_value_scenarios FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND metric_scope = 'aggregate'
  AND symbol = {{symbol}}
  AND scenario = {{scenario}}
ORDER BY capacity_fraction, model;
