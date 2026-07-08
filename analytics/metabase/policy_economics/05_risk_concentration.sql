SELECT
    symbol AS Market,
    policy_name AS Policy,
    round(risk_concentration, 2) AS "Risk Concentration",
    round(capture_rate * 100, 1) AS "Exposure Capture, %",
    round(acted_notional_fraction * 100, 1) AS "Notional Affected, %"
FROM gold.v_policy_economics_aggregate
WHERE split = 'final'
  AND policy_id IN ('P1', 'P2', 'P3')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, policy_id;
