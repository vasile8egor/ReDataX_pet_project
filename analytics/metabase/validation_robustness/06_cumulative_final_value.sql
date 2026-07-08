SELECT
    metric_date AS Date,
    symbol AS Market,
    cumulative_net_value_per_million_usdt
        AS "Cumulative Daily Value Index"
FROM gold.v_validation_daily_hurdle_path
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Date, Market;
