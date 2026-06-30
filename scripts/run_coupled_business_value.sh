#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"
FROZEN_RESULT="${FROZEN_RESULT:-${RESULTS_DIR}/coupled_rg_final.json}"
OUTPUT="${OUTPUT:-${RESULTS_DIR}/coupled_business_value.json}"

docker compose exec api \
  python -m \
  revolut_app.real_market.experiments.coupled_business_value \
  --frozen-result "${FROZEN_RESULT}" \
  --target-symbols BTCUSDT ETHUSDT \
  --capacity-fractions 0.01 0.05 0.10 0.20 \
  --bootstrap-samples 5000 \
  --output "${OUTPUT}"
