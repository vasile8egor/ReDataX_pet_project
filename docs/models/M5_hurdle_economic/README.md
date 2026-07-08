# M5: Hurdle Economic

`M5` separates event probability from conditional economic magnitude.

## Definition

The model has two stages:

1. probability of positive adverse-selection event;
2. conditional value given that the event occurs.

Expected value is:

```text
EV = P(event) * E(value | event) - action_cost
```

## Purpose

This structure is useful when adverse-selection events are common enough to classify but economic losses are concentrated in the tail.

## Reporting

Report probability quality, conditional-value quality, and final policy value separately.

## Policy Link

The natural decision companion is [P3 hurdle economic](../../decision_policies/P3_hurdle_economic.md).

