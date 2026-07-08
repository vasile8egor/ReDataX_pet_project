SELECT
    symbol,
    policy_id,
    policy_name,
    acted_notional_fraction,
    net_value_per_million_usdt,
    capture_rate,
    risk_concentration,
    benefit_cost_ratio
FROM gold.v_research_intervention_frontier
WHERE split = 'final'
  AND policy_id IN ('P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, acted_notional_fraction;
