SELECT
    model,
    round(capacity_fraction * 100, 0) AS capacity_pct,
    round(selected_trade_fraction * 100, 4)
        AS selected_trade_pct,
    round(selected_notional_fraction * 100, 4)
        AS selected_notional_pct,
    round(capture_rate * 100, 4)
        AS captured_loss_pct,
    round(
        net_protected_value_per_million_total_notional,
        4
    ) AS net_value_per_1m_usdt
FROM gold.fact_business_value_scenarios FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND metric_scope = 'aggregate'
  AND symbol = {{symbol}}
  AND scenario = {{scenario}}
ORDER BY capacity_fraction, model;
