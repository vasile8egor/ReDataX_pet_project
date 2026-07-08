# Targets

Targets define what the model is allowed to learn.

## Binary Adverse Selection

```text
y_t,H = 1 if markout_t,H > 0 else 0
```

Use for `M0`, `M1`, `M2`, and `M3` classification experiments.

## Economic Value

```text
positive_markout_bps = max(markout_t,H, 0)
dollar_exposure = notional_t * positive_markout_bps / 10000
```

Use for `M4` and `M5`.

## Horizon Discipline

Horizon must be fixed before model selection for a claim. Common horizons are `1s` and `5s`.

