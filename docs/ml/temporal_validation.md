# Temporal Validation

Primary validation must preserve time order.

## Recommended Layout

| Split | Purpose |
|---|---|
| Train | Fit parameters. |
| Validation | Tune features, thresholds, and calibration. |
| Test | Estimate out-of-time performance. |
| Final holdout | One-time validation after protocol freeze. |

## Day-Level Reporting

Aggregate metrics should be accompanied by daily metrics. Paired day-level comparisons are preferred because crypto market regimes vary strongly by date.

## Prohibited for Claims

Random event-level splits are allowed for smoke tests only. They cannot support final research claims because neighboring events leak regime context.

