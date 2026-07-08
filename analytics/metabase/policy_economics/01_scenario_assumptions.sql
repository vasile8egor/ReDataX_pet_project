SELECT
    symbol AS Market,
    horizon_seconds AS "Horizon, sec",
    round(internalization_rate * 100, 1) AS "Internalization, %",
    round(mitigation_efficiency * 100, 1) AS "Mitigation, %",
    round(action_cost_bps, 2) AS "Action Cost, bps",
    round(break_even_markout_bps, 2) AS "Break-even Markout, bps"
FROM gold.v_policy_economics_selected
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market;
