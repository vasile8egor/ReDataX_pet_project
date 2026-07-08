# Troubleshooting

## Ingestion

- Check source archive availability for the requested dates.
- Verify disk space before large Binance downloads.
- Confirm duplicates are handled before re-running a range.

## ClickHouse

- Confirm service health and credentials.
- Check table partitions for expected dates.
- Verify run IDs when dashboard numbers look stale.

## Experiments

- Confirm split dates do not overlap.
- Run a one-day smoke test before a long range.
- Inspect per-day metrics before trusting aggregate metrics.

## Dashboards

- Refresh dashboard filters.
- Confirm Metabase is pointed at the expected ClickHouse database.
- Treat screenshots as snapshots, not live truth.

