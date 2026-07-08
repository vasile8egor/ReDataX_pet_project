SELECT
    symbol,
    capacity_fraction,
    metric,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    statistically_positive
FROM gold.v_model_evolution_capture_bootstrap
WHERE horizon_seconds = 5
  AND metric IN ('capture_rate', 'captured_loss_per_million_total_notional')
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, capacity_fraction, metric;
