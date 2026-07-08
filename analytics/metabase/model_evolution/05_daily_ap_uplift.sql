WITH daily AS
(
    SELECT
        experiment_id,
        experiment_family,
        experiment_stage,
        metric_date,
        symbol,
        horizon_seconds,
        source_model,
        average_precision
    FROM gold.v_model_evolution_predictive
    WHERE metric_scope = 'daily'
      AND horizon_seconds = 5
      AND (
            (experiment_family = 'local_oos' AND experiment_stage = 'test')
            OR
            (experiment_family = 'cross_market' AND experiment_stage = 'final_test')
          )
      [[AND symbol = {{symbol}}]]
)
SELECT
    current.metric_date,
    current.symbol,
    current.comparison_name,
    current.average_precision - baseline.average_precision AS daily_ap_delta
FROM
(
    SELECT
        *,
        multiIf(
            experiment_family = 'local_oos' AND source_model = 'm1_multiscale',
                'M1 Local multiscale vs M0',
            experiment_family = 'local_oos' AND source_model = 'm2_rg_flow',
                'M1R local RG-flow vs M1',
            experiment_family = 'cross_market' AND source_model = 'rg_no_j',
                'M2 Cross-market RG-noJ vs M1',
            experiment_family = 'cross_market' AND source_model = 'rg_with_j',
                'M3 RG-with-J vs M2',
            ''
        ) AS comparison_name,
        multiIf(
            experiment_family = 'local_oos' AND source_model = 'm1_multiscale',
                'm0_single_scale',
            experiment_family = 'local_oos' AND source_model = 'm2_rg_flow',
                'm1_multiscale',
            experiment_family = 'cross_market' AND source_model = 'rg_no_j',
                'm1_local',
            experiment_family = 'cross_market' AND source_model = 'rg_with_j',
                'rg_no_j',
            ''
        ) AS baseline_source_model
    FROM daily
) AS current
INNER JOIN daily AS baseline
    ON current.experiment_id = baseline.experiment_id
   AND current.experiment_stage = baseline.experiment_stage
   AND current.metric_date = baseline.metric_date
   AND current.symbol = baseline.symbol
   AND current.horizon_seconds = baseline.horizon_seconds
   AND current.baseline_source_model = baseline.source_model
WHERE current.comparison_name != ''
ORDER BY current.symbol, current.metric_date, current.comparison_name;
