# ReDataX M2 - Cross-Market Multiscale Model

M2 extends the local M1 classifier with synchronized multiscale flow states from BTCUSDT, ETHUSDT, and ETHBTC. It is the accepted `RG-noJ` specification and the strongest validated classifier in the M0-M3 sequence.

> M2 is a predictive cross-market model. Its results show incremental information, not a causal transmission mechanism between markets.

## Model card

| Field | Value |
|---|---|
| Model ID | `M2` |
| Experiment name | `rg_no_j` |
| Family | Regularized binary classification |
| Status | Accepted and selected among M0-M3 |
| Predecessor | `M1` local multiscale model |
| Primary target | Positive aggressor-aligned future markout |
| Target markets | `BTCUSDT`, `ETHUSDT` |
| Input markets | `BTCUSDT`, `ETHUSDT`, `ETHBTC` |
| Time scales | `1, 2, 4, 8, 16, 32, 64` seconds |
| Feature count | 87 |
| Forecast horizon | 5 seconds |
| Main implementation | [`coupled_rg_final.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/coupled_rg_final.py) |

## Research question

After the target market's own multiscale state is known, do synchronized states from related markets improve prediction of the target's future signed markout?

For target market (A) and observed market set

$$
\mathcal S=\{\mathrm{BTCUSDT},\mathrm{ETHUSDT},\mathrm{ETHBTC}\},
$$

M2 tests whether

$$
\Pr(Y_{A,H}=1\mid X_A,X_{\mathcal S\setminus A})
\neq
\Pr(Y_{A,H}=1\mid X_A).
$$

M1 and M2 use the same target, observations, estimator family, temporal splits, and metrics. Their only intended difference is the cross-market information set.

## Why cross-market state may help

BTCUSDT, ETHUSDT, and ETHBTC share assets and respond to common liquidity and information shocks. A target-market imbalance can therefore represent different states depending on whether related markets confirm, oppose, or ignore it.

This is a predictive argument. Simultaneous market states can improve forecasting even when both markets are responding to an unobserved common factor.

## Data and synchronization

The model uses public Binance Spot `aggTrades`, aggregated to a common grid of 86,400 UTC seconds per day.

For each market (s\in\mathcal S), ReDataX calculates aggressive buy and sell quote volumes, (V_s^+(t)) and (V_s^-(t)), and the signed-flow field

$$
\phi_s(t)=
\begin{cases}
\dfrac{V_s^+(t)-V_s^-(t)}{V_s^+(t)+V_s^-(t)}, & V_s^+(t)+V_s^-(t)>0,\\
0, & \text{otherwise}.
\end{cases}
$$

The field is dimensionless and lies in ([-1,1]). ETHBTC quote volume is denominated in BTC, while the USDT pairs use USDT. This does not affect the normalized field, but it means the raw log-volume feature starts in a different unit. Standardization reduces numerical scale differences but does not make the economic units identical.

## Multiscale features

For every market and scale (B\in\{1,2,4,8,16,32,64\}), the trailing calendar-time field is

$$
\bar\phi_s^{(B)}(t)=\frac{1}{B}\sum_{u=0}^{B-1}\phi_s(t-u).
$$

Let (d_A(t)=\operatorname{sign}\phi_A(t)) be the current orientation of the target market. M2 creates four transforms for every market-scale pair:

$$
\begin{aligned}
h_{s,B}^{(A)}(t) &= d_A(t)\bar\phi_s^{(B)}(t),\\
r_{s,B}(t) &= \left|\bar\phi_s^{(B)}(t)\right|,\\
a_{s,B}(t) &= \left(\bar\phi_s^{(B)}(t)\right)^2,\\
b_{s,B}(t) &= \left(\bar\phi_s^{(B)}(t)\right)^4.
\end{aligned}
$$

It also includes the current log quote volume

$$
\ell_s(t)=\log\left(1+V_s^+(t)+V_s^-(t)\right)
$$

for each market. The total feature count is

$$
|\mathcal S|+4|\mathcal S||\mathcal B|
=3+4\times3\times7=87.
$$

No explicit pairwise products are included. This is the meaning of `no_j`: market blocks enter the linear logit additively, although the model can still use all blocks at the same time.

## Target

For target market (A\in\{\mathrm{BTCUSDT},\mathrm{ETHUSDT}\}), define

$$
m_{A,H}(t)=10^4d_A(t)\frac{P_A(t+H)-P_A(t)}{P_A(t)},
\qquad
Y_{A,H}(t)=\mathbf 1\{m_{A,H}(t)>0\}.
$$

The final experiment fixes (H=5) seconds. A valid observation requires at least 64 seconds of history, a nonzero target direction, finite positive target VWAP at (t) and (t+H), and a future timestamp inside the same day. Related markets may be inactive in the current second; zero flow is a valid state.

## Estimator and training

M2 uses standardized logistic regression:

$$
\widehat p_A(t)=\sigma\left(\beta_0+\sum_{s\in\mathcal S}\beta_s^\top z_s(t)\right).
$$

The implementation uses:

- `StandardScaler` fitted on training data only;
- `SGDClassifier(loss="log_loss", penalty="l2")`;
- coefficient averaging;
- a fixed random seed;
- development selection over `alpha` in `1e-5`, `1e-4`, and `1e-3`.

`alpha` is the L2 regularization strength in scikit-learn. The selected M2 value is `1e-3`.

## Temporal protocol

| Split | Dates | Purpose |
|---|---|---|
| Train | 2025-01-06 to 2025-01-19 | Fit scaler and classifier candidates |
| Development | 2025-01-20 to 2025-01-26 | Select `alpha` by mean daily AP |
| Final test | 2025-01-27 to 2025-02-02 | One out-of-time comparison |

The experiment does not shuffle individual observations between calendar periods. Uncertainty is estimated with 5,000 bootstrap resamples of the seven daily metric differences.

Primary metrics are ROC-AUC, Average Precision, Brier score, and positive-class lift in the top prediction decile. Brier improvement is defined as `Brier(M1) - Brier(M2)`, so positive values mean lower error for M2.

## Results

### REAL-05A: mean daily M2 minus M1 difference

| Market | Metric | Difference | 95% day-bootstrap interval |
|---|---|---:|---:|
| BTCUSDT | ROC-AUC | +0.01452 | [0.01238, 0.01696] |
| BTCUSDT | Average Precision | +0.01879 | [0.01676, 0.02129] |
| BTCUSDT | Brier improvement | +0.00301 | [0.00210, 0.00388] |
| BTCUSDT | Top-decile lift | +0.06856 | [0.05865, 0.07971] |
| ETHUSDT | ROC-AUC | +0.00849 | [0.00602, 0.01096] |
| ETHUSDT | Average Precision | +0.01120 | [0.00892, 0.01385] |
| ETHUSDT | Brier improvement | +0.00100 | [0.00050, 0.00155] |
| ETHUSDT | Top-decile lift | +0.04268 | [0.03438, 0.05305] |

All four metrics improved on all seven final-test days for both targets. Pooled AP increased from 0.63155 to 0.64967 for BTCUSDT and from 0.63675 to 0.64763 for ETHUSDT.

The accepted conclusion is limited to short-horizon signed-markout ranking under the tested data and protocol. It is not evidence of realized trading profit or causal market influence.

## Repository map

- Features, training, evaluation, bootstrap, and JSON output: [`coupled_rg_final.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/coupled_rg_final.py)
- Market-data query layer: [`queries.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/src/revolut_app/real_market/experiments/queries.py)
- Experiment registry: [`experiment_registry.md`](https://github.com/vasile8egor/ReDataX_pet_project/blob/2d6affc3893398cb3c7b02f31f7d678d5ea0fdfe/docs/results/experiment_registry.md)

## Reproduce

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

The command requires the ReDataX services and the corresponding ClickHouse market data.

## Limitations

- Cross-market association does not establish causality or direction of information transfer.
- Public timestamps do not reproduce the latency of a production data pipeline.
- Calendar windows can contain very different event counts across markets and regimes.
- Inactive seconds are explicitly encoded as zero flow; changing this rule changes the model.
- The source does not contain the order book, fees, private inventory, fill probabilities, or hedge execution.
- The seven-day final test does not cover every market regime.
- `RG-noJ` is a naming convention for a multiscale predictive representation, not a physical renormalization-group calculation.

## References

1. Glosten, L. R., and Milgrom, P. R. (1985). [Bid, ask and transaction prices in a specialist market with heterogeneously informed traders](https://doi.org/10.1016/0304-405X(85)90044-3).
2. Easley, D., Lopez de Prado, M. M., and O'Hara, M. (2012). [Flow toxicity and liquidity in a high-frequency world](https://doi.org/10.1093/rfs/hhs053).
3. Cont, R., Kukanov, A., and Stoikov, S. (2014). [The price impact of order book events](https://doi.org/10.1093/jjfinec/nbt003).
4. Pedregosa, F. et al. (2011). [Scikit-learn: Machine Learning in Python](https://jmlr.org/papers/v12/pedregosa11a.html).
5. Efron, B., and Tibshirani, R. J. (1994). [An Introduction to the Bootstrap](https://doi.org/10.1201/9780429246593).
6. Binance. [Spot REST API market data documentation](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints).
