#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
API_WAIT_SECONDS="${API_WAIT_SECONDS:-90}"

GAINS=(12 18 24)
CAPS=(4 6 8)

wait_for_api() {
  local deadline
  deadline=$((SECONDS + API_WAIT_SECONDS))

  echo "Waiting for API at ${API_URL}/health..."

  until curl \
      --fail \
      --silent \
      --show-error \
      --output /dev/null \
      "${API_URL}/health"; do
    if (( SECONDS >= deadline )); then
      echo "API did not become ready within ${API_WAIT_SECONDS}s."
      exit 1
    fi

    sleep 2
  done

  echo "API is ready."
}

wait_for_api

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT
          toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version =
          'hamiltonian-controller-v2-directional-normal'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

if [[ "${#DATASET_IDS[@]}" -ne 10 ]]; then
  echo "Expected 10 datasets, found ${#DATASET_IDS[@]}."
  exit 1
fi

for gain in "${GAINS[@]}"; do
  for cap in "${CAPS[@]}"; do
    model_version="hamiltonian-controller-v2-g${gain}-c${cap}-sensitivity"

    echo
    echo "Configuration: gain=${gain}, cap=${cap}"
    echo "Model version: ${model_version}"

    for dataset_id in "${DATASET_IDS[@]}"; do
      echo "Dataset: ${dataset_id}"

      started_at=$(date +%s)

      if ! http_stats=$(
        curl --fail-with-body \
          --silent \
          --show-error \
          --output /dev/null \
          --write-out \
            'http=%{http_code} total=%{time_total}s connect=%{time_connect}s starttransfer=%{time_starttransfer}s' \
          --request POST \
          "${API_URL}/fx/policy-comparison" \
          --header "Content-Type: application/json" \
          --data "{
            \"event_dataset_id\": \"${dataset_id}\",
            \"policies\": [
              \"naive\",
              \"inventory_aware\",
              \"platform\"
            ],
            \"amount_multiplier\": 150,
            \"snapshot_every_n_events\": 20,
            \"persist_result\": true,
            \"model_version\": \"${model_version}\",
            \"physics_mode\": \"controller\",
            \"hamiltonian_preset\": \"local-v1\",
            \"controller_preset\": \"directional-v2\",
            \"directional_controller_parameters\": {
              \"spread_gain_bps_per_delta_energy\": ${gain},
              \"max_adjustment_bps\": ${cap},
              \"delta_h_epsilon\": 0.000001
            },
            \"hedging_policy\": \"none\"
          }"
      ); then
        echo "Request failed for dataset=${dataset_id}, gain=${gain}, cap=${cap}."
        exit 1
      fi

      finished_at=$(date +%s)

      echo "Completed in $((finished_at - started_at))s: ${http_stats}"

      sleep 1
    done
  done
done

echo
echo "Directional-v2 sensitivity replay completed."
