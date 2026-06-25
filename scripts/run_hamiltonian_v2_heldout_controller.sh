#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

OBSERVER_MODEL_VERSION="hamiltonian-observer-v1-heldout"
CONTROLLER_MODEL_VERSION="hamiltonian-controller-v2-g18-c6-heldout"

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT
          toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version =
          '${OBSERVER_MODEL_VERSION}'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

if [[ "${#DATASET_IDS[@]}" -ne 10 ]]; then
  echo "Expected 10 held-out datasets."
  echo "Found ${#DATASET_IDS[@]}."
  exit 1
fi

total="${#DATASET_IDS[@]}"
current=0

for dataset_id in "${DATASET_IDS[@]}"; do
  current=$((current + 1))

  existing_runs=$(
    docker exec clickhouse clickhouse-client \
      --user default \
      --password default \
      --query "
        SELECT uniqExact(run_id)
        FROM gold.fact_simulation_runs
        WHERE model_version =
            '${CONTROLLER_MODEL_VERSION}'
          AND event_dataset_id =
            '${dataset_id}'
      "
  )

  if [[ "${existing_runs}" -eq 3 ]]; then
    echo "[$current/$total] Already completed: ${dataset_id}"
    continue
  fi

  if [[ "${existing_runs}" -ne 0 ]]; then
    echo "Partial result detected:"
    echo "dataset=${dataset_id}"
    echo "runs=${existing_runs}"
    echo "Refusing to create ambiguous duplicates."
    exit 1
  fi

  echo
  echo "[$current/$total] Controller replay: ${dataset_id}"

  curl --fail-with-body \
    --silent \
    --show-error \
    --output /dev/null \
    --write-out \
      "http=%{http_code} total=%{time_total}s\n" \
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
      \"model_version\": \"${CONTROLLER_MODEL_VERSION}\",
      \"physics_mode\": \"controller\",
      \"hamiltonian_preset\": \"local-v1\",
      \"controller_preset\": \"directional-v2\",
      \"directional_controller_parameters\": {
        \"spread_gain_bps_per_delta_energy\": 18,
        \"max_adjustment_bps\": 6,
        \"delta_h_epsilon\": 0.000001
      },
      \"hedging_policy\": \"none\"
    }"
done

echo
echo "Held-out controller replay completed."
