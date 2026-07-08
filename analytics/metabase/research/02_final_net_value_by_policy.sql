SELECT
    symbol,
    multiIf(
        policy_id = 'P0', 'P0 No action',
        policy_id = 'P1', 'P1 Probability',
        policy_id = 'P2', 'P2 Direct value',
        policy_id = 'P3', 'P3 Hurdle value',
        policy_id = 'P4', 'P4 Oracle',
        policy_id
    ) AS policy,
    net_value_per_million_usdt,
    gross_value_per_million_usdt,
    acted_notional_fraction,
    benefit_cost_ratio
FROM gold.v_research_policy_comparison
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, policy_id;
