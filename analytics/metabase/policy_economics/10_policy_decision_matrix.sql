SELECT *
FROM
(
    SELECT 1 AS decision_order,
           'P1 Probability budget' AS policy,
           'Maximize ranking quality under a fixed notional budget' AS objective,
           'Strong absolute value; best point estimate on ETH' AS observed_result,
           'Strong baseline' AS role
    UNION ALL
    SELECT 2,
           'P2 Direct economic',
           'Maximize expected positive markout per unit of intervention',
           'Lower absolute value, but highest capital efficiency and B/C',
           'Capital-efficient baseline'
    UNION ALL
    SELECT 3,
           'P3 Hurdle economic',
           'Separate probability and severity, then apply an economic gate',
           'Positive final value on both markets; highest deployable value on BTC',
           'Selected final policy'
    UNION ALL
    SELECT 4,
           'P4 Oracle upper bound',
           'Estimate the maximum attainable value with future information',
           'Large remaining predictive and policy headroom',
           'Diagnostic only'
)
ORDER BY decision_order;
