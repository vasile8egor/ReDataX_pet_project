# ClickHouse data model for research reporting

## Purpose

The reporting layer converts experiment JSON artifacts into normalized
ClickHouse tables. Metabase reads semantic views rather than raw JSON.

## Grain

### `dim_research_experiment_runs`

One row per frozen research version.

### `fact_research_model_selection`

One row per candidate, symbol, stage and horizon. Development keeps the
top-20 leaderboard. Validation stores one preselected policy per horizon.
Final stores the single configuration chosen before the final holdout.

### `fact_research_policy_metrics`

One row per:

```text
experiment × split × symbol × horizon × scope × date × policy
```

`metric_scope = daily` uses the real date. `metric_scope = aggregate` uses
`1970-01-01` as a technical sentinel. Aggregate values are loaded directly
from the experiment artifact and are not recomputed as an average of daily
ratios.

### `fact_research_bootstrap`

One row per paired day-bootstrap comparison.

### `fact_research_prediction_diagnostics`

One row per date and evaluated configuration.

### `fact_research_oracle_horizon`

One row per symbol, horizon and notional budget from the oracle feasibility
scan.

## Model and policy identifiers

| Policy | Model | Component |
|---|---|---|
| P0 No action | NA | none |
| P1 Probability budget | M5 | break-even classifier |
| P2 Direct economic | M4 | direct regression |
| P3 Hurdle economic | M5 | hurdle |
| P4 Oracle | ORACLE | oracle |

P4 is diagnostic and not deployable.

## Semantic views

- `v_research_final_summary`
- `v_research_policy_comparison`
- `v_research_daily_value`
- `v_research_model_selection_path`
- `v_research_intervention_frontier`
- `v_research_oracle_gap`
- `v_research_bootstrap_summary`

## Idempotency

The loader accepts `--replace`. It removes all rows for the selected
`experiment_id` with synchronous ClickHouse mutations and inserts a fresh
snapshot.

## Applying the schema

```bash
bash scripts/apply_research_reporting_schema.sh
```

The SQL file is also copied into ClickHouse `docker-entrypoint-initdb.d` for
new empty volumes. Existing volumes require the explicit apply command.
