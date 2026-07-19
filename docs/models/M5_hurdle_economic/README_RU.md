---
model_id: M5
model_name: Двухчастная экономическая модель с барьером
implementation_name: m5_hurdle_economic_model
model_family: hurdle_expected_loss
research_role: separate_occurrence_and_severity_estimation_for_P3
implementation_status: planned
prediction_horizon_seconds: 600
decision_step_seconds: 10
primary_policy: P3_hurdle_economic
reference_model: M4_direct_value_regression
---

# M5: двухчастная экономическая модель с барьером

## 1. Назначение

Этот файл описывает прикладную спецификацию модели M5:

- фактический статус реализации;
- место M5 в последовательности M0-M5;
- требования к данным и целевым переменным;
- обучение компонента вероятности неблагоприятного события;
- обучение компонента условной амплитуды убытка;
- объединение прогнозов в ожидаемый неблагоприятный маркаут;
- временную проверку и контроль утечек;
- калибровку обеих компонент и итогового произведения;
- подключение к политике P3;
- сравнение M5 с прямой регрессией M4;
- структуру сохраняемых артефактов;
- критерии приемки;
- места для ссылок на дашборды и комментариев к результатам.

Математическое обоснование приведено в [THEORY.md](THEORY.md). Общая постановка задачи приведена в [00_problem_statement.md](../../research/00_problem_statement.md).

M5 отвечает на вопрос:

> Улучшает ли раздельное прогнозирование вероятности неблагоприятного события и величины убытка при условии его наступления итоговую оценку риска и экономическую ценность вмешательства относительно прямой модели M4?

Итоговый прогноз M5 имеет единицы базисных пунктов:

\[
\widehat S_i^{M5}
=
\widehat p_i\widehat\mu_i,
\]

где

\[
\widehat p_i \approx \Pr(S_i>0\mid x_i),
\qquad
\widehat\mu_i \approx \mathbb E[S_i\mid S_i>0,x_i].
\]

## 2. Место в иерархии моделей

| Модель | Выход модели | Основное назначение |
|---|---|---|
| `M0_single_scale` | вероятность неблагоприятного события | одномасштабная точка отсчета |
| `M1_local_multiscale` | вероятность неблагоприятного события | проверка локального многомасштабного описания |
| `M2_cross_market_rg_no_j` | вероятность неблагоприятного события | проверка добавочной информации соседнего рынка |
| `M3_cross_market_rg_with_j` | вероятность неблагоприятного события | проверка явного межрыночного взаимодействия |
| `M4_direct_value_regression` | ожидаемая амплитуда убытка | прямая экономическая оценка для P2 |
| `M5_hurdle_economic_model` | вероятность, условная амплитуда и их произведение | двухчастная экономическая оценка для P3 |

M5 оценивает тот же статистический объект, что и M4:

\[
\mathbb E[S_i\mid x_i].
\]

Различается способ оценки:

```text
M4: X -> E[S | X]
M5: X -> P(S > 0 | X) и E[S | S > 0, X] -> произведение
```

M5 не считается автоматически лучше M4. Ее преимущество должно быть подтверждено на одинаковых данных, временных частях, признаках и экономических параметрах.

## 3. Фактический статус реализации

На момент подготовки документа M5 в коде отсутствует.

Текущие точки входа репозитория:

