SELECT
    symbol AS Market,
    policy_name AS Policy,
    acted_notional_fraction,
    capture_rate,
    risk_concentration,
    net_value_per_million_usdt
FROM gold.v_policy_economics_aggregate
WHERE split = 'final'
  AND policy_id IN ('P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, policy_id;
