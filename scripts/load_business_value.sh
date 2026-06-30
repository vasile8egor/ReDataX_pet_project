#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"
INPUT="${INPUT:-${RESULTS_DIR}/coupled_business_value.json}"

docker compose exec -T clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --multiquery \
  < sql/clickhouse/init_business_value.sql

docker compose exec api \
  python -m revolut_app.analytics.load_business_value \
  --replace \
  --input "${INPUT}"
