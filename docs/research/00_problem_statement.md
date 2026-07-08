# Problem Statement

ReDataX studies whether short-horizon order-flow structure can improve FX-style inventory and pricing decisions in a controlled research environment.

The project has two related questions:

1. In synthetic FX flows, can inventory-aware pricing improve risk-return trade-offs compared with naive pricing?
2. In real Binance `aggTrades`, does multiscale signed order flow contain short-horizon adverse-selection signal beyond a single fixed time scale?

## Scope

The project is not a trading system and does not reproduce internal algorithms from any financial institution. It is a research platform for data engineering, microstructure modeling, decision policy simulation, and analytics.

## Primary Objects

| Object | Definition |
|---|---|
| Client request | A simulated FX quote or transaction event. |
| Inventory state | Current signed exposure by currency or synthetic asset. |
| Aggressive trade | Binance `aggTrades` event with inferred buyer/seller aggression. |
| Signed flow field | Normalized buy-minus-sell volume over a time bucket. |
| Markout | Future price movement in the direction of the aggressor. |
| Decision policy | Rule that converts state or model score into action. |

## Success Criteria

- Models must be compared on temporally separated data.
- Improvements must be reported with effect size, uncertainty, and operating-point sensitivity.
- Business interpretation must use unit economics rather than raw classification metrics alone.
- Claims must state whether they are synthetic, real-market, exploratory, or holdout verified.

