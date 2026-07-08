# P0: No Action

`P0` is the baseline policy. It does not alter quotes, hedge, reject flow, or otherwise intervene based on the model.

## Purpose

- Establish default economic outcome.
- Separate model signal from policy value.
- Provide a sanity check for simulations.

## Reporting

All active policies should report uplift or loss relative to `P0`.

