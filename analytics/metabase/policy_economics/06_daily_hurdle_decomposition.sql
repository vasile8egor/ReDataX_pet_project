SELECT
    metric_date AS Date,
    symbol AS Market,
    gross_value_per_million_usdt AS "Gross Value / $1M",
    -action_cost_per_million_usdt AS "Action Cost / $1M",
    net_value_per_million_usdt AS "Net Value / $1M"
FROM gold.v_policy_economics_daily
WHERE split = 'final'
  AND policy_id = 'P3'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Date, Market;
