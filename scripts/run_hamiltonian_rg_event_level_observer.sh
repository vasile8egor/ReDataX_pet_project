#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

SOURCE_MODEL_VERSION="hamiltonian-observer-v1-heldout"
RG_MODEL_VERSION="hamiltonian-observer-v1-rg-event-level"

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT
          toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version =
          '${SOURCE_MODEL_VERSION}'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

if [[ "${#DATASET_IDS[@]}" -ne 10 ]]; then
  echo "Expected 10 datasets."
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
            '${RG_MODEL_VERSION}'
          AND event_dataset_id =
            '${dataset_id}'
      "
  )

  if [[ "${existing_runs}" -eq 3 ]]; then
    echo "[$current/$total] Already completed: ${dataset_id}"
    continue
  fi

  if [[ "${existing_runs}" -ne 0 ]]; then
    echo "Partial run detected:"
    echo "dataset=${dataset_id}"
    echo "runs=${existing_runs}"
    exit 1
  fi

  echo
  echo "[$current/$total] Event-level replay: ${dataset_id}"

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
      \"snapshot_every_n_events\": 1,
      \"persist_result\": true,
      \"model_version\": \"${RG_MODEL_VERSION}\",
      \"physics_mode\": \"observer\",
      \"hamiltonian_preset\": \"local-v1\",
      \"hedging_policy\": \"none\"
    }"
done

echo
echo "RG event-level observer replay completed."
