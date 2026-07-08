# ReDataX Experiment Registry


---

## 1. Статусы

| Статус | Значение |
|---|---|
| **Final holdout verified** | Модель была зафиксирована до однократной проверки на ранее не использованном периоде. |
| **Out-of-time verified** | Проверка проведена на более поздних датах, но затем этот период использовался для анализа и больше не является финальным holdout. |
| **Artifact verified** | Результат подтверждён сохранённым JSON/CSV/PDF/log. |
| **Historical/local** | Результат получен в локальной или более ранней ветке; текущий путь в `main` ещё не подтверждён. |
| **Rejected** | Гипотеза не дала устойчивого инкрементального эффекта. |
| **Exploratory** | Диагностический результат, не являющийся production- или causal-утверждением. |

---

## 2. Канонические обозначения моделей

| ID | Название | Определение |
|---|---|---|
| `M0` | Single-scale order-flow model | Локальная модель с фиксированным масштабом, преимущественно `B=16`. |
| `M1` | Local multiscale order-flow model | Локальные признаки signed flow на `B={1,2,4,8,16,32,64}`. |
| `M2` | RG-inspired scale-flow model | `M1` плюс разности масштабов и локальные scaling observables. |
| `RG-noJ` | Cross-market multiscale effective-field model | Синхронные поля BTCUSDT, ETHUSDT и ETHBTC без явных произведений `J_ij phi_i phi_j`. |
| `RG-J` | Coupled cross-market effective-field model | `RG-noJ` плюс явные попарные interaction terms. |

`RG-noJ` и `RG-J` являются supervised predictive effective-action models. Их коэффициенты нельзя называть равновесными физическими константами связи.

---

## 3. Основные определения

### Signed order-flow field

\[
\phi_i(t)=
\frac{V_i^{buy}(t)-V_i^{sell}(t)}
{V_i^{buy}(t)+V_i^{sell}(t)+\varepsilon}.
\]

### Coarse-graining

\[
\phi_i^{(B)}(t)=\frac{1}{B}\sum_{k=0}^{B-1}\phi_i(t-k),
\qquad B\in\{1,2,4,8,16,32,64\}.
\]

### Adverse-selection markout

\[
m_{t,H}=\varepsilon_t
\frac{P_{t+H}^{future}-P_t}{P_t}10^4.
\]

Положительный markout означает движение цены в направлении агрессора и против пассивного market maker.

### Observed dollar adverse-selection exposure

\[
L_t=N_t\frac{\max(m_{t,H},0)}{10^4}.
\]

Это proxy наблюдаемого markout exposure, а не фактический PnL market maker.

---

## 4. Сводная таблица экспериментов

| ID | Эксперимент | Основной вопрос | Итог |
|---|---|---|---|
| `SYN-01` | Synthetic policy baseline | Улучшает ли inventory-aware policy risk-return относительно naive? | Положительный simulation result |
| `SYN-02` | Hamiltonian observer consistency | Меняет ли observer execution path? | Execution-neutral в проверенном replay |
| `SYN-03` | Directional controller | Даёт ли Hamiltonian controller экономический эффект? | Historical/local, не использовать как current-main headline |
| `RG-01` | Synthetic temporal coarse-graining | Даёт ли scale-aware controller дополнительный эффект? | Controller extension rejected, analytics retained |
| `REAL-01` | One-day smoke test | Есть ли вообще короткий multiscale signal? | Да, на 1-5 секундах |
| `REAL-02` | Multi-day OOS multiscale proof | Превосходит ли `M1` модель `M0` out of time? | Подтверждено |
| `REAL-03` | RG-inspired ablation | Добавляет ли `M2` эффект сверх `M1`? | Не подтверждено |
| `REAL-04` | Dollar adverse-selection capture | Захватывает ли `M1` больше dollar loss, чем `M0`? | Относительный эффект есть, абсолютный capture слабый |
| `REAL-05` | Final cross-market experiment | Помогают ли другие рынки и явные `J`? | `RG-noJ` подтверждена, общий `J`-эффект отвергнут |

---

# 5. Synthetic experiments

## SYN-01 - Synthetic policy baseline

**Цель.** Сравнить `naive`, `inventory_aware` и `platform` на одинаковых синтетических потоках запросов.

