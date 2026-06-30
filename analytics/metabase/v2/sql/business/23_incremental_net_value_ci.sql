SELECT
    round(capacity_fraction * 100, 0) AS capacity_pct,
    comparison,
    round(mean_delta, 4) AS delta_net_value_per_1m_usdt,
    round(ci_lower, 4) AS ci_lower,
    round(ci_upper, 4) AS ci_upper,
    round(positive_day_fraction * 100, 2)
        AS positive_days_pct
FROM gold.fact_business_value_bootstrap FINAL
WHERE experiment_id = 'coupled_business_value_v1'
  AND symbol = {{symbol}}
  AND scenario = {{scenario}}
  AND metric =
      'net_protected_value_per_million_total_notional'
ORDER BY capacity_fraction, comparison;
