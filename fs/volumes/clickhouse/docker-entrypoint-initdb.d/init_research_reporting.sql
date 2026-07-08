CREATE DATABASE IF NOT EXISTS gold;

-- ============================================================
-- Static research registries
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.dim_research_model_registry
(
    model_id LowCardinality(String),
    model_name String,
    model_family LowCardinality(String),
    target_type LowCardinality(String),
    status LowCardinality(String),
    predecessor_id String,
    description String,
    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY model_id;

CREATE TABLE IF NOT EXISTS gold.dim_research_policy_registry
(
    policy_id LowCardinality(String),
    policy_name String,
    policy_family LowCardinality(String),
    deployable UInt8,
    description String,
    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY policy_id;

-- ============================================================
-- Experiment metadata
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.dim_research_experiment_runs
(
    experiment_id String,
    research_version LowCardinality(String),
    artifact_type LowCardinality(String),
    git_commit String,

    scenario_name LowCardinality(String),
    mitigation_efficiency Float64,
    internalization_rate Float64,
    action_cost_bps Float64,
    break_even_markout_bps Float64,
    decision_stride_seconds UInt32,

    train_start Date,
    train_end Date,
    development_start Date,
    development_end Date,
    validation_start Date,
    validation_end Date,
    final_start Date,
    final_end Date,

    hurdle_source_path String,
    oracle_source_path String,
    hurdle_configuration_json String,
    oracle_configuration_json String,

    created_at DateTime64(3, 'UTC'),
    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY experiment_id;

-- ============================================================
-- Model-selection path
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.fact_research_model_selection
(
    experiment_id String,
    symbol LowCardinality(String),
    stage LowCardinality(String),
    horizon_seconds UInt32,

    candidate_rank UInt32,
    is_selected UInt8,
    accepted UInt8,

    model_id LowCardinality(String),
    model_component LowCardinality(String),
    model_preset LowCardinality(String),
    policy_id LowCardinality(String),

    notional_budget_fraction Float64,
    min_expected_net_margin_bps Float64,
    min_break_even_probability Float64,
    prediction_multiplier Float64,

    mean_daily_net_value_per_million_usdt Float64,
    median_daily_net_value_per_million_usdt Float64,
    std_daily_net_value_per_million_usdt Float64,
    worst_day_net_value_per_million_usdt Float64,
    positive_day_fraction Float64,
    robust_score Float64,

    model_spec_json String,
    policy_spec_json String,
    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY stage
ORDER BY
(
    experiment_id,
    symbol,
    stage,
    horizon_seconds,
    candidate_rank,
    model_id,
    policy_id
);

-- ============================================================
-- Daily and aggregate policy economics
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.fact_research_policy_metrics
(
    experiment_id String,
    metric_scope LowCardinality(String),
    metric_date Date,
    split LowCardinality(String),

    symbol LowCardinality(String),
    horizon_seconds UInt32,

    model_id LowCardinality(String),
    model_component LowCardinality(String),
    model_preset LowCardinality(String),
    policy_id LowCardinality(String),
    policy_name LowCardinality(String),

    notional_budget_fraction Float64,
    min_expected_net_margin_bps Float64,
    min_break_even_probability Float64,
    prediction_multiplier Float64,

    observations UInt64,
    acted_observations UInt64,
    acted_event_fraction Float64,
    mean_action_fraction_on_acted_events Float64,

    total_notional_usdt Float64,
    acted_notional_usdt Float64,
    acted_notional_fraction Float64,

    total_adverse_loss_usdt Float64,
    captured_adverse_loss_usdt Float64,
    capture_rate Float64,
    risk_concentration Float64,

    gross_protected_value_usdt Float64,
    action_cost_usdt Float64,
    net_protected_value_usdt Float64,

    gross_value_per_million_usdt Float64,
    net_value_per_million_usdt Float64,
    break_even_action_cost_bps Float64,
    benefit_cost_ratio Float64,

    oracle_capture_fraction Float64,
    profitable UInt8,

    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY split
ORDER BY
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    metric_scope,
    metric_date,
    policy_id
);

-- ============================================================
-- Bootstrap comparisons
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.fact_research_bootstrap
(
    experiment_id String,
    split LowCardinality(String),
    symbol LowCardinality(String),
    horizon_seconds UInt32,

    comparison_id LowCardinality(String),
    candidate_policy_id LowCardinality(String),
    baseline_policy_id LowCardinality(String),
    metric_name LowCardinality(String),

    days UInt32,
    bootstrap_samples UInt32,
    mean_delta Float64,
    ci_lower Float64,
    ci_upper Float64,
    positive_day_fraction Float64,

    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY split
ORDER BY
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    comparison_id
);

-- ============================================================
-- Prediction diagnostics
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.fact_research_prediction_diagnostics
(
    experiment_id String,
    split LowCardinality(String),
    metric_date Date,
    symbol LowCardinality(String),
    horizon_seconds UInt32,

    model_id LowCardinality(String),
    model_preset LowCardinality(String),
    policy_id LowCardinality(String),

    probability_positive_mean Float64,
    probability_break_even_mean Float64,
    expected_positive_markout_p95_bps Float64,
    expected_positive_markout_max_bps Float64,
    direct_expected_markout_p95_bps Float64,
    hurdle_predicted_net_positive_fraction Float64,
    direct_predicted_net_positive_fraction Float64,

    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY split
ORDER BY
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    metric_date
);

-- ============================================================
-- Oracle feasibility scan
-- ============================================================

CREATE TABLE IF NOT EXISTS gold.fact_research_oracle_horizon
(
    experiment_id String,
    symbol LowCardinality(String),
    horizon_seconds UInt32,
    notional_budget_fraction Float64,

    aggregate_net_value_per_million_usdt Float64,
    mean_daily_net_value_per_million_usdt Float64,
    robust_score Float64,
    positive_day_fraction Float64,
    bootstrap_ci_lower Float64,
    bootstrap_ci_upper Float64,

    above_break_even_event_fraction Float64,
    above_break_even_notional_fraction Float64,
    acted_notional_fraction Float64,
    capture_rate Float64,
    break_even_action_cost_bps Float64,
    benefit_cost_ratio Float64,

    strictly_feasible UInt8,
    is_best_by_robust_score UInt8,
    is_capital_efficient UInt8,

    loaded_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY
(
    experiment_id,
    symbol,
    horizon_seconds,
    notional_budget_fraction
);

-- ============================================================
-- Semantic views for Metabase
--
-- Important:
-- Explicit output-column lists are declared for every view.
-- This prevents ClickHouse from exposing qualified expression names
-- such as `p.experiment_id` instead of `experiment_id`.
-- ============================================================

CREATE OR REPLACE VIEW gold.v_research_final_summary
(
    experiment_id,
    research_version,
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    policy_name,
    scenario_name,
    internalization_rate,
    mitigation_efficiency,
    action_cost_bps,
    break_even_markout_bps,
    aggregate_net_value_per_million_usdt,
    aggregate_gross_value_per_million_usdt,
    acted_notional_fraction,
    capture_rate,
    risk_concentration,
    break_even_action_cost_bps,
    benefit_cost_ratio,
    oracle_capture_fraction,
    mean_daily_uplift_per_million_usdt,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    days
)
AS
SELECT
    p.experiment_id,
    r.research_version,
    p.symbol,
    p.horizon_seconds,
    p.model_id,
    p.model_preset,
    p.policy_id,
    p.policy_name,

    r.scenario_name,
    r.internalization_rate,
    r.mitigation_efficiency,
    r.action_cost_bps,
    r.break_even_markout_bps,

    p.net_value_per_million_usdt,
    p.gross_value_per_million_usdt,

    p.acted_notional_fraction,
    p.capture_rate,
    p.risk_concentration,
    p.break_even_action_cost_bps,
    p.benefit_cost_ratio,
    p.oracle_capture_fraction,

    b.mean_delta,
    b.ci_lower,
    b.ci_upper,
    b.positive_day_fraction,
    b.days
FROM gold.fact_research_policy_metrics FINAL AS p
ANY LEFT JOIN gold.fact_research_bootstrap FINAL AS b
    ON p.experiment_id = b.experiment_id
   AND p.split = b.split
   AND p.symbol = b.symbol
   AND p.horizon_seconds = b.horizon_seconds
   AND b.comparison_id = 'hurdle_minus_no_action'
ANY LEFT JOIN gold.dim_research_experiment_runs FINAL AS r
    ON p.experiment_id = r.experiment_id
WHERE p.metric_scope = 'aggregate'
  AND p.split = 'final'
  AND p.policy_id = 'P3';


CREATE OR REPLACE VIEW gold.v_research_policy_comparison
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    model_id,
    model_component,
    model_preset,
    policy_id,
    policy_name,
    acted_notional_fraction,
    capture_rate,
    risk_concentration,
    gross_value_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps,
    benefit_cost_ratio,
    oracle_capture_fraction,
    profitable
)
AS
SELECT
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    model_id,
    model_component,
    model_preset,
    policy_id,
    policy_name,
    acted_notional_fraction,
    capture_rate,
    risk_concentration,
    gross_value_per_million_usdt,
    net_value_per_million_usdt,
    break_even_action_cost_bps,
    benefit_cost_ratio,
    oracle_capture_fraction,
    profitable
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'aggregate';


CREATE OR REPLACE VIEW gold.v_research_daily_value
(
    experiment_id,
    split,
    metric_date,
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    policy_name,
    acted_notional_fraction,
    capture_rate,
    net_value_per_million_usdt,
    benefit_cost_ratio,
    profitable
)
AS
SELECT
    experiment_id,
    split,
    metric_date,
    symbol,
    horizon_seconds,
    model_id,
    model_preset,
    policy_id,
    policy_name,
    acted_notional_fraction,
    capture_rate,
    net_value_per_million_usdt,
    benefit_cost_ratio,
    profitable
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'daily';


CREATE OR REPLACE VIEW gold.v_research_model_selection_path
(
    experiment_id,
    symbol,
    stage,
    horizon_seconds,
    candidate_rank,
    is_selected,
    accepted,
    model_id,
    model_component,
    model_preset,
    policy_id,
    notional_budget_fraction,
    min_expected_net_margin_bps,
    min_break_even_probability,
    prediction_multiplier,
    mean_daily_net_value_per_million_usdt,
    std_daily_net_value_per_million_usdt,
    positive_day_fraction,
    robust_score
)
AS
SELECT
    experiment_id,
    symbol,
    stage,
    horizon_seconds,
    candidate_rank,
    is_selected,
    accepted,
    model_id,
    model_component,
    model_preset,
    policy_id,
    notional_budget_fraction,
    min_expected_net_margin_bps,
    min_break_even_probability,
    prediction_multiplier,
    mean_daily_net_value_per_million_usdt,
    std_daily_net_value_per_million_usdt,
    positive_day_fraction,
    robust_score
FROM gold.fact_research_model_selection FINAL;


CREATE OR REPLACE VIEW gold.v_research_intervention_frontier
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    policy_id,
    policy_name,
    acted_notional_fraction,
    net_value_per_million_usdt,
    capture_rate,
    risk_concentration,
    benefit_cost_ratio
)
AS
SELECT
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    policy_id,
    policy_name,
    acted_notional_fraction,
    net_value_per_million_usdt,
    capture_rate,
    risk_concentration,
    benefit_cost_ratio
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'aggregate'
  AND policy_id != 'P0';


CREATE OR REPLACE VIEW gold.v_research_oracle_gap
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    model_net_value_per_million_usdt,
    oracle_net_value_per_million_usdt,
    oracle_gap_per_million_usdt,
    oracle_capture_fraction
)
AS
SELECT
    m.experiment_id,
    m.split,
    m.symbol,
    m.horizon_seconds,

    m.net_value_per_million_usdt,

    o.net_value_per_million_usdt,

    o.net_value_per_million_usdt
        - m.net_value_per_million_usdt,

    if(
        o.net_value_per_million_usdt > 0,
        m.net_value_per_million_usdt
            / o.net_value_per_million_usdt,
        0
    )
FROM gold.fact_research_policy_metrics FINAL AS m
INNER JOIN gold.fact_research_policy_metrics FINAL AS o
    ON m.experiment_id = o.experiment_id
   AND m.split = o.split
   AND m.symbol = o.symbol
   AND m.horizon_seconds = o.horizon_seconds
   AND m.metric_scope = o.metric_scope
   AND m.metric_date = o.metric_date
WHERE m.metric_scope = 'aggregate'
  AND m.policy_id = 'P3'
  AND o.policy_id = 'P4';


CREATE OR REPLACE VIEW gold.v_research_bootstrap_summary
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    comparison_id,
    candidate_policy_id,
    baseline_policy_id,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    days,
    bootstrap_samples,
    statistically_positive
)
AS
SELECT
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    comparison_id,
    candidate_policy_id,
    baseline_policy_id,
    mean_delta,
    ci_lower,
    ci_upper,
    positive_day_fraction,
    days,
    bootstrap_samples,
    ci_lower > 0
FROM gold.fact_research_bootstrap FINAL;
