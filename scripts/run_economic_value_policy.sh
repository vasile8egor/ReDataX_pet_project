#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"
OUTPUT="${OUTPUT:-${RESULTS_DIR}/economic_value_policy.json}"

docker compose exec api \
  python -m \
  revolut_app.real_market.experiments.economic_value_policy \
  --target-symbols BTCUSDT ETHUSDT \
  --train-start 2025-01-06 \
  --train-end 2025-01-26 \
  --development-start 2025-01-27 \
  --development-end 2025-02-02 \
  --final-test-start 2025-02-03 \
  --final-test-end 2025-02-09 \
  --scenario base:0.50:0.25:0.50 \
  --alphas 0.0001 0.001 \
  --target-clips-bps 5 10 20 \
  --notional-weight-powers 0 0.5 \
  --notional-budget-fractions 0.005 0.01 0.02 0.05 0.10 \
  --minimum-net-margins-bps 0 0.05 0.10 0.20 \
  --minimum-positive-day-fraction 0.7142857143 \
  --risk-penalty 0.50 \
  --bootstrap-samples 5000 \
  --output "${OUTPUT}"
