# ReDataX M1 - Local Multiscale Order-Flow Model

M1 is the first accepted extension of the single-scale M0 baseline. It predicts whether the future aggressor-aligned markout will be positive using the recent order-flow state of one market observed over several nested time scales.

> M1 is a research classifier. It does not predict medium-term price direction, reconstruct a market maker's private inventory, or estimate realized trading PnL.

## Model card

| Field | Value |
|---|---|
| Model ID | `M1` |
| Experiment name | `m1_local` |
| Family | Regularized binary classification |
| Status | Accepted |
| Predecessor | `M0` single-scale local baseline |
| Primary target | Positive aggressor-aligned future markout |
| Target markets | `BTCUSDT`, `ETHUSDT` |
| Input markets | Target market only |
| Time scales | `1, 2, 4, 8, 16, 32, 64` seconds |
| Feature count | 29 |
| Final cross-market experiment horizon | 5 seconds |
| Main implementation | [`coupled_rg_final.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/coupled_rg_final.py) |

## Research question

Does a multiscale description of the target market's signed flow contain more short-horizon information than one fixed aggregation scale?

M1 is compared with M0 while keeping the target, classifier family, observations, temporal splits, and metrics unchanged. The intended ablation is therefore:

```text
M0: one local scale
M1: seven local scales
```

The acceptance criterion is a positive out-of-time improvement in daily Average Precision.

## Data

The model uses public Binance Spot aggregate trades (`aggTrades`). Each event provides price, quantity, event time, and the buyer-maker flag. ReDataX converts the flag into the aggressive side and aggregates trades to completed UTC seconds.

For target market (A), define aggressive buy and sell quote volumes in second (t) as (V_A^+(t)) and (V_A^-(t)). The normalized signed-flow field is

$$
\phi_A(t)=
\begin{cases}
\dfrac{V_A^+(t)-V_A^-(t)}{V_A^+(t)+V_A^-(t)}, & V_A^+(t)+V_A^-(t)>0,\\
0, & \text{otherwise}.
\end{cases}
$$

Inactive seconds remain in the calendar-time grid and contribute zero flow.

## Multiscale representation

For each scale (B\in\{1,2,4,8,16,32,64\}), ReDataX computes the trailing average

$$
\bar\phi_A^{(B)}(t)=\frac{1}{B}\sum_{u=0}^{B-1}\phi_A(t-u).
$$

Let (d_A(t)=\operatorname{sign}\phi_A(t)). M1 derives four features per scale:

$$
\begin{aligned}
h_{A,B}(t) &= d_A(t)\bar\phi_A^{(B)}(t),\\
r_{A,B}(t) &= \left|\bar\phi_A^{(B)}(t)\right|,\\
a_{A,B}(t) &= \left(\bar\phi_A^{(B)}(t)\right)^2,\\
b_{A,B}(t) &= \left(\bar\phi_A^{(B)}(t)\right)^4.
\end{aligned}
$$

The current second's total quote volume is represented by

$$
\ell_A(t)=\log\left(1+V_A^+(t)+V_A^-(t)\right).
$$

The complete feature vector has

$$
1+4\times7=29
$$

columns. The even powers are engineered nonlinear transforms for a linear classifier. Their use does not imply that the market follows a physical φ⁴ field theory.

## Target

Let (P_A(t)) be the target market's VWAP in completed second (t). The aggressor-aligned markout at horizon (H) is

$$
m_{A,H}(t)=10^4d_A(t)\frac{P_A(t+H)-P_A(t)}{P_A(t)}.
$$

The binary label is

$$
Y_{A,H}(t)=\mathbf{1}\{m_{A,H}(t)>0\}.
$$

A positive label means that price subsequently moved in the current aggressor's direction, which is an adverse-selection proxy for a hypothetical passive counterparty.

An observation is valid only when the target market is active, (d_A(t)\neq0), both current and future VWAP values are finite and positive, and the target timestamp remains inside the same day.

## Estimator

M1 uses a standardized logistic model implemented with:

- `StandardScaler` fitted on training data only;
- `SGDClassifier(loss="log_loss", penalty="l2")`;
- averaged coefficients;
- a fixed random seed;
- `alpha` selected from `1e-5`, `1e-4`, and `1e-3` by mean daily development AP.

In scikit-learn, `alpha` is the L2 regularization strength. Larger values mean stronger regularization. The selected value in the final M1-M3 contour is `1e-3`.

## Validation protocol

Two related experiments are reported for M1.

### REAL-02: M1 versus M0

| Split | Dates |
|---|---|
| Train | 2025-01-06 to 2025-01-15 |
| Development | 2025-01-16 to 2025-01-19 |
| Test | 2025-01-20 to 2025-01-26 |

This experiment evaluates 1-second and 5-second horizons. Daily AP differences are resampled by calendar day with 5,000 bootstrap repetitions.

### REAL-05: common M1-M3 contour

| Split | Dates |
|---|---|
| Train | 2025-01-06 to 2025-01-19 |
| Development | 2025-01-20 to 2025-01-26 |
| Final test | 2025-01-27 to 2025-02-02 |

REAL-05 fixes the horizon at 5 seconds and uses the second-level M1 as the local baseline for M2 and M3.

## Results

### REAL-02: daily AP improvement over M0

| Market | Horizon | Mean delta AP | 95% day-bootstrap interval |
|---|---:|---:|---:|
| BTCUSDT | 1 s | +0.01960 | [0.01423, 0.02484] |
| BTCUSDT | 5 s | +0.01727 | [0.01095, 0.02406] |
| ETHUSDT | 1 s | +0.01827 | [0.01272, 0.02353] |
| ETHUSDT | 5 s | +0.01106 | [0.00597, 0.01647] |

The difference was positive on all seven test days for both markets and both horizons. This supports the claim that a local multiscale flow profile ranks short-horizon positive markouts better than the fixed-scale baseline.

Results from the event-level REAL-02 implementation should not be mechanically compared with absolute metrics from the second-level REAL-05 implementation.

## Repository map

- Current M1-M3 experiment: [`coupled_rg_final.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/coupled_rg_final.py)
- Historical M0-M1 out-of-time comparison: [`adverse_selection_oos.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/adverse_selection_oos.py)
- Experiment registry: [`experiment_registry.md`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/docs/results/experiment_registry.md)

## Reproduce the current M1-M3 contour

The command requires the project services and ClickHouse data to be available.

```bash
docker compose exec api python -m \
  revolut_app.real_market.experiments.coupled_rg_final \
  --target-symbols BTCUSDT ETHUSDT \
  --horizon-seconds 5 \
  --alphas 0.00001 0.0001 0.001 \
  --train-start 2025-01-06 \
  --train-end 2025-01-19 \
  --development-start 2025-01-20 \
  --development-end 2025-01-26 \
  --final-test-start 2025-01-27 \
  --final-test-end 2025-02-02 \
  --bootstrap-samples 5000 \
  --output /opt/airflow/data/real_market/results/coupled_rg_final.json
```

The output records configuration, selected regularization strengths, development scores, final daily and aggregate metrics, paired bootstrap comparisons, and raw-scale coefficients.

## Limitations

- Nested windows create correlated features, so individual coefficients should not be interpreted independently.
- Calendar-time windows contain different event counts across liquidity regimes.
- M1 observes only the target market and ignores related trading pairs.
- The binary target ignores markout magnitude.
- Aggregate trades do not include the order book, fees, private inventory, fills, or realized hedging costs.
- Seven test days provide a useful internal comparison but limited regime coverage.
- Multiple scales do not establish scale invariance or a renormalization-group flow in the physical sense.

## References

1. Glosten, L. R., and Milgrom, P. R. (1985). [Bid, ask and transaction prices in a specialist market with heterogeneously informed traders](https://doi.org/10.1016/0304-405X(85)90044-3).
2. Easley, D., Lopez de Prado, M. M., and O'Hara, M. (2012). [Flow toxicity and liquidity in a high-frequency world](https://doi.org/10.1093/rfs/hhs053).
3. Pedregosa, F. et al. (2011). [Scikit-learn: Machine Learning in Python](https://jmlr.org/papers/v12/pedregosa11a.html).
4. Efron, B., and Tibshirani, R. J. (1994). [An Introduction to the Bootstrap](https://doi.org/10.1201/9780429246593).
5. Binance. [Spot REST API market data documentation](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints).
