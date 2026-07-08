SELECT
    symbol AS Market,
    policy_name AS Policy,
    round(net_value_per_million_usdt, 2) AS "Net Value / $1M",
    round(acted_notional_fraction * 100, 1) AS "Notional Affected, %",
    round(capture_rate * 100, 1) AS "Exposure Captured, %",
    round(risk_concentration, 2) AS "Risk Concentration",
    round(benefit_cost_ratio, 2) AS "Benefit / Cost",
    round(break_even_action_cost_bps, 2) AS "Break-even Cost, bps"
FROM gold.v_policy_economics_aggregate
WHERE split = 'final'
  AND policy_id IN ('P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, policy_id;
