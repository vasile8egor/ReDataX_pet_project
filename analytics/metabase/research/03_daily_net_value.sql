SELECT
    metric_date,
    symbol,
    policy_id,
    policy_name,
    net_value_per_million_usdt
FROM gold.v_research_daily_value
WHERE split = 'final'
  AND policy_id IN ('P0', 'P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY metric_date, symbol, policy_id;
