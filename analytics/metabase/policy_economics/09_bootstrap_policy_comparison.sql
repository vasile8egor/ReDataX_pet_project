SELECT
    symbol AS Market,
    multiIf(
        comparison_id = 'hurdle_minus_no_action', 'Hurdle vs No Action',
        comparison_id = 'hurdle_minus_probability', 'Hurdle vs Probability',
        comparison_id = 'hurdle_minus_direct', 'Hurdle vs Direct',
        comparison_id
    ) AS Comparison,
    round(mean_delta, 2) AS "Mean Daily Difference",
    concat(
        '[',
        toString(round(ci_lower, 2)),
        '; ',
        toString(round(ci_upper, 2)),
        ']'
    ) AS "95% CI",
    round(positive_day_fraction * 100, 1) AS "Positive Days, %",
    multiIf(
        ci_lower > 0, 'Positive',
        ci_upper < 0, 'Negative',
        'Not significant'
    ) AS Inference
FROM gold.v_research_bootstrap_summary
WHERE split = 'final'
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, comparison_id;
