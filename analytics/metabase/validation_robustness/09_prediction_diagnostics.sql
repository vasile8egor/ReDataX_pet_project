SELECT
    split AS Split,
    symbol AS Market,
    horizon_seconds AS "Horizon, sec",
    days AS Days,
    round(mean_probability_positive, 3) AS "Mean P(markout > 0)",
    round(mean_probability_break_even, 3) AS "Mean P(markout > BE)",
    round(mean_expected_positive_markout_p95_bps, 2)
        AS "Expected Markout P95, bps",
    round(maximum_expected_positive_markout_bps, 2)
        AS "Maximum Expected Markout, bps",
    round(mean_hurdle_predicted_net_positive_fraction * 100, 1)
        AS "Hurdle Predicted Positive, %",
    round(mean_direct_predicted_net_positive_fraction * 100, 1)
        AS "Direct Predicted Positive, %"
FROM gold.v_validation_prediction_diagnostics_summary
WHERE split IN ('validation', 'final')
  [[AND experiment_id = {{experiment_id}}]]
  [[AND symbol = {{symbol}}]]
ORDER BY Market, Split;
