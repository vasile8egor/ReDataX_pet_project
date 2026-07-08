# Metabase dashboards

## Dashboard 1: Executive Research Summary

Use the SQL cards in:

```text
analytics/metabase/research/
```

Recommended variables:

| Variable | Type | Default |
|---|---|---|
| `experiment_id` | Text | `research_v1_0` |
| `symbol` | Text | empty / optional |

Recommended layout:

1. Final KPI summary.
2. Net value by policy.
3. Daily net value.
4. Intervention efficiency frontier.
5. Bootstrap comparisons.
6. Model-selection path.
7. Oracle gap.
8. Oracle horizon scan.

Add a Markdown disclaimer:

> Scenario-adjusted potential protected value, not realized bank PnL.
> Results use public Binance aggTrades and explicit assumptions for
> internalization, mitigation efficiency and action cost.
