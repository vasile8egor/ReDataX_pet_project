SELECT
    model,
    round(net_protected_value_per_million_total_notional, 4)
        AS net_value_per_1m_usdt,
    round(gross_protected_value_per_million_total_notional, 4)
        AS gross_value_per_1m_usdt,
    round(break_even_action_cost_bps, 4)
        AS break_even_cost_bps,
    round(capture_rate * 100, 4)
        AS captured_loss_pct,
    round(selected_notional_fraction * 100, 4)
        AS selected_notional_pct,
    round(risk_concentration, 4)
        AS risk_concentration,
    round(benefit_cost_ratio, 4)
        AS benefit_cost_ratio
FROM gold.fact_business_value_scenarios FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND metric_scope = 'aggregate'
  AND symbol = {{symbol}}
  AND scenario = {{scenario}}
  AND capacity_fraction = {{capacity_fraction}}
ORDER BY net_value_per_1m_usdt DESC;
