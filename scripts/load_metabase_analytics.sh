#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"

docker compose exec -T clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --multiquery \
  < sql/clickhouse/init_analytics_metrics.sql

docker compose exec api \
  python -m revolut_app.analytics.load_model_artifacts \
  --replace \
  --oos "${RESULTS_DIR}/oos_rg_proof.json" \
  --capture "${RESULTS_DIR}/adverse_selection_capture.json" \
  --coupled "${RESULTS_DIR}/coupled_rg_final.json"
