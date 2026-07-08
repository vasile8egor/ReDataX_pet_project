# Model Evolution Dashboard

## Model mapping

| Artifact | Source model | Dashboard ID |
|---|---|---|
| oos_rg_proof.json | m0_single_scale | M0 |
| oos_rg_proof.json | m1_multiscale | M1 |
| oos_rg_proof.json | m2_rg_flow | M1R diagnostic |
| coupled_rg_final.json | m1_local | M1 |
| coupled_rg_final.json | rg_no_j | M2 |
| coupled_rg_final.json | rg_with_j | M3 |
| final economic reporting | direct regression | M4 |
| final economic reporting | hurdle model | M5 |

`m2_rg_flow` from the local OOS experiment is not M2 in the final
documentation. It is a diagnostic extension of M1.

## Load existing analytics facts

```bash
bash scripts/load_metabase_analytics.sh
```

## Apply model-evolution views

```bash
docker compose exec -T clickhouse   clickhouse-client   --user default   --password default   --multiquery   < sql/clickhouse/init_model_evolution_views.sql
```

## Design constraint

Do not place M0-M3 pooled AP values on one undifferentiated chart. The local
OOS and cross-market experiments use different date windows and sample
construction. Use separate panels and rely on paired AP deltas as the main
evolutionary evidence.

## Historical capture warning

The adverse-selection capture artifact constrains event count, not notional.
It is historical ranking evidence. The final economic policies use explicit
notional budgets.