- [`adverse_selection_oos.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/main/src/revolut_app/real_market/experiments/adverse_selection_oos.py) - классификационное вневыборочное сравнение;
- [`adverse_selection_capture.py`](https://github.com/vasile8egor/ReDataX_pet_project/blob/main/src/revolut_app/real_market/experiments/adverse_selection_capture.py) - диагностическая оценка захвата наблюдаемого убытка.

Текущий классификационный контур содержит:

```text
m0_single_scale
m1_multiscale
m2_rg_flow
```

Текущий контур экономического захвата содержит только:

```text
m0_single_scale
m1_multiscale
```

В репозитории пока отсутствуют:

- единый версионируемый контракт целей `adverse_event` и `adverse_amplitude_bps`;
- модель вероятности M5 как отдельный сохраняемый компонент;
- модель условной амплитуды M5;
- обучение второй компоненты только на `S > 0`;
- совместный прогноз `p_hat * mu_hat`;
- раздельная калибровка `p_hat`, `mu_hat` и их произведения;
- политика P3 с ограничением по доле номинала;
- сравнение P3 с P2 на одной маске;
- отрицательные контроли двухчастного разложения;
- пакет воспроизводимых артефактов M5;
- дашборды M5.

Статус модели:

```text
planned
```

Любые результаты существующих классификаторов нельзя публиковать под именем M5.

## 4. Граница между текущим кодом и целевой спецификацией

| Компонент | Текущий код | Целевая M5 |
|---|---|---|
| тип задачи | бинарная классификация | классификация + условная положительная регрессия |
| единица наблюдения | агрегированная сделка | состояние рынка с шагом 10 секунд |
| стандартные горизонты | 1 и 5 секунд | основной горизонт 600 секунд |
| бинарная цель | `markout_bps > 0` | `S > 0`, эквивалентно `markout_bps > 0` |
| непрерывная цель | используется только постфактум в метриках | `S = max(markout_bps, 0)` |
| выход модели | вероятность | `p_hat`, `mu_hat`, `p_hat * mu_hat` |
| положительная подвыборка | не используется для отдельной модели | обязательна для компонента амплитуды |
| отбор наблюдений | верхняя доля строк | бюджет по доле номинала |
| порог окупаемости | не применяется | 4 б.п. в конфигурации 1.0 |
| политика | диагностический захват | P3 |
| калибровка | отсутствует | обязательна для трех выходов |
| сравнение с M4 | отсутствует | обязательное парное сравнение |

До реализации регулярной сетки решений допускается диагностический вариант на уровне агрегированных сделок:

```text
m5_trade_level_prototype
```

Он должен иметь отдельный статус и не заменяет основной эксперимент версии 1.0.

## 5. Предварительные условия

Перед реализацией M5 должны быть выполнены следующие условия:

- [ ] зафиксирована единая формула знакового маркаута для M0-M5;
- [ ] зафиксирован основной горизонт `600` секунд;
- [ ] зафиксирована длина будущего окна цены или VWAP;
- [ ] реализована сетка решений с шагом `10` секунд;
- [ ] исключено использование будущей информации при построении признаков;
- [ ] реализовано временное разбиение с защитным промежутком;
- [ ] определена последняя принятая основа признаков M0-M3;
- [ ] M4 и M5 используют одну основу признаков;
- [ ] M4 и M5 оцениваются на одной маске наблюдений;
- [ ] определены единицы номинала и базисных пунктов;
- [ ] зафиксированы параметры экономики вмешательства;
- [ ] реализован бюджет по доле номинала, а не по числу строк;
- [ ] итоговый тест не использован для выбора моделей, калибраторов и порогов;
- [ ] положительная подвыборка достаточно велика для временной проверки компонента амплитуды.

Если условия не выполнены, результат M5 считается диагностическим.

## 6. Рекомендуемая структура кода

Целевая реализация может быть разделена следующим образом:

```text
src/revolut_app/real_market/
├── datasets/
│   └── adverse_selection_dataset.py
├── targets/
│   ├── markout.py
│   ├── adverse_event.py
│   └── adverse_amplitude.py
├── features/
│   └── feature_backbones.py
├── models/
│   ├── classification_baselines.py
│   ├── positive_regression_baselines.py
│   ├── m4_direct_value_regression.py
│   ├── m5_occurrence.py
│   ├── m5_severity.py
│   ├── m5_hurdle.py
│   └── calibration.py
├── policies/
│   └── p3_hurdle_economic.py
├── evaluation/
│   ├── classification_metrics.py
│   ├── regression_metrics.py
│   ├── hurdle_metrics.py
│   ├── economic_metrics.py
│   ├── temporal_validation.py
│   └── bootstrap.py
└── experiments/
    └── adverse_selection_hurdle_oos.py
```

Эти пути являются предлагаемой архитектурой. Они не описывают уже существующие модули.

Общие функции расчета целей, временных частей, признаков и экономики должны использоваться M4 и M5 совместно.

## 7. Связанные документы

- [THEORY.md](THEORY.md) - математическая постановка M5;
- [M4/THEORY.md](../M4_direct_value_regression/THEORY.md) - прямая оценка ожидаемой амплитуды;
- [M4/README.md](../M4_direct_value_regression/README.md) - прикладная спецификация M4;
- [00_problem_statement.md](../../research/00_problem_statement.md) - общая постановка задачи;
- [feature_engineering.md](../../ml/feature_engineering.md) - построение признаков;
- [targets.md](../../ml/targets.md) - формулы целей;
- [temporal_validation.md](../../ml/temporal_validation.md) - временная проверка;
- [calibration.md](../../ml/calibration.md) - калибровка прогнозов;
- [model_selection.md](../../ml/model_selection.md) - выбор алгоритмов;
- [leakage_checklist.md](../../ml/leakage_checklist.md) - контроль утечек;
- [P3_hurdle_economic.md](../../decision_policies/P3_hurdle_economic.md) - политика P3;
- [P2_direct_economic.md](../../decision_policies/P2_direct_economic.md) - политика сравнения P2;
- [P4_oracle.md](../../decision_policies/P4_oracle.md) - недостижимый верхний ориентир;
- [unit_economics.md](../../decision_policies/unit_economics.md) - экономика вмешательства;
- [metric_dictionary.md](../../analytics/metric_dictionary.md) - словарь метрик;
- [MODEL_REGISTRY.md](../MODEL_REGISTRY.md) - реестр моделей.

## 8. Источник данных

Основной источник реальных рыночных данных:

```text
raw.fact_real_market_agg_trades
```

Основные рынки:

```text
BTCUSDT
ETHUSDT
```

Минимально необходимые поля исходного слоя:

| Поле | Назначение |
|---|---|
| `event_timestamp` | построение окон и временной сетки |
| `aggregate_trade_id` | устойчивый порядок событий с одинаковым временем |
| `symbol` | идентификатор рынка |
| `price` | текущая и будущая цена |
| `base_quantity` | расчет будущего VWAP |
| `quote_quantity` | номинал и признаки потока |
| `aggressor_side` | знак условной экспозиции |
| `trade_date` | временные части и дневные метрики |

Если M5 использует M2 или M3 как основу признаков, дополнительно требуется причинно синхронизированное состояние соседнего рынка.

## 9. Единица наблюдения

Целевая версия использует регулярную сетку решений:

```text
t_i = t_0 + i * decision_step_seconds
```

Основная конфигурация:

```text
decision_step_seconds = 10
prediction_horizon_seconds = 600
target_window_seconds = <зафиксировать>
```

Для каждого момента `decision_ts` формируется одна строка:

```text
decision_ts
trade_date
target_symbol
reference_symbol
notional_usdt
feature_backbone
features
markout_bps
adverse_event
adverse_amplitude_bps
target_available_ts
split_name
market_regime
```

Поле `target_available_ts` должно удовлетворять:

```text
target_available_ts >= decision_ts + prediction_horizon_seconds
```

Оно используется для проверки пересечений между обучением и последующими временными частями.

## 10. Контракт целевых переменных

Пусть `markout_bps` - знаковый будущий маркаут, положительный при движении против условной экспозиции платформы.

Бинарная цель:

```text
adverse_event = 1 if markout_bps > 0 else 0
```

Непрерывная цель:

```text
adverse_amplitude_bps = max(markout_bps, 0.0)
```

Формально:

\[
Y_i=\mathbf 1\{M_i>0\},
\qquad
S_i=\max(M_i,0).
\]

Обязательные инварианты:

```text
adverse_event in {0, 1}
adverse_amplitude_bps >= 0
adverse_event == 0  => adverse_amplitude_bps == 0
adverse_event == 1  => adverse_amplitude_bps > 0
```

Последний инвариант требует заранее определенного правила обработки нулевых и численно малых маркаутов. Рекомендуется использовать единый допуск `target_epsilon_bps`, зафиксированный в `targets.md`.

Пример контракта:

```yaml
target_schema_version: adverse_selection_v1
markout_direction: against_platform_exposure
adverse_event_rule: markout_bps > target_epsilon_bps
adverse_amplitude_rule: max(markout_bps, 0.0)
target_epsilon_bps: 0.0
prediction_horizon_seconds: 600
target_window_seconds: <зафиксировать>
```

## 11. Выходы модели

M5 должна возвращать три значения для каждого наблюдения:

```text
adverse_probability
conditional_severity_bps
expected_adverse_amplitude_bps
```

Связь между ними:

```text
expected_adverse_amplitude_bps
    = adverse_probability * conditional_severity_bps
```

Ограничения области значений:

```text
0.0 <= adverse_probability <= 1.0
conditional_severity_bps > 0.0
expected_adverse_amplitude_bps >= 0.0
```

Рекомендуемый интерфейс:

```python
@dataclass(frozen=True)
class HurdlePrediction:
    adverse_probability: np.ndarray
    conditional_severity_bps: np.ndarray
    expected_adverse_amplitude_bps: np.ndarray
```

Внутри M5 запрещено заменять вероятность жесткой меткой:

```text
(adverse_probability > 0.5) * conditional_severity_bps
```

Пороговые правила относятся к политике P3, а не к статистической модели.

## 12. Основа признаков

M5 использует один из ранее проверенных наборов:

```text
m0_single_scale
m1_local_multiscale
m2_cross_market_rg_no_j
m3_cross_market_rg_with_j
```

Рекомендуемый интерфейс:

```text
--feature-backbone m0|m1|m2|m3
```

Основной вариант выбирается только на обучающей и проверочной частях.

Для основного сравнения M4 и M5 должны использовать:

```text
same feature_backbone
same feature_schema_version
same observation mask
same train/validation/test manifest
same target schema
same economic assumptions
```

По умолчанию обе компоненты M5 получают один набор признаков:

```text
occurrence_features == severity_features
```

Разные признаки допускаются только как зарегистрированное разложение:

```text
m5_shared_backbone
m5_separate_backbones_ablation
```

## 13. Общая маска наблюдений

M4 и M5 должны сравниваться на одной полной маске:

```text
valid_target
AND valid_notional
AND valid_features_for_all_compared_models
AND valid_time_split
AND valid_market_state
```

После применения полной маски компонент амплитуды получает дополнительную обучающую маску:

```text
severity_train_mask = common_train_mask AND adverse_event == 1
```

Нельзя использовать будущую цель для маршрутизации наблюдения при применении модели. Условие `adverse_event == 1` разрешено только при обучении и оценке компонента амплитуды на уже размеченных данных.

В артефактах сохраняются:

```text
rows_before_mask
rows_after_common_mask
rows_train_occurrence
rows_train_severity
positive_rate_train
positive_rate_validation
positive_rate_test
removed_missing_target
removed_missing_features
removed_stale_reference_market
removed_split_embargo
```

## 14. Простые ориентиры

До обучения основной M5 необходимо рассчитать ориентиры, использующие только обучающую часть.

### 14.1. Постоянная вероятность

```text
p_hat = mean(adverse_event on train)
```

Идентификатор:

```text
m5_occurrence_prior_baseline
```

### 14.2. Постоянная условная амплитуда

```text
mu_hat = mean(adverse_amplitude_bps on train where adverse_event == 1)
```

Идентификатор:

```text
m5_severity_mean_positive_baseline
```

### 14.3. Полный постоянный ориентир

```text
s_hat = p_train * mu_positive_train
```

Идентификатор:

```text
m5_hurdle_constant_baseline
```

### 14.4. Однокомпонентные ориентиры

Только вероятность:

```text
s_hat = p_hat_model * mu_positive_train
```

Только амплитуда:

```text
s_hat = p_train * mu_hat_model
```

Эти варианты позволяют проверить, дает ли добавочную ценность каждая часть модели.

### 14.5. Прямая регрессия M4

M4 является обязательной основной моделью сравнения:

```text
m4_direct_value_regression
```

Без парного сравнения с M4 вывод о преимуществе двухчастного разложения не формулируется.

## 15. Компонент вероятности

Компонент вероятности оценивает:

\[
\Pr(S_i>0\mid x_i).
\]

### 15.1. Линейная точка отсчета

Рекомендуемая модель:

```text
LogisticRegression
```

или потоковый вариант:

```text
SGDClassifier(loss="log_loss")
```

Идентификатор:

```text
m5_occurrence_logistic
```

Преимущества:

- интерпретируемый линейный ориентир;
- ограниченный расход памяти;
- совместимость со стандартизацией и потоковым обучением;
- прогноз вероятности без дополнительного преобразования.

### 15.2. Нелинейный кандидат

Рекомендуемый вариант:

```text
HistGradientBoostingClassifier
```

Идентификатор:

```text
m5_occurrence_hist_gb
```

Он проверяет наличие нелинейного сигнала, но не заменяет линейную точку отсчета.

### 15.3. Требования к вероятности

Обязательные проверки:

```text
0 <= p_hat <= 1
non_finite_probabilities == 0
probability_calibration_report exists
```

Основные метрики:

| Метрика | Назначение |
|---|---|
| `average_precision` | качество ранжирования редкого события |
| `roc_auc` | дополнительная ранговая диагностика |
| `log_loss` | качество вероятностного прогноза |
| `brier_score` | среднеквадратичная ошибка вероятности |
| `calibration_intercept` | систематический сдвиг уровня риска |
| `calibration_slope` | чрезмерная или недостаточная уверенность |
| `expected_calibration_error` | агрегированная ошибка калибровки |

Точность при пороге 0.5 не является основной метрикой.

## 16. Компонент условной амплитуды

Компонент амплитуды оценивает:

\[
\mathbb E[S_i\mid S_i>0,x_i].
\]

Она обучается только на строках:

```text
adverse_event == 1
```

### 16.1. Гамма-регрессия с логарифмической связью

Рекомендуемая основная линейная кандидатура:

```text
GammaRegressor
```

Идентификатор:

```text
m5_severity_gamma_glm
```

Преимущества:

- положительный прогноз;
- естественная работа с правосторонне асимметричной положительной целью;
- интерпретируемое мультипликативное влияние признаков.

Ограничение:

- модель не допускает нулевые цели, что соответствует положительной подвыборке, но требует строгой проверки контракта.

### 16.2. Регрессия на логарифме положительной цели

Вариант:

```text
y_log = log1p(adverse_amplitude_bps)
```

Идентификатор:

```text
m5_severity_log_target
```

Обратное преобразование без поправки оценивает не условное среднее исходной величины. Поэтому должны сравниваться:

```text
naive_inverse
smearing_correction
validation_calibration
```

### 16.3. Нелинейный кандидат

Рекомендуемый вариант:

```text
HistGradientBoostingRegressor
```

Идентификаторы:

```text
m5_severity_hist_gb_squared
m5_severity_hist_gb_poisson
```

Положительность выхода обеспечивается выбранной функцией потерь или явным ограничением, зарегистрированным в конфигурации.

### 16.4. Метрики условной амплитуды

Метрики рассчитываются только на `adverse_event == 1`:

| Метрика | Назначение |
|---|---|
| `mae_positive_bps` | средняя абсолютная ошибка положительной части |
| `rmse_positive_bps` | чувствительность к ошибкам в хвосте |
| `mean_prediction_positive_bps` | средний условный прогноз |
| `mean_target_positive_bps` | средняя реализованная амплитуда |
| `mean_bias_positive_bps` | систематическое смещение |
| `gamma_deviance` | соответствие гамма-модели |
| `spearman_positive` | ранжирование амплитуды внутри положительной части |
| `tail_mae_positive_bps` | ошибка в заранее заданном верхнем хвосте |

## 17. Рекомендуемая начальная конфигурация

Начальная исследовательская конфигурация:

```yaml
model_name: m5_hurdle_economic_model
feature_backbone: <selected_on_validation>
target_schema_version: adverse_selection_v1
prediction_horizon_seconds: 600
decision_step_seconds: 10

occurrence:
  model_name: m5_occurrence_logistic
  penalty: l2
  c_grid: [0.01, 0.1, 1.0, 10.0]
  class_weight: null
  standardize_features: true
  calibrator: sigmoid

severity:
  model_name: m5_severity_gamma_glm
  link: log
  alpha_grid: [1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2]
  max_iter: 1000
  standardize_features: true
  calibrator: multiplicative

combined:
  formula: calibrated_probability * calibrated_severity_bps
  calibrator: identity_or_validation_selected
  prediction_floor_bps: 0.0

policy:
  policy_name: P3_hurdle_economic
  budget_notional_fraction: 0.10
  internalization_rate: 0.25
  mitigation_efficiency: 0.50
  action_cost_bps: 0.50
  break_even_markout_bps: 4.00
```

Это отправная точка, а не уже подтвержденная конфигурация.

## 18. Ограничения по памяти

При шаге решений 10 секунд основной набор должен храниться на уровне решений, а не на уровне всех исходных сделок.

Рекомендуемый порядок:

1. читать сделки по одному дню и рынку;
2. строить причинные признаки;
3. материализовать строки решений;
4. рассчитывать обе цели;
5. сохранять компактный набор в ClickHouse или Parquet;
6. обучать компонент вероятности на полной обучающей части;
7. обучать компонент амплитуды на положительной подвыборке;
8. рассчитывать прогнозы пакетами;
9. сохранять только необходимые вневыборочные выходы.

Не рекомендуется одновременно хранить в памяти:

- полные сделки нескольких месяцев;
- все варианты признаков M0-M3;
- все матрицы подбора параметров;
- полную и положительную копии одинаковой матрицы признаков.

Для положительной подвыборки предпочтительно хранить индексы или маску, а не полную копию матрицы.

## 19. Стандартизация

Для линейных компонентов параметры стандартизации оцениваются только на обучении:

```text
occurrence_scaler.fit(X_train)
severity_scaler.fit(X_train[adverse_event_train == 1])
```

Это два разных преобразователя, поскольку распределение признаков в полной и положительной выборках может различаться.

Далее:

```text
occurrence_scaler.transform(X_validation)
occurrence_scaler.transform(X_test)

severity_scaler.transform(X_validation)
severity_scaler.transform(X_test)
```

При применении модели компонент амплитуды получает все строки. Она не должна использовать истинное значение `adverse_event` для выбора строк во время прогноза.

Для древовидных моделей стандартизация обычно не требуется, но маски и правила пропусков должны совпадать с линейными вариантами.

## 20. Обработка пропусков

Основной вариант:

```text
удалить строку, если отсутствует обязательный причинный признак
```

Заполнение допускается только при выполнении условий:

- правило имеет экономический смысл;
- параметры рассчитаны на обучении;
- добавлен индикатор пропуска;
- результат сравнен с удалением строк;
- не используется будущее значение.

Одна общая маска применяется до разделения на компоненты.

Для M2/M3 устаревшее состояние соседнего рынка нельзя заменять ближайшим будущим значением.

## 21. Обучение

Общая последовательность:

```text
1. Загрузить манифест временных частей.
2. Построить или прочитать таблицу решений.
3. Применить общую маску допустимых строк.
4. Рассчитать статистики целей только на train.
5. Обучить постоянные ориентиры.
6. Обучить кандидаты компонента вероятности на полном train.
7. Обучить кандидаты компонента амплитуды на train с S > 0.
8. Получить прогнозы обеих компонент на validation.
9. Выбрать параметры и методы калибровки только по validation.
10. Рассчитать и проверить произведение p_hat * mu_hat.
11. Сравнить M5 с M4 на validation.
12. Зафиксировать всю спецификацию.
13. При разрешенной схеме переобучить компоненты на train + validation.
14. Один раз рассчитать прогнозы на final test.
15. Запустить P3, P2, P0 и P4 на общей тестовой маске.
16. Сохранить прогнозные, экономические и диагностические артефакты.
```

Итоговый тест не используется для:

- выбора основы признаков;
- выбора алгоритма вероятности;
- выбора алгоритма амплитуды;
- выбора регуляризации;
- выбора калибраторов;
- выбора порогов P3;
- выбора бюджета;
- выбора параметров экономики;
- выбора между M4 и M5.

## 22. Временная проверка

Основная схема:

```text
train -> embargo -> validation -> embargo -> final_test
```

Минимальная длина защитного промежутка:

```text
embargo_seconds >= prediction_horizon_seconds + target_window_seconds
```

Рекомендуется расширяющееся окно:

```text
fold 1: train_1 -> validation_1
fold 2: train_1 + train_2 -> validation_2
fold 3: train_1 + train_2 + train_3 -> validation_3
```

Для каждого временного сгиба публикуются:

```text
rows_total
rows_positive
positive_rate
mean_positive_amplitude_bps
p90_positive_amplitude_bps
p99_positive_amplitude_bps
```

Если отдельный сгиб содержит недостаточно положительных наблюдений, он не должен молча исключаться. Необходимо либо объединить более крупные последовательные периоды, либо изменить частоту оценки до открытия итогового теста.

Обязательные поля манифеста:

```text
split_id
train_start
train_end
validation_start
validation_end
test_start
test_end
embargo_seconds
prediction_horizon_seconds
target_window_seconds
```

## 23. Настройка параметров

Параметры двух компонент нельзя выбирать независимо только по их локальным метрикам. Выбор должен учитывать итоговый прогноз и политику P3.

Рекомендуемый порядок:

1. исключить технически некорректные конфигурации;
2. проверить вероятность по `log_loss`, `Brier` и калибровке;
3. проверить амплитуду по девиации, смещению среднего и хвосту;
4. проверить произведение по ошибке и калибровке на полной выборке;
5. сравнить итоговую экономическую ценность P3 с P2;
6. выбрать наиболее простую конфигурацию, удовлетворяющую всем ограничениям.

Рекомендуемая таблица подбора:

| occurrence_model | severity_model | backbone | AP | Brier | MAE+ | Combined MAE | Combined bias | P3 V/$1M | P3-P2 V/$1M |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `[заполнить]` | `[заполнить]` | `[заполнить]` | | | | | | | |

Нельзя выбирать M5 только по средней точности компонента вероятности.

## 24. Калибровка

M5 требует трех уровней проверки калибровки.

### 24.1. Калибровка вероятности

Для групп по `adverse_probability` сохраняются:

```text
probability_bin
observations
mean_predicted_probability
realized_positive_rate
mean_notional_usdt
```

Рекомендуемые методы:

```text
identity
sigmoid
isotonic_time_validated
```

Калибратор обучается только на проверочной части или на внутренних внефолдовых прогнозах обучения.

### 24.2. Калибровка условной амплитуды

На положительной части для групп по `conditional_severity_bps` сохраняются:

```text
severity_bin
positive_observations
mean_predicted_severity_bps
mean_realized_severity_bps
median_realized_severity_bps
p90_realized_severity_bps
```

Рекомендуемые варианты:

```text
identity
multiplicative_mean_ratio
linear_positive
isotonic_time_validated
```

### 24.3. Калибровка произведения

На полной выборке для групп по `expected_adverse_amplitude_bps` сохраняются:

```text
expected_loss_bin
observations
mean_predicted_expected_bps
mean_realized_adverse_amplitude_bps
realized_positive_rate
mean_realized_positive_severity_bps
notional_usdt
```

Даже если обе компоненты приемлемо откалиброваны отдельно, произведение необходимо проверить повторно.

Допускаются два режима:

```text
component_calibration_only
component_plus_combined_calibration
```

Выбор режима производится до открытия итогового теста.

## 25. Итоговые прогнозные метрики

На полной выборке рассчитываются:

| Метрика | Назначение |
|---|---|
| `mae_bps` | средняя абсолютная ошибка произведения |
| `rmse_bps` | чувствительность к крупным ошибкам |
| `mean_prediction_bps` | средний прогноз M5 |
| `mean_target_bps` | средняя реализованная амплитуда |
| `mean_bias_bps` | систематический сдвиг |
| `tweedie_deviance` | сопоставимость с M4 на неотрицательной цели |
| `spearman` | качество ранжирования ожидаемого убытка |
| `top_10pct_lift` | концентрация амплитуды в верхнем дециле |
| `top_10pct_capture` | доля всей амплитуды в верхнем дециле |
| `non_finite_predictions` | техническая корректность |
| `negative_predictions` | нарушение области значений |

Метрики публикуются отдельно для:

```text
BTCUSDT
ETHUSDT
all_symbols
calm
elevated
stress
```

Результаты M5 должны быть представлены рядом с M4 на одной маске.

## 26. Политика P3

Для каждого наблюдения рассчитывается ожидаемая валовая защищенная стоимость:

\[
\widehat G_i
=
N_i\rho_{int}\rho_{mit}
\frac{\widehat p_i\widehat\mu_i}{10^4}.
\]

Стоимость действия:

\[
K_i=N_i\frac{c_{act}}{10^4}.
\]

Ожидаемая чистая стоимость:

\[
\widehat V_i
=
\widehat G_i-K_i.
\]

Для конфигурации версии 1.0:

```text
internalization_rate = 0.25
mitigation_efficiency = 0.50
action_cost_bps = 0.50
break_even_markout_bps = 4.00
budget_notional_fraction = 0.10
```

Основной режим P3:

```text
1. Рассчитать p_hat, mu_hat и expected_bps = p_hat * mu_hat.
2. Рассчитать ожидаемую чистую стоимость.
3. Исключить строки с expected_net_value <= 0.
4. Рассчитать expected_net_value_per_notional.
5. Отсортировать допустимые строки по убыванию этого показателя.
6. Выбирать действия до достижения бюджета по номиналу.
```

При постоянных параметрах экономики ранжирование по `expected_net_value_per_notional` эквивалентно ранжированию по `expected_bps` после применения порога безубыточности.

Если номиналы сильно различаются, простой жадный отбор может не дать точного решения дискретной задачи. Реализация должна зафиксировать один из режимов:

```text
greedy_value_density
exact_knapsack_for_daily_batch
fractional_last_observation_for_diagnostic_only
```

Дробное действие над частью наблюдения допустимо только как аналитический ориентир и не должно смешиваться с основной бинарной политикой.

## 27. Дополнительный двухпороговый режим

Как анализ чувствительности допускается правило:

```text
adverse_probability >= probability_threshold
AND conditional_severity_bps >= severity_threshold_bps
```

Пороги выбираются только на проверочной части.

Идентификатор режима:

```text
p3_dual_threshold_ablation
```

Этот вариант не является основной политикой, поскольку отдельные пороги могут исключить экономически выгодные сочетания умеренной вероятности и высокой амплитуды или высокой вероятности и умеренной амплитуды.

## 28. Бюджет по номиналу

Политика должна удовлетворять:

\[
\frac{\sum_i a_iN_i}{\sum_iN_i}\le B.
\]

Основное значение:

```text
B = 0.10
```

Обязательные проверки:

```text
selected_notional_fraction <= budget_notional_fraction + tolerance
selected_trade_fraction is reported but not used as budget
selected_notional_usdt is finite and non-negative
```

Текущий скрипт `adverse_selection_capture.py` выбирает верхнюю долю строк. Такой режим может использоваться только как диагностический ориентир и не считается реализацией P3.

## 29. Экономические метрики

Обязательный набор:

| Метрика | Назначение |
|---|---|
| `selected_notional_fraction` | использованная доля бюджета |
| `captured_exposure_rate` | доля фактического потенциального убытка в выбранных наблюдениях |
| `risk_concentration` | захват риска, деленный на долю вовлеченного номинала |
| `gross_protected_value_usdt` | фактически защищенная валовая стоимость по сценарию |
| `action_cost_usdt` | стоимость вмешательств |
| `net_protected_value_usdt` | валовая стоимость минус затраты |
| `net_value_per_million_usdt` | чистая стоимость на 1 млн оборота |
| `benefit_cost_ratio` | отношение валовой выгоды к стоимости |
| `break_even_action_cost_bps` | максимальная стоимость действия при нулевой чистой ценности |
| `cost_headroom_bps` | запас до безубыточности |
| `oracle_efficiency` | доля достигнутой ценности относительно P4 |

Дополнительно публикуются:

```text
eligible_notional_fraction
budget_utilization
selected_observations
positive_selected_fraction
mean_selected_realized_amplitude_bps
p90_selected_realized_amplitude_bps
```

Экономические значения являются сценарными оценками, а не реальной прибылью конкретной организации.

## 30. Сравнение политик

На одной тестовой маске сравниваются:

| Политика | Источник решения |
|---|---|
| P0 | отсутствие действий |
| P1 | вероятность принятой классификационной модели M0-M3 |
| P2 | прямой прогноз M4 |
| P3 | произведение вероятности и условной амплитуды M5 |
| P4 | реализованная будущая амплитуда, доступная только постфактум |

Основные парные разности:

```text
P3 - P2
P3 - P1
P3 - P0
P4 - P3
```

Для вывода о преимуществе M5 главной является разность:

```text
P3 - P2
```

Положительная разность P3-P1 не доказывает преимущество двухчастного разложения, поскольку P1 решает другую статистическую задачу.

## 31. Разложения модели

Обязательные варианты:

| Идентификатор | Формула | Проверяемый вопрос |
|---|---|---|
| `m5_constant` | `p_const * mu_const` | превосходит ли M5 постоянный риск |
| `m5_probability_only` | `p_model * mu_const` | дает ли сигнал вероятность |
| `m5_severity_only` | `p_const * mu_model` | дает ли сигнал амплитуда |
| `m5_full` | `p_model * mu_model` | полезно ли совместное разложение |
| `m4_direct` | прямой прогноз | лучше ли M5 прямой оценки |

Все варианты используют одинаковую основу признаков и временные части.

## 32. Отрицательные контроли

Необходимо реализовать минимум три контроля.

### 32.1. Перемешивание амплитуды внутри дня

```text
p_model * shuffled(mu_model within trade_date)
```

Проверяет, важна ли согласованность компонент на уровне наблюдения.

### 32.2. Временной сдвиг амплитуды

```text
p_model(t) * mu_model(t - lag)
```

Сдвиг выполняется причинно и не должен использовать будущее.

### 32.3. Замена одной компоненты постоянной

```text
p_model * mu_const
p_const * mu_model
```

Если отрицательные контроли не ухудшают результат, интерпретация произведения как совместной оценки риска не подтверждается.

## 33. Устойчивость и неопределенность

Метрики рассчитываются по торговым дням. Для разностей M5-M4 и P3-P2 применяется парная блочная повторная выборка по дням.

Обязательные поля:

```text
days
mean_delta
ci_025
ci_975
positive_day_fraction
median_delta
worst_day_delta
best_day_delta
```

Основные сравниваемые показатели:

```text
combined_mae_bps
mean_bias_bps
net_value_per_million_usdt
captured_exposure_rate
benefit_cost_ratio
oracle_efficiency
```

Дополнительно проверяется устойчивость по режимам:

```text
calm
elevated
stress
```

Если преимущество определяется одним днем или только одним режимом, M5 не получает основной статус `accepted`.

## 34. Предлагаемый интерфейс запуска

Целевая команда:

```bash
python -m revolut_app.real_market.experiments.adverse_selection_hurdle_oos \
  --symbols BTCUSDT ETHUSDT \
  --feature-backbone m1 \
  --prediction-horizon-seconds 600 \
  --target-window-seconds <VALUE> \
  --decision-step-seconds 10 \
  --train-start <YYYY-MM-DD> \
  --train-end <YYYY-MM-DD> \
  --validation-start <YYYY-MM-DD> \
  --validation-end <YYYY-MM-DD> \
  --test-start <YYYY-MM-DD> \
  --test-end <YYYY-MM-DD> \
  --embargo-seconds <VALUE> \
  --occurrence-model logistic \
  --severity-model gamma \
  --probability-calibration sigmoid \
  --severity-calibration multiplicative \
  --combined-calibration identity \
  --budget-notional-fraction 0.10 \
  --internalization-rate 0.25 \
  --mitigation-efficiency 0.50 \
  --action-cost-bps 0.50 \
  --bootstrap-samples 5000 \
  --output-dir artifacts/models/M5/<RUN_ID>
```

Эта команда является целевым интерфейсом. До появления соответствующего модуля она не считается рабочей.

## 35. Конфигурация запуска

Каждый запуск должен иметь отдельный файл:

```text
config.yaml
```

Минимальное содержимое:

```yaml
run_id: <RUN_ID>
model_id: M5
model_name: m5_hurdle_economic_model
implementation_status: experimental
symbols: [BTCUSDT, ETHUSDT]
feature_backbone: M1
feature_schema_version: <VERSION>
target_schema_version: adverse_selection_v1
prediction_horizon_seconds: 600
target_window_seconds: <VALUE>
decision_step_seconds: 10
embargo_seconds: <VALUE>

occurrence_model:
  name: logistic
  parameters: {}
  calibration: sigmoid

severity_model:
  name: gamma
  parameters: {}
  calibration: multiplicative

combined_prediction:
  formula: p_hat * mu_hat
  calibration: identity

policy:
  name: P3_hurdle_economic
  budget_notional_fraction: 0.10
  internalization_rate: 0.25
  mitigation_efficiency: 0.50
  action_cost_bps: 0.50
  break_even_markout_bps: 4.00

splits:
  train_start: <DATE>
  train_end: <DATE>
  validation_start: <DATE>
  validation_end: <DATE>
  test_start: <DATE>
  test_end: <DATE>
```

## 36. Структура артефактов

Рекомендуемая структура:

```text
artifacts/models/M5/<RUN_ID>/
├── config.yaml
├── manifest.json
├── data_summary.json
├── feature_schema.json
├── target_schema.json
├── split_manifest.json
├── occurrence/
│   ├── model.bin
│   ├── scaler.bin
│   ├── calibrator.bin
│   └── metrics.json
├── severity/
│   ├── model.bin
│   ├── scaler.bin
│   ├── calibrator.bin
│   └── metrics.json
├── combined/
│   ├── calibrator.bin
│   ├── metrics.json
│   └── calibration_bins.parquet
├── predictions.parquet
├── daily_metrics.parquet
├── policy_p3_metrics.json
├── policy_comparison.json
├── bootstrap.json
├── ablations.json
├── negative_controls.json
├── model_card.json
└── README.md
```

Если калибратор не используется, в манифесте сохраняется:

```text
calibration_method: identity
```

Пустой или отсутствующий файл не должен оставлять способ калибровки неявным.

## 37. Схема таблицы прогнозов

Рекомендуемые поля `predictions.parquet`:

```text
run_id
model_id
symbol
decision_ts
trade_date
split_name
market_regime
notional_usdt
markout_bps
adverse_event
adverse_amplitude_bps
occurrence_probability_raw
occurrence_probability_calibrated
severity_bps_raw
severity_bps_calibrated
expected_amplitude_bps_raw
expected_amplitude_bps_calibrated
expected_gross_value_usdt
expected_action_cost_usdt
expected_net_value_usdt
expected_net_value_per_notional
eligible_for_action
selected_by_p3
selected_by_p2
selected_by_p4
feature_backbone
feature_schema_version
target_schema_version
occurrence_model_version
severity_model_version
```

Для итогового теста все прогнозные поля должны быть рассчитаны без использования реализованной цели.

## 38. Схема метрик компонента вероятности

Рекомендуемое содержимое `occurrence/metrics.json`:

```json
{
  "observations": 0,
  "positives": 0,
  "positive_rate": 0.0,
  "average_precision": 0.0,
  "roc_auc": 0.0,
  "log_loss": 0.0,
  "brier_score": 0.0,
  "calibration_intercept": 0.0,
  "calibration_slope": 0.0,
  "expected_calibration_error": 0.0,
  "non_finite_predictions": 0
}
```

## 39. Схема метрик компонента амплитуды

Рекомендуемое содержимое `severity/metrics.json`:

```json
{
  "positive_observations": 0,
  "mae_positive_bps": 0.0,
  "rmse_positive_bps": 0.0,
  "mean_prediction_positive_bps": 0.0,
  "mean_target_positive_bps": 0.0,
  "mean_bias_positive_bps": 0.0,
  "gamma_deviance": 0.0,
  "spearman_positive": 0.0,
  "tail_mae_positive_bps": 0.0,
  "non_finite_predictions": 0,
  "non_positive_predictions": 0
}
```

## 40. Схема метрик объединенного прогноза

Рекомендуемое содержимое `combined/metrics.json`:

```json
{
  "observations": 0,
  "mae_bps": 0.0,
  "rmse_bps": 0.0,
  "mean_prediction_bps": 0.0,
  "mean_target_bps": 0.0,
  "mean_bias_bps": 0.0,
  "tweedie_deviance": 0.0,
  "spearman": 0.0,
  "top_10pct_lift": 0.0,
  "top_10pct_capture": 0.0,
  "calibration_intercept": 0.0,
  "calibration_slope": 0.0,
  "weighted_absolute_calibration_error": 0.0,
  "non_finite_predictions": 0,
  "negative_predictions": 0
}
```

## 41. Схема экономических метрик P3

Рекомендуемое содержимое `policy_p3_metrics.json`:

```json
{
  "budget_notional_fraction": 0.10,
  "selected_notional_fraction": 0.0,
  "budget_utilization": 0.0,
  "selected_observations": 0,
  "selected_notional_usdt": 0.0,
  "total_notional_usdt": 0.0,
  "total_adverse_exposure_usdt": 0.0,
  "captured_adverse_exposure_usdt": 0.0,
  "captured_exposure_rate": 0.0,
  "risk_concentration": 0.0,
  "gross_protected_value_usdt": 0.0,
  "action_cost_usdt": 0.0,
  "net_protected_value_usdt": 0.0,
  "net_value_per_million_usdt": 0.0,
  "benefit_cost_ratio": 0.0,
  "break_even_action_cost_bps": 0.0,
  "cost_headroom_bps": 0.0,
  "oracle_efficiency": 0.0
}
```

## 42. Дашборды и места для результатов

### M5-01. Размер положительной подвыборки

**Назначение:** проверить, достаточно ли наблюдений для обучения компонента амплитуды.

**Поля:**

```text
symbol
trade_date
market_regime
observations
positive_observations
positive_rate
mean_positive_amplitude_bps
p90_positive_amplitude_bps
p99_positive_amplitude_bps
```

**Ссылка:** `[добавить ссылку на Metabase или изображение]`

**Комментарий:** `[описать устойчивость доли положительных событий и размер хвоста]`

### M5-02. Калибровка вероятности

**Назначение:** сопоставить прогнозную вероятность и реализованную частоту события.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать свободный член, наклон и проблемные интервалы вероятности]`

### M5-03. Калибровка условной амплитуды

**Назначение:** сопоставить `mu_hat` с реализованной амплитудой на `S > 0`.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать смещение среднего, качество центральной части и хвоста]`

### M5-04. Калибровка произведения

**Назначение:** проверить соответствие `p_hat * mu_hat` реализованной средней амплитуде на полной выборке.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[сравнить M5 с M4 по децилям прогнозного риска]`

