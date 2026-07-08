# Experimental Design

The design separates synthetic policy simulation from real-market predictive modeling.

## Synthetic Experiments

Synthetic experiments compare pricing and inventory policies on identical generated event streams.

Canonical comparison:

- `naive`
- `inventory_aware`
- `platform`
- Hamiltonian observer variants
- economic value policies where applicable

Primary metrics include net PnL, acceptance rate, average spread, inventory pressure, stress-time, and Hamiltonian regime distribution.

## Real-Market Experiments

Real-market experiments use Binance spot `aggTrades`, reconstruct aggressive side, build causal features, and predict short-horizon adverse-selection outcomes.

Canonical symbols:

- `BTCUSDT`
- `ETHUSDT`
- `ETHBTC`

Canonical horizons:

- `1s`
- `5s`
- longer horizons only when explicitly justified

## Temporal Protocol

Use train, validation, test, and optional final holdout by date. Do not shuffle individual events across time for primary claims.

Recommended split roles:

| Role | Use |
|---|---|
| Train | Fit model parameters. |
| Validation | Select features, thresholds, calibration, and policy parameters. |
| Test | Estimate out-of-time performance after development choices. |
| Final holdout | One-time claim validation after the protocol is frozen. |

