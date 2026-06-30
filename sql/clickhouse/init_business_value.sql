CREATE DATABASE IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.fact_business_value_scenarios
(
    experiment_id LowCardinality(String),
    metric_scope LowCardinality(String),
    metric_date Date,
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    capacity_fraction Float64,

    scenario LowCardinality(String),
    mitigation_efficiency Float64,
    internalization_rate Float64,
    action_cost_bps Float64,

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
    risk_concentration Float64,

    gross_protected_value_usdt Float64,
    action_cost_usdt Float64,
    net_protected_value_usdt Float64,

    gross_protected_value_per_million_total_notional Float64,
    net_protected_value_per_million_total_notional Float64,
    break_even_action_cost_bps Float64,
    benefit_cost_ratio Float64,

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
    scenario,
    model,
    metric_date
);

CREATE TABLE IF NOT EXISTS gold.fact_business_value_bootstrap
(
    experiment_id LowCardinality(String),
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    capacity_fraction Float64,
    scenario LowCardinality(String),
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
    scenario,
    comparison,
    metric
);
