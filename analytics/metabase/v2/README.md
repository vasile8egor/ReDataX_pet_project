# ReDataX Metabase Analytics v2

Этот пакет создаёт два воспроизводимых дэшборда:

1. **FX Policy & Risk** - синтетическая банковская/FX-система.
2. **Real Market Model Validation** - out-of-time результаты на Binance aggTrades.

## 1. Установка файлов

Скопируйте содержимое пакета в корень репозитория, сохраняя пути.

## 2. Создание аналитических таблиц

```bash
docker compose exec -T clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --multiquery \
  < sql/clickhouse/init_analytics_metrics.sql
```

## 3. Размещение JSON-артефактов

Ожидаемые пути внутри API-контейнера:

```text
/opt/airflow/data/real_market/results/oos_rg_proof.json
/opt/airflow/data/real_market/results/adverse_selection_capture.json
/opt/airflow/data/real_market/results/coupled_rg_final.json
```

Host-путь при стандартном volume:

```text
./data/real_market/results/
```

## 4. Загрузка артефактов в ClickHouse

```bash
bash scripts/load_metabase_analytics.sh
```

Проверка:

```bash
docker compose exec clickhouse \
  clickhouse-client \
  --user default \
  --password default \
  --query "
    SELECT experiment_id, count()
    FROM gold.fact_model_validation_metrics FINAL
    GROUP BY experiment_id
    ORDER BY experiment_id
  "
```

## 5. Подключение Metabase

Откройте `http://localhost:3001`.

ClickHouse connection:

```text
Host: clickhouse
Port: 8123
Database: gold
Username: default
Password: default
SSL: disabled
```

После загрузки новых таблиц выполните:

```text
Admin settings -> Databases -> ClickHouse -> Sync database schema now
```

## 6. Создание карточек

Для каждого `.sql`:

1. `New -> SQL query`.
2. Выберите ClickHouse.
3. Вставьте SQL.
4. Настройте variables, если они присутствуют.
5. Выберите визуализацию из таблицы ниже.
6. Сохраните карточку с указанным названием.

## 7. Dashboard: FX Policy & Risk

| SQL | Название карточки | Визуализация |
|---|---|---|
| `01_policy_kpi.sql` | Policy KPI Table | Table |
| `02_risk_return_frontier.sql` | Risk-Return Frontier | Scatter: X=`stress_time_pct`, Y=`net_pnl_usd`, series=`policy` |
| `03_customer_tradeoff.sql` | Customer Trade-off | Scatter: X=`customer_spread_bps`, Y=`acceptance_rate_pct`, series=`policy` |
| `04_regime_distribution.sql` | Regime Distribution | Stacked bar: X=`policy`, Y=`regime_pct`, breakout=`regime` |
| `05_phi_trajectory.sql` | Inventory Pressure Trajectory | Line: X=`event_index`, series=`naive`, `inventory_aware`, `platform` |
| `06_hamiltonian_leading_indicator.sql` | Hamiltonian Before Stress | Grouped bar: X=`stress_within_10_events`, Y=`avg_h_total`, breakout=`policy` |

### Рекомендуемая компоновка

```text
┌──────────────────────────────────────────────────────────────┐
│ Policy KPI Table                                             │
├───────────────────────────────┬──────────────────────────────┤
│ Risk-Return Frontier          │ Customer Trade-off           │
├───────────────────────────────┼──────────────────────────────┤
│ Regime Distribution           │ Hamiltonian Before Stress    │
├──────────────────────────────────────────────────────────────┤
│ Inventory Pressure Trajectory                                │
└──────────────────────────────────────────────────────────────┘
```

## 8. Dashboard: Real Market Model Validation

| SQL | Название карточки | Визуализация |
|---|---|---|
| `11_pooled_average_precision.sql` | Final Holdout AP | Grouped bar: X=`symbol`, Y=`average_precision`, breakout=`model` |
| `12_daily_average_precision.sql` | Daily AP Stability | Line: X=`date`, Y=`average_precision`, breakout=`model`; dashboard filter `symbol` |
| `13_bootstrap_ap_delta.sql` | AP Delta with 95% CI | Table |
| `14_quality_summary.sql` | Model Quality Summary | Table |
| `15_capture_rate_by_capacity.sql` | Dollar Loss Capture | Line: X=`capacity_pct`, Y=`capture_rate_pct`, breakout=`model` |
| `16_capture_delta_per_million.sql` | Extra Captured Loss per $1m | Line: X=`capacity_pct`, Y=`delta_loss_per_million_usdt` |

### Рекомендуемая компоновка

```text
┌───────────────────────────────┬──────────────────────────────┐
│ Final Holdout AP              │ AP Delta with 95% CI         │
├──────────────────────────────────────────────────────────────┤
│ Daily AP Stability                                           │
├───────────────────────────────┬──────────────────────────────┤
│ Model Quality Summary         │ Extra Captured Loss per $1m  │
├──────────────────────────────────────────────────────────────┤
│ Dollar Loss Capture                                          │
└──────────────────────────────────────────────────────────────┘
```

## 9. Dashboard filters

### FX Policy & Risk

Создайте Text filters:

- `model_version`;
- `physics_mode`.

Привяжите их к одноимённым SQL variables.

Для `05_phi_trajectory.sql` создайте Text filter:

- `currency`, default `EUR`.

### Real Market Model Validation

Создайте Category filter:

- `symbol`: `BTCUSDT`, `ETHUSDT`.

Создайте Number filter:

- `horizon_seconds`: `1`, `5`.

Не привязывайте horizon filter к карточкам финального coupled experiment, поскольку там зафиксирован горизонт 5 секунд.

## 10. Что экспортировать в репозиторий

Для README и отчёта достаточно четырёх изображений:

1. Risk-Return Frontier.
2. Hamiltonian Before Stress.
3. Final Holdout AP.
4. AP Delta with 95% CI или Extra Captured Loss per $1m.

Экспорт:

```text
Card -> Download results / Export as PNG
Dashboard -> Export as PDF
```

Рекомендуемая структура:

```text
docs/analytics/
├── fx_policy/
├── real_market/
└── metabase/
```

## 11. Интерпретационные ограничения

- Synthetic PnL не является результатом реального банка.
- Future VWAP markout не равен realized PnL.
- `RG-noJ` - physics-inspired cross-market model, а не строгая Wilsonian RG.
- `RG-J` нельзя объявлять общей победившей моделью.
- Final holdout нельзя использовать для нового тюнинга.
