SELECT
    scenario,
    model,
    round(
        net_protected_value_per_million_total_notional,
        4
    ) AS net_value_per_1m_usdt,
    round(break_even_action_cost_bps, 4)
        AS break_even_action_cost_bps,
    round(benefit_cost_ratio, 4)
        AS benefit_cost_ratio
FROM gold.fact_business_value_scenarios FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND metric_scope = 'aggregate'
  AND symbol = {{symbol}}
  AND capacity_fraction = {{capacity_fraction}}
ORDER BY scenario, model;
