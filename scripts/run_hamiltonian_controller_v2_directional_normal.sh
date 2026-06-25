#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

MODEL_VERSION="hamiltonian-controller-v2-directional-normal"

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT
          toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version =
          'hamiltonian-controller-v1-normal'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

if [[ "${#DATASET_IDS[@]}" -eq 0 ]]; then
  echo "No controller-v1 datasets found."
  exit 1
fi

echo "Found ${#DATASET_IDS[@]} immutable datasets."

for dataset_id in "${DATASET_IDS[@]}"; do
  echo
  echo "Directional controller-v2 replay: ${dataset_id}"

  curl --fail-with-body \
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
      \"model_version\": \"${MODEL_VERSION}\",
      \"physics_mode\": \"controller\",
      \"hamiltonian_preset\": \"local-v1\",
      \"controller_preset\": \"directional-v2\",
      \"hedging_policy\": \"none\"
    }"

  echo
  sleep 1
done

echo
echo "Directional Hamiltonian controller-v2 runs completed."