**Метрики.** Net PnL, acceptance, spread, stress-time, inventory pressure, Hamiltonian state.

**Вывод.** В проверенных synthetic artifacts `inventory_aware` демонстрирует более сильный risk-return profile, чем `naive`. Рост inventory bucket связан с ростом Hamiltonian и вероятности stress-regime.

**Статус.** Artifact verified.

**Допустимая формулировка.**

> В синтетическом replay inventory-aware pricing уменьшает давление на inventory и улучшает simulated risk-return относительно naive policy при заданных предположениях генератора.

**Недопустимая формулировка.**

> Модель воспроизводит production-алгоритм Revolut или доказывает реальную прибыль банка.

---

## SYN-02 - Hamiltonian observer consistency

**Цель.** Проверить, что observer рассчитывает `h_total`, компоненты Hamiltonian и regimes, не меняя execution path.

**Вывод.** В baseline-versus-observer consistency check execution mismatches отсутствовали.

**Статус.** Artifact verified.

**Допустимая формулировка.**

> Hamiltonian observer был проверен как execution-neutral diagnostic layer в тестовом replay.

---

## SYN-03 - Directional pricing controller

**Цель.** Использовать направление и величину Hamiltonian state для изменения pricing decisions.

**Результат.** Ранее локальные эксперименты показывали положительный эффект, однако предыдущий аудит репозитория не подтвердил полный end-to-end controller path в текущем `main`.

**Статус.** Historical/local.

**Ограничение.** Точные проценты controller uplift не публикуются в README до появления воспроизводимого current-main command и сохранённого result artifact.

---

## RG-01 - Synthetic temporal coarse-graining

**Цель.** Проверить структуру observables на масштабах `B={1,2,4,8,16,32,64}` и полезность scale-aware controller.

**Результат.** Multiscale diagnostics сохранили интерпретируемую структуру, но scale-aware controller не дал стабильного инкрементального эффекта.

**Статус.** Exploratory; controller hypothesis rejected.

**Вывод.** RG-layer сохранён как analytics/diagnostics, а не как отдельный controller.

---

# 6. Real-market experiments

## REAL-01 - One-day adverse-selection smoke test

**Дата.** `2025-01-06`.

**Данные.** Binance spot aggTrades.

| Symbol | Trades |
|---|---:|
| BTCUSDT | 1,357,198 |
| ETHUSDT | 845,102 |
| ETHBTC | 25,966 |

**Split.** 60% train, 20% validation, 20% test внутри дня.

**Сравнение.** Fixed-scale baseline против multiscale model.

### Horizon 1 second

| Symbol | Delta ROC-AUC | Delta AP | Delta top-decile lift |
|---|---:|---:|---:|
| BTCUSDT | +0.03698 | +0.01445 | +0.00986 |
| ETHUSDT | +0.06310 | +0.03322 | +0.02746 |
| ETHBTC | -0.00129 | +0.00818 | +0.05731 |

### Horizon 5 seconds

| Symbol | Delta ROC-AUC | Delta AP | Delta top-decile lift |
|---|---:|---:|---:|
| BTCUSDT | +0.01942 | +0.00800 | +0.01290 |
| ETHUSDT | +0.03431 | +0.02056 | +0.04175 |
| ETHBTC | +0.00821 | +0.03229 | -0.11163 |

**Вывод.** Продолжать исследование имеет смысл на горизонтах 1-5 секунд. На 30-60 секундах эффект для ликвидных USDT-пар существенно ослабевает.

**Статус.** Positive smoke test, не финальное доказательство.

---

## REAL-02 - Multi-day out-of-time multiscale proof

**Symbols.** BTCUSDT, ETHUSDT.

**Horizons.** 1 s, 5 s.

| Role | Dates |
|---|---|
| Train | 2025-01-06 - 2025-01-15 |
| Validation | 2025-01-16 - 2025-01-19 |
| Test | 2025-01-20 - 2025-01-26 |

**Основная метрика.** Daily Average Precision и paired day-level bootstrap.

### `M1 - M0` на test

