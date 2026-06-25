#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

MODEL_VERSION="hamiltonian-observer-v1-heldout"

SEEDS=(
  1001
  1002
  1003
  1004
  1005
  1006
  1007
  1008
  1009
  1010
)

mkdir -p artifacts/heldout_observer_responses

existing_datasets=$(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT uniqExact(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version = '${MODEL_VERSION}'
    "
)

if [[ "${existing_datasets}" -ne 0 ]]; then
  echo "Held-out observer data already exists:"
  echo "datasets=${existing_datasets}"
  echo "Refusing to generate duplicate held-out datasets."
  exit 1
fi

total="${#SEEDS[@]}"
current=0

for seed in "${SEEDS[@]}"; do
  current=$((current + 1))

  echo
  echo "[$current/$total] Generating held-out dataset: seed=${seed}"

  curl --fail-with-body \
    --silent \
    --show-error \
    --request POST \
    "${API_URL}/fx/policy-comparison" \
    --header "Content-Type: application/json" \
    --output \
      "artifacts/heldout_observer_responses/seed_${seed}.json" \
    --write-out \
      "http=%{http_code} total=%{time_total}s\n" \
    --data "{
      \"policies\": [
        \"naive\",
        \"inventory_aware\",
        \"platform\"
      ],
      \"steps\": 5000,
      \"dt_seconds\": 10,
      \"base_intensity\": 0.03,
      \"alpha\": 0.08,
      \"beta\": 0.12,
      \"seed\": ${seed},
      \"amount_multiplier\": 150,
      \"snapshot_every_n_events\": 20,
      \"persist_result\": true,
      \"model_version\": \"${MODEL_VERSION}\",
      \"physics_mode\": \"observer\",
      \"hamiltonian_preset\": \"local-v1\",
      \"hedging_policy\": \"none\"
    }"
done

echo
echo "Held-out observer datasets completed."
