SELECT
    split AS Split,
    symbol AS Market,
    policy_name AS Policy,
    days AS Days,
    round(mean_daily_net_value_per_million_usdt, 2) AS "Mean / $1M",
    round(median_daily_net_value_per_million_usdt, 2) AS "Median / $1M",
    round(std_daily_net_value_per_million_usdt, 2) AS "Std / $1M",
    round(minimum_daily_net_value_per_million_usdt, 2) AS "Worst Day / $1M",
    round(maximum_daily_net_value_per_million_usdt, 2) AS "Best Day / $1M",
    round(positive_day_fraction * 100, 1) AS "Positive Days, %"
FROM gold.v_validation_daily_policy_stats
WHERE policy_id IN ('P1', 'P2', 'P3')
  AND split IN ('validation', 'final')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, Split, policy_id;
