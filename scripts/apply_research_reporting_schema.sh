#!/usr/bin/env bash
set -euo pipefail

SQL_FILE="${SQL_FILE:-sql/clickhouse/init_research_reporting.sql}"

docker compose exec -T clickhouse \
  clickhouse-client \
  --user "${CLICKHOUSE_USER:-default}" \
  --password "${CLICKHOUSE_PASSWORD:-default}" \
  --multiquery \
  < "${SQL_FILE}"

echo "Research reporting schema applied."
