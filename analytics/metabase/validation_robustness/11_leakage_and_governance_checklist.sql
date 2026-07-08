SELECT *
FROM
(
    SELECT 1 AS check_order,
           'Chronological split' AS check_name,
           'Train, development, validation and final periods do not overlap'
               AS evidence,
           'Passed' AS status
    UNION ALL
    SELECT 2,
           'Final holdout isolation',
           'The final period is used only after one horizon is selected on validation',
           'Passed'
    UNION ALL
    SELECT 3,
           'Causal feature construction',
           'Features use current and historical observations; future data define targets only',
           'Passed'
    UNION ALL
    SELECT 4,
           'Oracle isolation',
           'Oracle results are diagnostic and never used as deployable predictions',
           'Passed'
    UNION ALL
    SELECT 5,
           'Frozen scenario assumptions',
           'Internalization, mitigation and action cost are fixed before final reporting',
           'Passed'
    UNION ALL
    SELECT 6,
           'No post-final retuning',
           'The research_v1_0 configuration is frozen after the final holdout is viewed',
           'Passed'
    UNION ALL
    SELECT 7,
           'Artifact traceability',
           'Experiment ID, Git commit and source JSON paths are stored in ClickHouse',
           'Passed'
    UNION ALL
    SELECT 8,
           'External validity',
           'Public Binance flow is a market proxy, not proprietary bank client flow',
           'Limitation'
)
ORDER BY check_order;
