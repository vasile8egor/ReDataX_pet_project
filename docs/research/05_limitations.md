# Limitations

## Research Limitations

- Binance spot `aggTrades` are public crypto-market data and are not a direct proxy for retail FX execution.
- Aggressor side is inferred from exchange fields and should be validated when ingestion logic changes.
- Markout is a proxy for adverse selection, not complete market-maker PnL.
- Temporal regimes can change, so older validation periods do not guarantee future performance.
- Model results are sensitive to fees, spread assumptions, threshold choice, and liquidity constraints.

## Engineering Limitations

- Some historical artifacts may not be reproducible from current `main` without migration.
- Local experiments and saved Metabase exports should not be treated as production monitoring.
- Long-running backfills can be sensitive to ClickHouse availability and disk capacity.

## Claim Discipline

Use the weakest accurate label: exploratory, artifact verified, out-of-time verified, or final holdout verified.

