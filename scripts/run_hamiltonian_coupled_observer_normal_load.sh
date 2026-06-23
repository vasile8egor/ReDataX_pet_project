#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version = 'baseline-v2'
        AND physics_mode = 'none'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

for dataset_id in "${DATASET_IDS[@]}"; do
  echo
  echo "Normal-load observer: ${dataset_id}"

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
      \"model_version\": \"hamiltonian-coupled-observer-v1-normal\",
      \"physics_mode\": \"observer\",
      \"hedging_policy\": \"none\",
      \"hamiltonian_preset\": \"coupled-v1\"
    }"

  echo
  sleep 1
done

echo "Normal-load observer runs completed."
