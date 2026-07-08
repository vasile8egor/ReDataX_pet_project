# Validation, Robustness and Reproducibility Dashboard

## Dashboard title

ReDataX - Validation, Robustness and Reproducibility

## Purpose

The dashboard documents:

- chronological temporal splits;
- development and validation selection;
- one-time final holdout evaluation;
- day-level robustness;
- paired bootstrap uncertainty;
- validation-to-final consistency;
- prediction diagnostics;
- reproducibility metadata;
- leakage and governance controls.

## Apply semantic views

```bash
docker compose exec -T clickhouse   clickhouse-client   --user default   --password default   --multiquery   < sql/clickhouse/init_validation_robustness_views.sql
```

## Recommended filters

- experiment_id: default `research_v1_0`
- symbol: optional

## Recommended layout

1. Title and methodological note
2. Temporal split protocol
3. Reproducibility manifest
4. Selection funnel
5. Validation versus final consistency
6. Daily validation/final value
7. Cumulative final value index
8. Daily robustness summary
9. Bootstrap robustness
10. Prediction diagnostics
11. Oracle horizon robustness
12. Leakage and governance checklist

## Critical interpretation rules

- Validation and final statistics each use seven daily clusters.
- Bootstrap confidence intervals describe variation across days, not
  independent event-level uncertainty.
- Compare validation daily means with final daily means. Do not compare a
  pooled aggregate ratio with an equal-weighted daily mean.
- The cumulative final chart is an index of daily normalized values, not
  cumulative realized bank profit.
- Final holdout data must not be used for further tuning.
- Oracle outputs are diagnostic only.

## Selection-funnel storage note

For development, the reporting artifact stores only the top-20 leaderboard,
not every grid-search combination. Therefore the dashboard reports
`Leaderboard Rows Stored`, not the total number of candidates evaluated by
the experiment. Validation rows represent the horizon-level candidates that
were actually carried forward.
