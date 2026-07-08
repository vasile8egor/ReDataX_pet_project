# Theoretical Framework

The framework uses market microstructure concepts and RG-inspired multiscale notation as organizing tools. The physics vocabulary is phenomenological: coefficients are predictive parameters, not equilibrium constants.

## Signed Flow

For market `i` and time bucket `B`, the normalized flow field is:

```text
phi_i^B(t) = (V_buy_i,B(t) - V_sell_i,B(t)) / (V_buy_i,B(t) + V_sell_i,B(t) + epsilon)
```

`phi` lies near `[-1, 1]` and summarizes directional pressure.

## Coarse-Graining

The canonical scale set is:

```text
B = {1, 2, 4, 8, 16, 32, 64} seconds
```

Single-scale models use one bucket. Multiscale models use a vector across buckets. Cross-market models add synchronized fields from BTCUSDT, ETHUSDT, and ETHBTC.

## Adverse Selection

For horizon `H`, a positive markout means that price moved in the aggressor direction:

```text
markout_t,H = aggressor_sign_t * (future_price_t+H - price_t) / price_t * 10000
```

The binary target is usually `markout_t,H > 0`. Economic targets use the positive markout magnitude and notional.

## Inventory and Hamiltonian Observer

Synthetic FX experiments use an observer that maps inventory pressure, flow imbalance, and stress components into a diagnostic Hamiltonian score. The observer can be execution-neutral or used as part of a controller, but those roles must be documented separately.