### M5-05. Вклад двух компонент

**Назначение:** сравнить постоянный, вероятностный, амплитудный и полный варианты.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать, какая компонента формирует основной прирост]`

### M5-06. M4 против M5

**Назначение:** парно сравнить прямую и двухчастную оценки ожидаемого убытка.

**Показатели:**

```text
MAE
RMSE
mean_bias
Spearman
top_10pct_capture
weighted_calibration_error
```

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать, улучшает ли M5 прогноз или только интерпретацию]`

### M5-07. P2 против P3 против P4

**Назначение:** сравнить экономическую ценность политик при одинаковом бюджете.

**Показатели:**

```text
net_value_per_million_usdt
benefit_cost_ratio
captured_exposure_rate
risk_concentration
oracle_efficiency
```

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[описать прирост P3-P2 и оставшийся разрыв до P4]`

### M5-08. Кривая бюджета

**Назначение:** показать зависимость экономического результата от доли вовлеченного номинала.

**Бюджеты:**

```text
1%
2.5%
5%
10%
15%
20%
```

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать область устойчивого преимущества и точку насыщения]`

### M5-09. Дневная устойчивость P3-P2

**Назначение:** проверить, не определяется ли результат отдельными днями.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать среднюю разницу, 95%-й интервал и долю положительных дней]`

### M5-10. Результат по рыночным режимам

**Назначение:** понять, как вероятность, амплитуда и экономика меняются между `calm`, `elevated` и `stress`.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать режимы, в которых M5 превосходит M4, и источник эффекта]`

