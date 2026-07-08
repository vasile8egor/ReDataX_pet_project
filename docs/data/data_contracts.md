# Data Contracts

Data contracts define stable fields expected by downstream experiments.

## Market Event Contract

Required fields:

- symbol;
- exchange timestamp;
- aggregate trade ID;
- price;
- quantity;
- inferred aggressor side;
- event date;
- ingestion metadata.

## Experiment Output Contract

Required fields:

- run ID;
- model ID;
- policy ID when applicable;
- symbol;
- horizon;
- split role;
- score or prediction;
- target;
- realized markout or value proxy;
- timestamp.