| Symbol | Horizon | Mean Delta AP | 95% CI | Positive days |
|---|---:|---:|---:|---:|
| BTCUSDT | 1 s | +0.01960 | [+0.01423, +0.02484] | 7/7 |
| BTCUSDT | 5 s | +0.01727 | [+0.01095, +0.02406] | 7/7 |
| ETHUSDT | 1 s | +0.01827 | [+0.01272, +0.02353] | 7/7 |
| ETHUSDT | 5 s | +0.01106 | [+0.00597, +0.01647] | 7/7 |

**Вывод.** `M1 > M0` подтверждено для двух инструментов и обоих коротких горизонтов.

**Статус.** Out-of-time verified. Период позднее использовался как development и больше не считается untouched final holdout.

**Допустимая формулировка.**

> Local multiscale order flow содержит устойчивую короткогоризонтную информацию сверх fixed single-scale representation.

---

## REAL-03 - RG-inspired scale-flow ablation

**Цель.** Проверить, дают ли scale differences и scaling observables дополнительную информацию сверх raw multiscale fields.

### `M2 - M1`

| Symbol | Horizon | Mean Delta AP | 95% CI | Вывод |
|---|---:|---:|---:|---|
| BTCUSDT | 1 s | +0.000333 | [+0.000042, +0.000610] | Минимальный AP-only эффект |
| BTCUSDT | 5 s | -0.000506 | [-0.001491, +0.000170] | Нет устойчивого эффекта |
| ETHUSDT | 1 s | +0.000274 | [-0.000219, +0.000754] | Не значимо |
| ETHUSDT | 5 s | +0.000347 | [-0.000093, +0.000712] | Не значимо |

**Интерпретация.** Новые transforms были построены из тех же `phi_B`, уже доступных `M1`, поэтому оказались в основном избыточными.

**Статус.** Rejected.

**Допустимая формулировка.**

> Простые RG-inspired scale transforms не дали общего преимущества над raw multiscale representation.

---

## REAL-04 - Observed dollar adverse-selection capture

**Цель.** Перевести ranking quality в observed dollar markout exposure без assumptions о spread, inventory, fill probability и hedging.

| Role | Dates |
|---|---|
| Train | 2025-01-06 - 2025-01-15 |
| Test | 2025-01-20 - 2025-01-26 |

**Capacities.** 1%, 5%, 10%, 20% сделок в каждом test-day.

### Primary comparison at `q=10%`: `M1 - M0`

| Symbol | Horizon | Delta capture rate | 95% CI | Delta loss per $1m | 95% CI |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 1 s | +0.00647 | [+0.00182, +0.01203] | +$1.35 | [+$0.26, +$2.73] |
| BTCUSDT | 5 s | +0.06661 | [+0.06276, +0.07053] | +$16.14 | [+$10.63, +$22.66] |
| ETHUSDT | 1 s | +0.00044 | [+0.00032, +0.00060] | +$0.07 | [+$0.05, +$0.12] |
| ETHUSDT | 5 s | +0.00224 | [+0.00125, +0.00403] | +$0.65 | [+$0.25, +$1.42] |

**Сильнейший relative result.** BTCUSDT, 5 s, q=20%: Delta capture rate `+0.15744`, Delta loss per $1m `+$37.78`.

**Критическое ограничение.** `M1` обучалась на binary toxicity, а не на expected dollar loss. Абсолютный capture в ряде конфигураций оставался хуже random trade-fraction benchmark. Выигрыш над `M0` частично связан с различием selected notional.

**Статус.** Out-of-time relative improvement; economic interpretation exploratory.

**Допустимая формулировка.**

> При одинаковом количестве выбранных сделок `M1` захватывает больше observed adverse-selection exposure, чем `M0`.

**Недопустимая формулировка.**

> Модель заработала указанный объём прибыли.

---

## REAL-05 - Final synchronized cross-market experiment

**Цель.** Проверить на untouched final holdout:

1. Добавляет ли состояние других рынков информацию сверх локальной `M1`.
2. Дают ли явные interaction terms дополнительный эффект сверх cross-market field.

**Markets.** BTCUSDT, ETHUSDT, ETHBTC.

**Target markets.** BTCUSDT, ETHUSDT.

**Grid.** 1 second.

**Scales.** 1, 2, 4, 8, 16, 32, 64 seconds.