### M5-11. Отрицательные контроли

**Назначение:** проверить необходимость согласованности двух компонент.

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[показать ухудшение после перемешивания, сдвига или замены компоненты]`

### M5-12. Стоимостная чувствительность

**Назначение:** показать устойчивость P3 к изменению стоимости действия и параметров смягчения.

**Сценарии:**

```text
action_cost_bps
internalization_rate
mitigation_efficiency
budget_notional_fraction
```

**Ссылка:** `[добавить ссылку]`

**Комментарий:** `[указать область положительной чистой стоимости и запас прочности]`

## 43. Критерии приемки

M5 получает статус `accepted`, если выполнены все обязательные условия.

### 43.1. Корректность данных

- [ ] цели M0-M5 рассчитываются единым кодом;
- [ ] признаки используют только информацию, доступную к `decision_ts`;
- [ ] временные части не пересекаются через будущее окно цели;
- [ ] M4 и M5 используют одну общую маску;
- [ ] компонент амплитуды обучается только на `S > 0`;
- [ ] при применении модели истинное событие не используется для маршрутизации строк;
- [ ] бюджет ограничен долей номинала.

### 43.2. Техническая корректность

- [ ] `0 <= p_hat <= 1`;
- [ ] `mu_hat > 0`;
- [ ] `p_hat * mu_hat >= 0`;
- [ ] отсутствуют нечисловые прогнозы;
- [ ] произведение в артефакте совпадает с сохраненными компонентами;
- [ ] все версии моделей, преобразователей и калибраторов сохранены;
- [ ] запуск воспроизводится по `config.yaml` и `manifest.json`.

### 43.3. Статистическая полезность

- [ ] компонент вероятности превосходит постоянную вероятность;
- [ ] компонент амплитуды превосходит постоянное среднее положительной части;
- [ ] полная M5 превосходит однокомпонентные варианты;
- [ ] вероятность имеет приемлемую калибровку;
- [ ] условная амплитуда не имеет существенного смещения среднего;
- [ ] произведение откалибровано на полной выборке;
- [ ] отрицательные контроли ухудшают результат.

### 43.4. Экономическая полезность

- [ ] P3 дает положительную чистую защищенную стоимость;
- [ ] P3 сравнивается с P2 при одинаковом бюджете и параметрах;
- [ ] средняя разность P3-P2 положительна;
- [ ] 95%-й доверительный интервал P3-P2 опубликован;
- [ ] результат не определяется одним днем;
- [ ] результат не определяется только одним рыночным режимом;
- [ ] опубликован разрыв между P3 и P4;
- [ ] выполнен анализ чувствительности к стоимости действия.

Если M5 улучшает отдельные метрики, но не улучшает P3 относительно P2, модель остается `research_only` и не заменяет M4 в основном выводе.

## 44. Автоматические проверки

Минимальный набор модульных и интеграционных тестов:

```text
test_target_event_matches_positive_amplitude
test_severity_training_uses_positive_rows_only
test_occurrence_scaler_fits_train_only
test_severity_scaler_fits_positive_train_only
test_inference_severity_runs_for_all_rows
test_probability_bounds
test_severity_positive_output
test_combined_prediction_equals_product
test_no_non_finite_predictions
test_common_mask_matches_m4
test_temporal_split_respects_embargo
test_reference_market_join_is_backward_only
test_calibrators_do_not_fit_test
test_policy_uses_notional_budget
test_policy_respects_budget_tolerance
test_break_even_markout_consistency
test_negative_control_changes_alignment
test_artifact_manifest_is_complete
test_repeated_run_is_deterministic
```

Интеграционный тест должен запускаться на малом фиксированном отрезке данных и проверять полный путь:

```text
data -> targets -> features -> two models -> calibration -> product -> P3 -> artifacts
```

## 45. План реализации

### Этап 1. Общие цели M4/M5

- [ ] вынести расчет знакового маркаута в общий модуль;
- [ ] реализовать `adverse_event`;
- [ ] реализовать `adverse_amplitude_bps`;
- [ ] добавить проверки инвариантов;
- [ ] зафиксировать версию схемы цели.

### Этап 2. Набор решений

- [ ] реализовать сетку 10 секунд;
- [ ] добавить горизонт 600 секунд;
- [ ] добавить будущее окно цены;
- [ ] материализовать компактную таблицу решений;
- [ ] добавить манифест временных частей.

### Этап 3. Компонент вероятности

- [ ] реализовать постоянный ориентир;
- [ ] реализовать логистическую модель;
- [ ] добавить нелинейного кандидата;
- [ ] добавить временную проверку;
- [ ] добавить калибровку вероятности.

### Этап 4. Компонент амплитуды

- [ ] реализовать постоянное среднее положительной части;
- [ ] реализовать гамма-регрессию;
- [ ] добавить нелинейного кандидата;
- [ ] обеспечить обучение только на `S > 0`;
- [ ] добавить калибровку условной амплитуды.

### Этап 5. Объединение

- [ ] реализовать класс M5;
- [ ] сохранить обе компоненты и произведение;
- [ ] добавить калибровку произведения;
- [ ] реализовать однокомпонентные разложения;
- [ ] реализовать отрицательные контроли.

### Этап 6. Политика P3

- [ ] реализовать ожидаемую валовую стоимость;
- [ ] реализовать стоимость действия;
- [ ] реализовать ожидаемую чистую стоимость;
- [ ] добавить порог безубыточности;
- [ ] реализовать бюджет по номиналу;
- [ ] сравнить P3 с P2 и P4.

### Этап 7. Воспроизводимость

- [ ] сохранять конфигурацию;
- [ ] сохранять модели и преобразователи;
- [ ] сохранять три калибратора;
- [ ] сохранять прогнозы итогового теста;
- [ ] сохранять дневные метрики;
- [ ] сохранять результаты повторной выборки;
- [ ] добавить карточку в реестр моделей.

### Этап 8. Дашборды

- [ ] загрузить прогнозы M5 в ClickHouse;
- [ ] построить калибровку вероятности;
- [ ] построить калибровку амплитуды;
- [ ] построить калибровку произведения;
- [ ] построить сравнение M4/M5;
- [ ] построить сравнение P2/P3/P4;
- [ ] построить дневную устойчивость;
- [ ] построить анализ по режимам;
- [ ] заполнить ссылки и комментарии в разделе 42.

## 46. Карточка для MODEL_REGISTRY

Шаблон записи:

```yaml
model_id: M5
model_name: m5_hurdle_economic_model
status: planned
research_role: separate_occurrence_and_severity_estimation_for_P3
feature_backbone: <M0|M1|M2|M3>
feature_schema_version: <VERSION>
target_schema_version: adverse_selection_v1
prediction_horizon_seconds: 600
decision_step_seconds: 10

