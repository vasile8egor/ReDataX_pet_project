SELECT
    symbol,
    model_net_value_per_million_usdt,
    oracle_net_value_per_million_usdt,
    oracle_gap_per_million_usdt,
    oracle_capture_fraction
FROM gold.v_research_oracle_gap
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol;
