#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
SOURCE_MODEL_VERSION="${SOURCE_MODEL_VERSION:-baseline-v2}"
BASELINE_MODEL_VERSION="${BASELINE_MODEL_VERSION:-baseline-current-v1}"
OBSERVER_MODEL_VERSION="${OBSERVER_MODEL_VERSION:-observer-current-v1}"

existing_runs="$({
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT count()
      FROM gold.fact_simulation_runs
      WHERE model_version IN (
        '${BASELINE_MODEL_VERSION}',
        '${OBSERVER_MODEL_VERSION}'
      )
      FORMAT TSVRaw
    "
})"

if [[ "${existing_runs}" -ne 0 ]]; then
  echo "Current comparison versions already contain ${existing_runs} runs." >&2
  echo "Choose new BASELINE_MODEL_VERSION and OBSERVER_MODEL_VERSION values." >&2
  exit 1
fi

mapfile -t DATASET_IDS < <(
  docker exec clickhouse clickhouse-client \
    --user default \
    --password default \
    --query "
      SELECT DISTINCT toString(event_dataset_id)
      FROM gold.fact_simulation_runs
      WHERE model_version = '${SOURCE_MODEL_VERSION}'
        AND physics_mode = 'none'
      ORDER BY event_dataset_id
      FORMAT TSVRaw
    "
)

if [[ "${#DATASET_IDS[@]}" -eq 0 ]]; then
  echo "No source datasets found for ${SOURCE_MODEL_VERSION}." >&2
  exit 1
fi

run_replay() {
  local dataset_id="$1"
  local model_version="$2"
  local physics_mode="$3"

  curl --fail-with-body --silent --show-error \
    --request POST \
    "${API_URL}/fx/policy-comparison" \
    --header 'Content-Type: application/json' \
    --data "{
      \"event_dataset_id\": \"${dataset_id}\",
      \"policies\": [\"naive\", \"inventory_aware\", \"platform\"],
      \"amount_multiplier\": 500,
      \"snapshot_every_n_events\": 20,
      \"persist_result\": true,
      \"model_version\": \"${model_version}\",
      \"physics_mode\": \"${physics_mode}\",
      \"hedging_policy\": \"none\"
    }" >/dev/null
}

for dataset_id in "${DATASET_IDS[@]}"; do
  echo "Paired replay: ${dataset_id}"
  run_replay "${dataset_id}" "${BASELINE_MODEL_VERSION}" 'none'
  run_replay "${dataset_id}" "${OBSERVER_MODEL_VERSION}" 'observer'
done

docker exec clickhouse clickhouse-client \
  --user default \
  --password default \
  --query "
    WITH
      baseline AS (
        SELECT *
        FROM gold.fact_simulation_runs
        WHERE model_version = '${BASELINE_MODEL_VERSION}'
          AND physics_mode = 'none'
      ),
      observer AS (
        SELECT *
        FROM gold.fact_simulation_runs
        WHERE model_version = '${OBSERVER_MODEL_VERSION}'
          AND physics_mode = 'observer'
      )
    SELECT
      count() AS compared_runs,
      countIf(baseline.generated_requests != event_counts.raw_events)
        AS incomplete_baseline_replays,
      countIf(observer.generated_requests != event_counts.raw_events)
        AS incomplete_observer_replays,
      countIf(baseline.accepted_events != observer.accepted_events)
        AS accepted_mismatches,
      countIf(baseline.rejected_events != observer.rejected_events)
        AS rejected_mismatches,
      countIf(abs(baseline.net_pnl_usd - observer.net_pnl_usd) > 0.000001)
        AS pnl_mismatches,
      countIf(abs(baseline.funding_cost_usd - observer.funding_cost_usd) > 0.000001)
        AS funding_mismatches,
      countIf(abs(baseline.stress_time_fraction - observer.stress_time_fraction) > 0.000001)
        AS stress_mismatches,
      countIf(abs(baseline.max_abs_pressure - observer.max_abs_pressure) > 0.000001)
        AS pressure_mismatches
    FROM baseline
    INNER JOIN observer USING (event_dataset_id, pricing_policy)
    INNER JOIN (
      SELECT event_dataset_id, count() AS raw_events
      FROM gold.fact_fx_events
      GROUP BY event_dataset_id
    ) AS event_counts USING (event_dataset_id)
    FORMAT PrettyCompact
  "
