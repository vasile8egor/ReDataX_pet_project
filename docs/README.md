# ReDataX Documentation

This directory is the canonical documentation workspace for the ReDataX research and engineering project.

ReDataX combines synthetic FX inventory simulations with real-market Binance `aggTrades` experiments. The documentation is organized around the full research loop: problem definition, model registry, ML protocol, decision policies, analytics, data contracts, engineering operations, and final reports.

## Map

| Section | Purpose |
|---|---|
| [research](research/00_problem_statement.md) | Research question, theory, experimental design, results, interpretation, and limitations. |
| [models](models/MODEL_REGISTRY.md) | Canonical model definitions from `M0` to economic hurdle policies. |
| [ml](ml/README.md) | Feature engineering, targets, temporal validation, calibration, model selection, and leakage controls. |
| [decision_policies](decision_policies/README.md) | How model scores become quote, hedge, skip, or no-action decisions. |
| [analytics](analytics/README.md) | Metric dictionary, ClickHouse model, Metabase dashboards, and reporting protocol. |
| [data](data/data_sources.md) | Data sources, contracts, lineage, and Binance `aggTrades` ingestion notes. |
| [engineering](engineering/system_architecture.md) | Runtime architecture, experiment runner, deployment, and troubleshooting. |
| [reports](reports/EXECUTIVE_SUMMARY.md) | Executive and final research reports. |

Existing generated artifacts are kept in place, including `docs/results/*` and `docs/analytics/baseline/*`.

## Documentation Principles

- Research claims must be linked to reproducible commands, saved artifacts, or explicit historical status.
- Model names must follow the registry in [models/MODEL_REGISTRY.md](models/MODEL_REGISTRY.md).
- Economic language must distinguish simulated PnL, observed markout exposure, and realized business value.
- Validation must be temporal. Random event-level splits are diagnostic only.
- Any final holdout result must be clearly separated from development, tuning, and exploratory analyses.

## Status Labels

| Label | Meaning |
|---|---|
| Final holdout verified | Fixed model evaluated once on untouched future data. |
| Out-of-time verified | Evaluated on later dates, but the period may have entered development analysis. |
| Artifact verified | Backed by saved JSON, CSV, PDF, or log artifact. |
| Exploratory | Useful for diagnosis, not a production or causal claim. |
| Rejected | Tested and not supported as a stable incremental effect. |
| Historical/local | Known from prior local work; not a current-main headline until reproduced. |

