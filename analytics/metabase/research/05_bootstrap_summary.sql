SELECT
    symbol,
    comparison_id,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    statistically_positive
FROM gold.v_research_bootstrap_summary
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY symbol, comparison_id;
