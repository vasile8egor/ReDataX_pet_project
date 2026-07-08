# M4: Direct Value Regression

`M4` predicts economic magnitude directly rather than only adverse-selection probability.

## Target

Examples:

- positive markout in basis points;
- dollar adverse-selection exposure;
- cost-adjusted value at a candidate action.

## Purpose

Use when policy quality depends more on magnitude than binary direction.

## Required Metrics

- MAE or robust regression loss;
- ranking quality by value bucket;
- calibration of expected value;
- policy simulation at fixed capacity or budget.

## Caution

Magnitude targets are heavy-tailed. Use winsorization, robust losses, or bucketed reporting when needed.

