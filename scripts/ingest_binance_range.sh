#!/usr/bin/env bash

set -euo pipefail

start_date="${1:-2025-01-07}"
end_date="${2:-2025-01-26}"

if [ "$#" -gt 2 ]; then
  symbols=("${@:3}")
else
  symbols=(BTCUSDT ETHUSDT)
fi

data_directory="/opt/airflow/data/real_market/binance"
day_attempts="${BINANCE_INGEST_DAY_ATTEMPTS:-6}"
day_retry_sleep_seconds="${BINANCE_INGEST_DAY_RETRY_SLEEP_SECONDS:-60}"

run_day() {
  local trade_date="$1"

  docker compose exec api \
    python -m \
    revolut_app.real_market.binance.smoke_cli \
    --date "${trade_date}" \
    --symbols "${symbols[@]}" \
    --data-directory "${data_directory}" \
    || return $?

  docker compose exec api \
    python -m \
    revolut_app.real_market.binance.ingest_cli \
    --date "${trade_date}" \
    --symbols "${symbols[@]}" \
    --data-directory "${data_directory}" \
    --batch-size 50000 \
    || return $?
}

for trade_date in $(
  python - "$start_date" "$end_date" <<'PY'
from datetime import date, timedelta
import sys

start = date.fromisoformat(sys.argv[1])
end = date.fromisoformat(sys.argv[2])

if end < start:
    raise SystemExit("end date must be greater than or equal to start date")

current = start

while current <= end:
    print(current.isoformat())
    current += timedelta(days=1)
PY
); do
  echo "Processing ${trade_date}"

  for attempt in $(seq 1 "${day_attempts}"); do
    if run_day "${trade_date}"; then
      break
    fi

    if [ "${attempt}" -eq "${day_attempts}" ]; then
      echo "Failed ${trade_date} after ${day_attempts} attempts" >&2
      exit 1
    fi

    echo "Retrying ${trade_date} in ${day_retry_sleep_seconds}s (attempt ${attempt}/${day_attempts})" >&2
    sleep "${day_retry_sleep_seconds}"
  done
done
