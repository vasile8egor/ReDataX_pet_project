SELECT
    round(capacity_fraction * 100, 0) AS capacity_pct,
    model,
    round(break_even_action_cost_bps, 4)
        AS break_even_action_cost_bps,
    round(action_cost_bps, 4)
        AS assumed_action_cost_bps
FROM gold.fact_business_value_scenarios FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND metric_scope = 'aggregate'
  AND symbol = {{symbol}}
  AND scenario = {{scenario}}
ORDER BY capacity_fraction, model;
