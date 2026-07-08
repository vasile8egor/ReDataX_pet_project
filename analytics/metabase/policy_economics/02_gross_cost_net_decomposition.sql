SELECT
    symbol AS Market,
    policy_name AS Policy,
    metric,
    value_per_million_usdt
FROM
(
    SELECT experiment_id, symbol, policy_id, policy_name,
           'Gross protected value' AS metric,
           gross_value_per_million_usdt AS value_per_million_usdt
    FROM gold.v_policy_economics_aggregate
    WHERE split = 'final' AND policy_id IN ('P1', 'P2', 'P3')

    UNION ALL

    SELECT experiment_id, symbol, policy_id, policy_name,
           'Action cost' AS metric,
           -action_cost_per_million_usdt AS value_per_million_usdt
    FROM gold.v_policy_economics_aggregate
    WHERE split = 'final' AND policy_id IN ('P1', 'P2', 'P3')

    UNION ALL

    SELECT experiment_id, symbol, policy_id, policy_name,
           'Net value' AS metric,
           net_value_per_million_usdt AS value_per_million_usdt
    FROM gold.v_policy_economics_aggregate
    WHERE split = 'final' AND policy_id IN ('P1', 'P2', 'P3')
)
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, policy_id, metric;
