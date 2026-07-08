SELECT
    metric_date AS Date,
    symbol AS Market,
    split AS Split,
    net_value_per_million_usdt AS "Net Value / $1M"
FROM gold.v_validation_daily_hurdle_path
WHERE split IN ('validation', 'final')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Date, Market, Split;
