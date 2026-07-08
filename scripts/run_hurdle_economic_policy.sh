#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"
OUTPUT="${OUTPUT:-${RESULTS_DIR}/hurdle_economic_policy.json}"

docker compose exec api \
  python -m \
  revolut_app.real_market.experiments.hurdle_economic_policy \
  --target-symbols BTCUSDT ETHUSDT \
  --horizons-seconds 120 300 600 \
  --decision-stride-seconds 10 \
  --train-start 2025-01-06 \
  --train-end 2025-01-26 \
  --development-start 2025-01-27 \
  --development-end 2025-02-02 \
  --validation-start 2025-02-03 \
  --validation-end 2025-02-09 \
  --final-test-start 2025-02-10 \
  --final-test-end 2025-02-16 \
  --scenario base:0.50:0.25:0.50 \
  --model-presets compact medium \
  --notional-budget-fractions 0.01 0.02 0.05 0.10 \
  --minimum-net-margins-bps 0 0.05 0.10 \
  --minimum-break-even-probabilities 0 0.40 0.50 0.60 \
  --prediction-multipliers 1.0 1.25 1.50 \
  --risk-penalty 0.50 \
  --minimum-positive-day-fraction 0.7142857143 \
  --bootstrap-samples 5000 \
  --output "${OUTPUT}"
