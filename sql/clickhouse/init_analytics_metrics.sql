-- ReDataX analytical tables for reproducible Metabase dashboards.
-- Apply after the base ClickHouse schema has been created.

CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_model_validation_metrics
(
    experiment_id LowCardinality(String),
    experiment_stage LowCardinality(String),
    metric_scope LowCardinality(String),
    metric_date Nullable(Date),
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    model LowCardinality(String),
    observations UInt64,
    toxic_rate Float64,
    roc_auc Float64,
    average_precision Float64,
    brier_score Float64,
    top_decile_lift Float64,
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY
(
    experiment_id,
    experiment_stage,
    metric_scope,
    symbol,
    horizon_seconds,
    model,
    coalesce(metric_date, toDate('1970-01-01'))
);

CREATE TABLE IF NOT EXISTS gold.fact_model_comparison_bootstrap
(
    experiment_id LowCardinality(String),
    experiment_stage LowCardinality(String),
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    comparison LowCardinality(String),
    metric LowCardinality(String),
    days UInt16,
    mean_delta Float64,
    ci_lower Float64,
    ci_upper Float64,
    positive_day_fraction Float64,
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY
(
    experiment_id,
    experiment_stage,
    symbol,
    horizon_seconds,
    comparison,
    metric
);

CREATE TABLE IF NOT EXISTS gold.fact_adverse_selection_capture
(
    experiment_id LowCardinality(String),
    metric_scope LowCardinality(String),
    metric_date Nullable(Date),
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    capacity_fraction Float64,
    model LowCardinality(String),
    observations UInt64,
    selected_observations UInt64,
    selected_trade_fraction Float64,
    total_notional_usdt Float64,
    selected_notional_usdt Float64,
    selected_notional_fraction Float64,
    total_adverse_loss_usdt Float64,
    captured_adverse_loss_usdt Float64,
    capture_rate Float64,
    loss_lift Float64,
    captured_loss_per_million_total_notional Float64,
    selected_loss_per_million_selected_notional Float64,
    oracle_capture_rate Float64,
    oracle_efficiency Float64,
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY
(
    experiment_id,
    metric_scope,
    symbol,
    horizon_seconds,
    capacity_fraction,
    model,
    coalesce(metric_date, toDate('1970-01-01'))
);

CREATE TABLE IF NOT EXISTS gold.fact_adverse_selection_capture_bootstrap
(
    experiment_id LowCardinality(String),
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    capacity_fraction Float64,
    comparison LowCardinality(String),
    metric LowCardinality(String),
    days UInt16,
    mean_delta Float64,
    ci_lower Float64,
    ci_upper Float64,
    positive_day_fraction Float64,
    loaded_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY
(
    experiment_id,
    symbol,
    horizon_seconds,
    capacity_fraction,
    comparison,
    metric
);
