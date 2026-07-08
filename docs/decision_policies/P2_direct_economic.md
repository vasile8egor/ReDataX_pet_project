# P2: Direct Economic

`P2` acts when a direct expected-value model predicts value above cost.

## Decision Rule

```text
act if predicted_value - action_cost > threshold
```

## Inputs

- `M4` value prediction;
- action cost;
- minimum margin of safety;
- optional inventory or risk limits.

## Reporting

Report total value, value per action, action rate, and sensitivity to cost assumptions.

