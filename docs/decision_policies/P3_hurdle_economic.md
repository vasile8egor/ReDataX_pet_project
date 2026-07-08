# P3: Hurdle Economic

`P3` combines event probability and conditional value.

## Decision Rule

```text
expected_value = p_event * conditional_value - action_cost
act if expected_value > threshold
```

## Inputs

- `M5` event probability;
- `M5` conditional value;
- cost model;
- threshold or budget.

## Use

This policy is preferred when event frequency and loss magnitude behave differently.

