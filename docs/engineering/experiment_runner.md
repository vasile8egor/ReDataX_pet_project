# Experiment Runner

Experiment runners should make research commands reproducible.

## Runner Responsibilities

- parse dates, symbols, horizons, and model IDs;
- build or load features;
- fit models only on permitted splits;
- write metrics and predictions;
- save metadata;
- return non-zero status on partial failure.

## Script Convention

Shell scripts in `scripts/` should be thin wrappers around Python modules. Python modules should own validation, logging, and artifact generation.

## Artifact Convention

Use run IDs that include model family, date range, and timestamp when practical.

