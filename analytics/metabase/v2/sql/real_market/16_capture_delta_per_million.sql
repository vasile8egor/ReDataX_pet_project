SELECT
    symbol,
    horizon_seconds,
    round(capacity_fraction * 100, 0) AS capacity_pct,
    round(mean_delta, 4) AS delta_loss_per_million_usdt,
    round(ci_lower, 4) AS ci_lower,
    round(ci_upper, 4) AS ci_upper,
    round(positive_day_fraction * 100, 2) AS positive_days_pct
FROM gold.fact_adverse_selection_capture_bootstrap FINAL
WHERE experiment_id = 'adverse_selection_capture_v1'
  AND comparison = 'm1_minus_m0'
  AND metric = 'captured_loss_per_million_total_notional'
[[AND symbol = {{symbol}}]]
[[AND horizon_seconds = {{horizon_seconds}}]]
ORDER BY symbol, horizon_seconds, capacity_fraction;