occurrence_model:
  implementation: <CLASS_OR_PIPELINE>
  parameters: <PARAMETERS>
  calibration: <METHOD>
  artifact_path: <PATH>

severity_model:
  implementation: <CLASS_OR_PIPELINE>
  parameters: <PARAMETERS>
  calibration: <METHOD>
  artifact_path: <PATH>

combined_prediction:
  formula: calibrated_probability * calibrated_severity_bps
  calibration: <METHOD>

primary_policy: P3_hurdle_economic
reference_model: M4_direct_value_regression
reference_policy: P2_direct_economic
budget_notional_fraction: 0.10
internalization_rate: 0.25
mitigation_efficiency: 0.50
action_cost_bps: 0.50
break_even_markout_bps: 4.00
run_id: <RUN_ID>
artifact_path: artifacts/models/M5/<RUN_ID>
accepted_at: null
```

## 47. Контрольный список после запуска

### Данные

- [ ] записано число строк до и после общей маски;
- [ ] записано число положительных наблюдений;
- [ ] опубликована доля положительных событий по временным частям;
- [ ] проверена причинность признаков;
- [ ] проверен защитный промежуток;
- [ ] проверено совпадение масок M4 и M5.

### Компонент вероятности

- [ ] сохранены AP, log loss и Brier;
- [ ] построена диаграмма калибровки;
- [ ] сохранены параметры модели и калибратора;
- [ ] отсутствуют вероятности вне `[0, 1]`.

### Компонент амплитуды

- [ ] модель обучалась только на положительной части;
- [ ] сохранены MAE+, RMSE+ и смещение среднего;
- [ ] проверена ошибка в хвосте;
- [ ] построена диаграмма калибровки;
- [ ] отсутствуют неположительные и нечисловые прогнозы.

### Объединенный прогноз

- [ ] произведение совпадает с компонентами;
- [ ] сохранены MAE, RMSE, смещение и ранговые метрики;
- [ ] построена калибровка ожидаемой амплитуды;
- [ ] проведено сравнение с M4;
- [ ] проведены разложения и отрицательные контроли.

### Экономика

- [ ] P3 использует бюджет по номиналу;
- [ ] порог безубыточности равен 4 б.п. для конфигурации 1.0;
- [ ] сохранены валовая стоимость, затраты и чистая стоимость;
- [ ] сохранены BCR и запас прочности;
- [ ] P3 сравнивается с P2 и P4;
- [ ] опубликован доверительный интервал P3-P2.

### Воспроизводимость

- [ ] сохранен `config.yaml`;
- [ ] сохранен `manifest.json`;
- [ ] сохранены модели, преобразователи и калибраторы;
- [ ] сохранены прогнозы итогового теста;
- [ ] указан идентификатор версии кода;
- [ ] карточка добавлена в `MODEL_REGISTRY.md`.

## 48. Известные ограничения

1. Положительная подвыборка меньше полной и может быть недостаточной для устойчивой оценки амплитуды.
2. Ошибки вероятности и амплитуды перемножаются.
3. Хорошая калибровка компонент по отдельности не гарантирует калибровку произведения.
4. Гамма-модель может недостаточно описывать экстремальный хвост.
5. Событие `S > 0` включает движения, слишком малые для окупаемости вмешательства.
6. Экономические параметры являются сценарными, а не параметрами реальной организации.
7. Binance `aggTrades` не содержит клиентских типов, реального инвентаря, маршрутизации и фактических решений о хеджировании.
8. Наблюдаемая предсказательная связь не доказывает причинный механизм движения цены.
9. Политика с постоянной стоимостью действия упрощает реальную зависимость затрат от ликвидности, размера и времени.
10. Результат на BTCUSDT и ETHUSDT нельзя автоматически переносить на валютный рынок или клиентский поток финансовой платформы.

## 49. Шаблон итогового результата

### 49.1. Конфигурация

| Параметр | Значение |
|---|---:|
| Основа признаков | `[M0/M1/M2/M3]` |
| Горизонт | `600 секунд` |
| Шаг решения | `10 секунд` |
| Модель вероятности | `[указать]` |
| Калибровка вероятности | `[указать]` |
| Модель амплитуды | `[указать]` |
| Калибровка амплитуды | `[указать]` |
| Калибровка произведения | `[указать]` |
| Бюджет | `10% номинала` |
| Порог безубыточности | `4.00 б.п.` |

### 49.2. Компонент вероятности

| Рынок | AP | Log loss | Brier | Наклон калибровки | Свободный член |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| ETHUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

### 49.3. Компонент амплитуды

| Рынок | Положительных строк | MAE+, б.п. | RMSE+, б.п. | Смещение, б.п. | Ошибка хвоста, б.п. |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| ETHUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

### 49.4. M4 против M5

| Рынок | MAE M4 | MAE M5 | Смещение M4 | Смещение M5 | Top-10% capture M4 | Top-10% capture M5 |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| ETHUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

### 49.5. P2 против P3

| Рынок | V/$1 млн P2 | V/$1 млн P3 | Разность P3-P2 | 95%-й интервал | BCR P3 | Эффективность P4 |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| ETHUSDT | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

### 49.6. Вывод

> `[Указать, улучшило ли двухчастное разложение прогноз ожидаемого неблагоприятного маркаута и чистую экономическую ценность относительно M4. Отдельно описать вклад вероятности, вклад амплитуды, устойчивость по дням и режимам, а также оставшийся разрыв до P4.]`

## 50. Итог

M5 завершает исследовательскую последовательность моделей ReDataX. Она разделяет задачу на оценку частоты неблагоприятного события и оценку его серьезности, но сохраняет единый экономический объект:

\[
\widehat S_i
=
\widehat p_i\widehat\mu_i.
\]

Модель считается успешной не из-за более сложной структуры и не из-за отдельной интерпретируемости компонент. Основной критерий - устойчивое вневыборочное преимущество политики P3 относительно P2 при одинаковых данных, признаках, временных частях, параметрах экономики и бюджете по номиналу.
