# Business Interpretation

Predictive metrics are only useful when translated into decisions and unit economics.

## From Score to Value

A model score can support:

- widening or tightening a quote;
- accepting or rejecting marginal flow;
- triggering a hedge;
- ranking trades by adverse-selection risk;
- reporting stress or inventory regimes.

The business value depends on acceptance elasticity, spread capture, hedge cost, missed revenue, and risk limits.

## Economic Language

| Term | Use |
|---|---|
| Simulated PnL | Output of synthetic replay assumptions. |
| Markout exposure | Observed future price movement proxy, not realized PnL. |
| Expected value | Policy-level expected gain after costs and action thresholds. |
| Oracle upper bound | Diagnostic estimate with perfect future information, not deployable performance. |

## Recommended Reporting

Always report a metric pair:

- predictive quality, such as AP, ROC-AUC, calibration, or lift;
- economic quality, such as expected value, cost-adjusted capture, or risk-adjusted utility.

