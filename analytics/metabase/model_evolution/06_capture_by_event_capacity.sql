SELECT
    symbol,
    capacity_fraction,
    model_name,
    selected_trade_fraction,
    selected_notional_fraction,
    capture_rate,
    loss_lift,
    captured_loss_per_million_total_notional
FROM gold.v_model_evolution_capture
WHERE metric_scope = 'aggregate'
  AND horizon_seconds = 5
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, capacity_fraction, model_id;
