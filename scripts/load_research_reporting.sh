#!/usr/bin/env bash
set -euo pipefail

HURDLE_INPUT="${HURDLE_INPUT:-/opt/airflow/data/real_market/results/hurdle_economic_policy.json}"
ORACLE_INPUT="${ORACLE_INPUT:-/opt/airflow/data/real_market/results/oracle_horizon_scan.json}"
EXPERIMENT_ID="${EXPERIMENT_ID:-research_v1_0}"
RESEARCH_VERSION="${RESEARCH_VERSION:-1.0}"

docker compose exec api \
  python -m revolut_app.analytics.load_research_reporting \
  --hurdle-input "${HURDLE_INPUT}" \
  --oracle-input "${ORACLE_INPUT}" \
  --experiment-id "${EXPERIMENT_ID}" \
  --research-version "${RESEARCH_VERSION}" \
  --replace
