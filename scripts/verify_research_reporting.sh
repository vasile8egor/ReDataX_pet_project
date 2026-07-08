#!/usr/bin/env bash
set -euo pipefail

EXPERIMENT_ID="${EXPERIMENT_ID:-research_v1_0}"

docker compose exec clickhouse \
  clickhouse-client \
  --user "${CLICKHOUSE_USER:-default}" \
  --password "${CLICKHOUSE_PASSWORD:-default}" \
  --query "
SELECT 'runs' AS dataset, count() AS rows
FROM gold.dim_research_experiment_runs FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
UNION ALL
SELECT 'model_selection', count()
FROM gold.fact_research_model_selection FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
UNION ALL
SELECT 'policy_metrics', count()
FROM gold.fact_research_policy_metrics FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
UNION ALL
SELECT 'bootstrap', count()
FROM gold.fact_research_bootstrap FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
UNION ALL
SELECT 'diagnostics', count()
FROM gold.fact_research_prediction_diagnostics FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
UNION ALL
SELECT 'oracle', count()
FROM gold.fact_research_oracle_horizon FINAL
WHERE experiment_id = '${EXPERIMENT_ID}'
ORDER BY dataset
"

docker compose exec clickhouse \
  clickhouse-client \
  --user "${CLICKHOUSE_USER:-default}" \
  --password "${CLICKHOUSE_PASSWORD:-default}" \
  --query "
SELECT *
FROM gold.v_research_final_summary
WHERE experiment_id = '${EXPERIMENT_ID}'
ORDER BY symbol
FORMAT PrettyCompact
"
