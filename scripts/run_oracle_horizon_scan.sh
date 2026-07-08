#!/usr/bin/env bash
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/opt/airflow/data/real_market/results}"
OUTPUT_JSON="${OUTPUT_JSON:-${RESULTS_DIR}/oracle_horizon_scan.json}"
OUTPUT_CSV="${OUTPUT_CSV:-${RESULTS_DIR}/oracle_horizon_scan.csv}"

docker compose exec api \
  python -m \
  revolut_app.real_market.experiments.oracle_horizon_scan \
  --target-symbols BTCUSDT ETHUSDT \
  --scan-start 2025-01-27 \
  --scan-end 2025-02-02 \
  --horizons-seconds \
    5 10 15 30 60 120 300 600 1800 3600 7200 \
  --notional-budget-fractions \
    0.005 0.01 0.02 0.05 0.10 \
  --scenario base:0.50:0.25:0.50 \
  --risk-penalty 0.50 \
  --minimum-positive-day-fraction 0.7142857143 \
  --bootstrap-samples 5000 \
  --output-json "${OUTPUT_JSON}" \
  --output-csv "${OUTPUT_CSV}"
