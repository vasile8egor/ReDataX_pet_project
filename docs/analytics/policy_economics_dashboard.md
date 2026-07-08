# Policy Economics and Capital Efficiency Dashboard

## Title

ReDataX - Policy Economics and Capital Efficiency

## Purpose

This dashboard explains how predictive scores become economically constrained
actions. It separates gross protected value, action cost, and net value, and
compares absolute value with capital efficiency.

## Apply views

```bash
docker compose exec -T clickhouse   clickhouse-client   --user default   --password default   --multiquery   < sql/clickhouse/init_policy_economics_views.sql
```

## Recommended filters

- experiment_id: default `research_v1_0`
- symbol: optional

## Recommended layout

1. Title, scenario and disclaimer
2. Scenario assumptions
3. Gross-cost-net decomposition
4. Break-even cost headroom
5. Capital usage vs exposure capture
6. Risk concentration
7. Daily hurdle decomposition
8. Policy efficiency table
9. Oracle headroom
10. Bootstrap comparison
11. Policy decision matrix

## Main visualizations

### Gross-cost-net decomposition

Grouped or stacked bar chart:

- X: Policy
- Y: value_per_million_usdt
- Breakout: metric
- Use the symbol filter or market as a breakout

Action cost is returned as a negative number.

### Capital usage vs capture

Scatter chart:

- X: acted_notional_fraction
- Y: capture_rate
- Tooltip: net_value_per_million_usdt, risk_concentration
- Label: Policy

Both axes are fractions. Format as percentages in Metabase.

### Daily hurdle decomposition

Line chart:

- X: Date
- Y: Gross, Action Cost, Net
- Prefer one market at a time
- Show the zero reference line

## Interpretation

- Gross value is scenario-adjusted potential protected exposure, not revenue.
- Net value subtracts the modeled action cost only.
- Benefit/cost above one indicates positive economics under the assumptions.
- Risk concentration above one means exposure capture exceeds the affected
  notional share.
- P4 uses realized future markout and is not deployable.
