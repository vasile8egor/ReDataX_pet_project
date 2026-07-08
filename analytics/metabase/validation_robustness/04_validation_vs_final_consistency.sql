SELECT
    symbol AS Market,
    horizon_seconds AS "Horizon, sec",
    round(validation_mean_daily_value, 2) AS "Validation Mean / $1M",
    round(validation_std_daily_value, 2) AS "Validation Std / $1M",
    round(validation_positive_day_fraction * 100, 1)
        AS "Validation Positive Days, %",
    round(final_mean_daily_value, 2) AS "Final Mean / $1M",
    round(final_std_daily_value, 2) AS "Final Std / $1M",
    round(final_positive_day_fraction * 100, 1)
        AS "Final Positive Days, %",
    round(final_minus_validation_mean, 2)
        AS "Final - Validation / $1M",
    if(direction_consistent = 1, 'Yes', 'No')
        AS "Direction Consistent",
    if(final_profitable_majority = 1, 'Yes', 'No')
        AS "Final Majority Positive"
FROM gold.v_validation_final_consistency
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market;
