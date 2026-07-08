SELECT
    symbol AS Market,
    policy_name AS Policy,
    round(action_cost_bps, 2) AS "Assumed Cost, bps",
    round(break_even_action_cost_bps, 2) AS "Break-even Cost, bps",
    round(action_cost_headroom_bps, 2) AS "Cost Headroom, bps",
    round(benefit_cost_ratio, 2) AS "Benefit / Cost"
FROM gold.v_policy_economics_aggregate
WHERE split = 'final'
  AND policy_id IN ('P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, policy_id;
