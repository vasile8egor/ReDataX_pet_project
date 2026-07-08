# Binance AggTrades

Binance `aggTrades` archives provide public aggregate trade events.

## Ingestion

The project includes scripts and code for range ingestion and downloader smoke checks. Downloaded data should be validated before use in modeling.

## Important Fields

- aggregate trade ID;
- price;
- quantity;
- first and last trade IDs;
- trade timestamp;
- buyer maker flag.

## Aggressor Side

The buyer maker flag is used to infer whether the aggressive side was buy or sell. This inference is central to signed-flow features and must be covered by smoke tests.

## Known Risks

- missing archive days;
- duplicate rows from repeated loads;
- timestamp alignment across symbols;
- schema changes in source archives.

