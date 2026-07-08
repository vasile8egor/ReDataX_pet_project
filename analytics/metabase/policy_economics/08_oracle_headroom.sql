SELECT
    symbol AS Market,
    round(model_net_value_per_million_usdt, 2) AS "Model Value / $1M",
    round(oracle_net_value_per_million_usdt, 2) AS "Oracle Value / $1M",
    round(oracle_gap_per_million_usdt, 2) AS "Remaining Headroom / $1M",
    round(oracle_capture_fraction * 100, 1) AS "Oracle Capture, %"
FROM gold.v_research_oracle_gap
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market;
