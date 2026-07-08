# P1: Probability Budget

`P1` acts on events with the highest predicted probability of adverse selection subject to a fixed budget or capacity.

## Inputs

- calibrated probability or monotonic score;
- action budget, such as top `k%`;
- action cost;
- optional inventory constraints.

## Use

This policy is useful when the action capacity is known but economic magnitude is uncertain.

## Limitations

It can over-act on frequent low-severity events if magnitude is not modeled.

