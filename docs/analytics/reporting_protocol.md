# Research reporting protocol

1. Freeze the experiment JSON artifacts and Git commit.
2. Apply the ClickHouse reporting schema.
3. Load both hurdle and oracle artifacts under one `experiment_id`.
4. Verify row counts and the final summary view.
5. Build Metabase cards only from semantic views.
6. Export the dashboard and preserve it with the JSON artifacts.
7. Never retune model parameters after viewing the final holdout.

## Commands

```bash
bash scripts/apply_research_reporting_schema.sh
bash scripts/load_research_reporting.sh
bash scripts/verify_research_reporting.sh
```

Default artifact paths inside the API container:

```text
/opt/airflow/data/real_market/results/hurdle_economic_policy.json
/opt/airflow/data/real_market/results/oracle_horizon_scan.json
```

Default experiment identifier:

```text
research_v1_0
```
