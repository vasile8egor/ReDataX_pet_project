SELECT *
FROM
(
    SELECT 1 AS hypothesis_order,
           'Temporal multiscale features improve the local baseline' AS hypothesis,
           'M1 vs M0: positive paired AP uplift on the 5-second OOS test' AS evidence,
           'Accepted' AS decision
    UNION ALL
    SELECT 2,
           'The local RG-flow diagnostic adds value beyond multiscale features',
           'M1R vs M1: near-zero and unstable incremental AP',
           'Rejected'
    UNION ALL
    SELECT 3,
           'Cross-market multiscale state improves the local model',
           'M2 vs M1: positive AP uplift with 7/7 positive days',
           'Accepted'
    UNION ALL
    SELECT 4,
           'Explicit pairwise J terms improve the cross-market state',
           'M3 vs M2: incremental AP is small and unstable',
           'Rejected'
    UNION ALL
    SELECT 5,
           'A 5-second economic policy covers the assumed action cost',
           'The direct value model selected no robust profitable actions',
           'Rejected / reformulated'
    UNION ALL
    SELECT 6,
           'Longer markout horizons contain sufficient economic headroom',
           'Oracle scan is positive on 120-600 second horizons',
           'Accepted'
    UNION ALL
    SELECT 7,
           'Probability and severity separation supports positive final value',
           'M5 + P3 is positive on the independent final holdout',
           'Accepted'
)
ORDER BY hypothesis_order;