**Horizon.** 5 seconds.

| Role | Dates |
|---|---|
| Train | 2025-01-06 - 2025-01-19 |
| Development | 2025-01-20 - 2025-01-26 |
| Final test | 2025-01-27 - 2025-02-02 |

**Regularization grid.** `alpha={1e-5,1e-4,1e-3}`. Все модели выбрали `alpha=1e-3`. После просмотра final holdout сетка не расширялась.

### REAL-05A - `RG-noJ - M1`

#### BTCUSDT

| Metric | Mean difference | 95% CI | Positive days |
|---|---:|---:|---:|
| ROC-AUC | +0.01452 | [+0.01238, +0.01696] | 7/7 |
| Average Precision | +0.01879 | [+0.01676, +0.02129] | 7/7 |
| Brier improvement | +0.00301 | [+0.00210, +0.00388] | 7/7 |
| Top-decile lift | +0.06856 | [+0.05865, +0.07971] | 7/7 |

Pooled AP: `0.63155 -> 0.64967`.

#### ETHUSDT

| Metric | Mean difference | 95% CI | Positive days |
|---|---:|---:|---:|
| ROC-AUC | +0.00849 | [+0.00602, +0.01096] | 7/7 |
| Average Precision | +0.01120 | [+0.00892, +0.01385] | 7/7 |
| Brier improvement | +0.00100 | [+0.00050, +0.00155] | 7/7 |
| Top-decile lift | +0.04268 | [+0.03438, +0.05305] | 7/7 |

Pooled AP: `0.63675 -> 0.64763`.

**Вывод.** Cross-market synchronized state добавляет устойчивую информацию сверх local target-market model.

**Статус.** Final holdout verified. Это сильнейший real-market result проекта.

---

### REAL-05B - `RG-J - RG-noJ`

#### BTCUSDT

| Metric | Mean difference | 95% CI | Positive days |
|---|---:|---:|---:|
| ROC-AUC | -0.000075 | [-0.000191, +0.000018] | 3/7 |
| Average Precision | +0.000259 | [+0.000113, +0.000396] | 6/7 |
| Brier improvement | -0.000057 | [-0.000173, +0.000056] | 3/7 |
| Top-decile lift | +0.000382 | [-0.001617, +0.002497] | 3/7 |

**Интерпретация.** Статистически положительный, но очень малый AP-only effect без подтверждения ROC-AUC, calibration и top-decile lift.

#### ETHUSDT

| Metric | Mean difference | 95% CI | Positive days |
|---|---:|---:|---:|
| ROC-AUC | -0.000284 | [-0.000471, -0.000096] | 1/7 |
| Average Precision | -0.000229 | [-0.000428, -0.000032] | 1/7 |
| Brier improvement | -0.000132 | [-0.000196, -0.000077] | 0/7 |
| Top-decile lift | -0.000257 | [-0.001045, +0.000810] | 1/7 |

**Интерпретация.** Явные `J` ухудшают ETHUSDT.

**Общий вывод.** Universal coupled-interaction advantage не подтверждён.

**Финальная выбранная модель.** `RG-noJ`.

**Каноническое название.**

> Synchronized cross-market multiscale effective-field model without explicit pairwise interaction terms.

---

# 7. Финальные выводы проекта

## Подтверждено

1. Multiscale local flow превосходит fixed single-scale representation.
2. Эффект воспроизводится out of time на BTCUSDT и ETHUSDT.
3. Синхронное состояние связанных рынков даёт дополнительную predictive information.
4. Cross-market effect выдержал untouched seven-day final holdout.
5. `RG-noJ` является лучшей проверенной real-market specification.
6. Отрицательные результаты сохранены без post-holdout tuning.

## Не подтверждено

1. Простые RG scale-flow transforms не дают общего эффекта сверх `M1`.
2. Явные `J` не дают устойчивого cross-symbol преимущества.
3. Коэффициенты supervised model нельзя интерпретировать как физические equilibrium couplings.
4. Public aggTrades не раскрывают реальный inventory market maker.
5. Observed markout exposure не равен realized PnL.
6. Проект не восстанавливает production-алгоритм Revolut.

---

# 8. Матрица допустимых утверждений

