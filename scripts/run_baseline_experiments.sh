#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

SEEDS=(
	11
	22
	33
	44
	55
	66
	77
	88
	99
	110
)

mkdir -p artifacts/baseline_responses

for seed in "${SEEDS[@]}"; do
  echo
  echo "========================================"
  echo "Running baseline experiment: seed=${seed}"
  echo "========================================"

  curl --fail-with-body \
    --request POST \
    "${API_URL}/fx/policy-comparison" \
    --header "Content-Type: application/json" \
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
      \"amount_multiplier\": 500,
      \"snapshot_every_n_events\": 20,
      \"persist_result\": true,
      \"model_version\": \"baseline-v2\",
      \"physics_mode\": \"none\",
      \"hedging_policy\": \"none\"
    }" \
    | tee "artifacts/baseline_responses/seed_${seed}.json"

  echo
  sleep 1
done

echo
echo "All baseline experiments completed."
