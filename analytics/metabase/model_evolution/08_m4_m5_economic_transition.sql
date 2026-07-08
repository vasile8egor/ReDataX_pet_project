SELECT
    symbol,
    policy_id,
    policy_name,
    model_id,
    acted_notional_fraction,
    capture_rate,
    net_value_per_million_usdt,
    benefit_cost_ratio
FROM gold.v_research_policy_comparison
WHERE split = 'final'
  AND policy_id IN ('P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, policy_id;