| Утверждение | README | LaTeX report | Resume/interview |
|---|---|---|---|
| `M1` лучше `M0` | Да | Да, подробно | Да |
| `RG-noJ` лучше `M1` на final holdout | Да, headline | Да, подробно | Да |
| `J` немного улучшает BTC AP | Краткая оговорка | Да | Только с caveat |
| `J` улучшает модель в целом | Нет | Явно отвергнуть | Нет |
| Dollar capture лучше `M0` | Кратко и с caveat | Да | Только как exploratory |
| Realized trading PnL uplift | Нет | Нет | Нет |
| Synthetic inventory-aware policy лучше naive | Да, как simulation | Да | Да, с пометкой simulation |
| Historical controller percentages | Нет до воспроизведения | Только appendix | Нет |
| Полноценная Wilsonian RG доказана | Нет | Нет | Нет |

---

# 9. Raw artifacts

| Artifact | Experiments | Repository destination |
|---|---|---|
| `oos_rg_proof.json` | `REAL-02`, `REAL-03` | `docs/results/raw/oos_rg_proof.json` |
| `adverse_selection_capture.json` | `REAL-04` | `docs/results/raw/adverse_selection_capture.json` |
| `coupled_rg_final.json` | `REAL-05` | `docs/results/raw/coupled_rg_final.json` |
| One-day MVP logs | `REAL-01` | `docs/results/raw/adverse_selection_mvp/` |
| Synthetic baseline exports | `SYN-01` | `docs/results/raw/synthetic_baseline/` |
| Observer consistency export | `SYN-02` | `docs/results/raw/observer_consistency/` |
| Historical controller artifacts | `SYN-03` | `docs/results/historical/controller/` |

Figures must be generated from committed raw artifacts, not from manually copied values.

---

# 10. Planned figures

| Figure ID | Experiment | Figure |
|---|---|---|
| `FIG-ARCH-01` | Platform | End-to-end architecture |
| `FIG-SYN-01` | `SYN-01` | Synthetic policy risk-return comparison |
| `FIG-SYN-02` | `SYN-02` | Hamiltonian and regime distributions |
| `FIG-REAL-01` | `REAL-02` | `M1-M0` bootstrap intervals |
| `FIG-REAL-02` | `REAL-03` | Rejected `M2-M1` ablation |
| `FIG-REAL-03` | `REAL-04` | Dollar capture by capacity |
| `FIG-REAL-04` | `REAL-05A` | Final `RG-noJ-M1` improvement |
| `FIG-REAL-05` | `REAL-05B` | `J` ablation for BTC and ETH |
| `FIG-TIME-01` | Real experiments | Train/development/final-test timeline |

---

# 11. Reproduction checklist

- [ ] Commit raw JSON artifacts.
- [ ] Verify experiment commands against current module paths.
- [ ] Store exact Python/package versions.
- [ ] Commit tests for all public experiment CLIs.
- [ ] Use stored integer `timestamp_us` where available.
- [ ] Use half-open future windows `[t+H,t+H+W)` consistently.
- [ ] Confirm the Docker `.git` volume path.
- [ ] Verify the historical controller path before publishing metrics.
- [ ] Generate figures only from committed raw artifacts.
- [ ] Do not retune on `2025-01-27` - `2025-02-02`.

---

# 12. Canonical project summary

ReDataX is a production-like banking and market-data research platform combining synthetic transaction simulation, inventory-aware pricing, ClickHouse analytics, orchestration, and physics-inspired multiscale modelling. On real Binance aggTrades, local multiscale signed flow consistently outperformed a single-scale baseline at short horizons. A final untouched holdout further showed that synchronized cross-market state from BTCUSDT, ETHUSDT, and ETHBTC improved adverse-selection prediction for both BTCUSDT and ETHUSDT across Average Precision, ROC-AUC, Brier score, and top-decile lift. Explicit pairwise interaction terms produced only a tiny AP-only gain for BTCUSDT and degraded ETHUSDT, so the final selected specification is the simpler cross-market multiscale `RG-noJ` model. The project supports a physics-inspired effective-field interpretation and a robust engineering workflow, but does not claim reconstruction of a physical renormalization-group flow or realized trading profitability.
