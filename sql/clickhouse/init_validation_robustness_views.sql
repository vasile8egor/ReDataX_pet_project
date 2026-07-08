CREATE OR REPLACE VIEW gold.v_validation_split_protocol
(
    experiment_id,
    research_version,
    git_commit,
    split_name,
    split_order,
    date_start,
    date_end,
    days,
    purpose,
    allowed_decisions,
    forbidden_decisions,
    created_at
)
AS
SELECT
    experiment_id,
    research_version,
    git_commit,
    split_name,
    split_order,
    date_start,
    date_end,
    dateDiff('day', date_start, date_end) + 1,
    purpose,
    allowed_decisions,
    forbidden_decisions,
    created_at
FROM
(
    SELECT
        experiment_id,
        research_version,
        git_commit,
        'train' AS split_name,
        1 AS split_order,
        train_start AS date_start,
        train_end AS date_end,
        'Fit model parameters' AS purpose,
        'Model fitting' AS allowed_decisions,
        'Policy selection and final reporting' AS forbidden_decisions,
        created_at
    FROM gold.dim_research_experiment_runs FINAL

    UNION ALL

    SELECT
        experiment_id,
        research_version,
        git_commit,
        'development',
        2,
        development_start,
        development_end,
        'Select model and policy within each horizon',
        'Model preset, policy threshold and budget selection',
        'Final horizon confirmation and final reporting',
        created_at
    FROM gold.dim_research_experiment_runs FINAL

    UNION ALL

    SELECT
        experiment_id,
        research_version,
        git_commit,
        'validation',
        3,
        validation_start,
        validation_end,
        'Select one horizon and confirm robustness',
        'Horizon selection among development winners',
        'Retuning on final holdout',
        created_at
    FROM gold.dim_research_experiment_runs FINAL

    UNION ALL

    SELECT
        experiment_id,
        research_version,
        git_commit,
        'final',
        4,
        final_start,
        final_end,
        'One-time evaluation of the frozen configuration',
        'Reporting only',
        'Any parameter or threshold tuning',
        created_at
    FROM gold.dim_research_experiment_runs FINAL
);


CREATE OR REPLACE VIEW gold.v_validation_selection_funnel
(
    experiment_id,
    symbol,
    stage,
    stage_order,
    horizon_seconds,
    candidates_recorded,
    accepted_among_recorded,
    selected_candidates,
    selected_model_preset,
    selected_policy_id,
    selected_budget_fraction,
    selected_margin_bps,
    selected_break_even_probability,
    selected_prediction_multiplier,
    selected_mean_daily_value,
    selected_std_daily_value,
    selected_robust_score,
    selected_positive_day_fraction
)
AS
SELECT
    experiment_id,
    symbol,
    stage,
    multiIf(stage = 'development', 1, stage = 'validation', 2, 3),
    horizon_seconds,
    count(),
    countIf(accepted = 1),
    countIf(is_selected = 1),
    anyIf(model_preset, is_selected = 1),
    anyIf(policy_id, is_selected = 1),
    anyIf(notional_budget_fraction, is_selected = 1),
    anyIf(min_expected_net_margin_bps, is_selected = 1),
    anyIf(min_break_even_probability, is_selected = 1),
    anyIf(prediction_multiplier, is_selected = 1),
    anyIf(mean_daily_net_value_per_million_usdt, is_selected = 1),
    anyIf(std_daily_net_value_per_million_usdt, is_selected = 1),
    anyIf(robust_score, is_selected = 1),
    anyIf(positive_day_fraction, is_selected = 1)
FROM gold.fact_research_model_selection FINAL
GROUP BY
    experiment_id,
    symbol,
    stage,
    horizon_seconds;


CREATE OR REPLACE VIEW gold.v_validation_daily_policy_stats
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    policy_id,
    policy_name,
    days,
    mean_daily_net_value_per_million_usdt,
    median_daily_net_value_per_million_usdt,
    std_daily_net_value_per_million_usdt,
    minimum_daily_net_value_per_million_usdt,
    maximum_daily_net_value_per_million_usdt,
    positive_day_fraction,
    mean_acted_notional_fraction,
    mean_capture_rate,
    mean_benefit_cost_ratio
)
AS
SELECT
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    policy_id,
    policy_name,
    count(),
    avg(net_value_per_million_usdt),
    median(net_value_per_million_usdt),
    stddevPop(net_value_per_million_usdt),
    min(net_value_per_million_usdt),
    max(net_value_per_million_usdt),
    avg(net_value_per_million_usdt > 0),
    avg(acted_notional_fraction),
    avg(capture_rate),
    avg(benefit_cost_ratio)
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'daily'
GROUP BY
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    policy_id,
    policy_name;


CREATE OR REPLACE VIEW gold.v_validation_daily_hurdle_path
(
    experiment_id,
    split,
    metric_date,
    symbol,
    horizon_seconds,
    net_value_per_million_usdt,
    acted_notional_fraction,
    capture_rate,
    benefit_cost_ratio,
    profitable,
    cumulative_net_value_per_million_usdt
)
AS
SELECT
    experiment_id,
    split,
    metric_date,
    symbol,
    horizon_seconds,
    net_value_per_million_usdt,
    acted_notional_fraction,
    capture_rate,
    benefit_cost_ratio,
    profitable,
    sum(net_value_per_million_usdt) OVER
    (
        PARTITION BY experiment_id, split, symbol, horizon_seconds
        ORDER BY metric_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
FROM gold.fact_research_policy_metrics FINAL
WHERE metric_scope = 'daily'
  AND policy_id = 'P3';


CREATE OR REPLACE VIEW gold.v_validation_prediction_diagnostics_summary
(
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    days,
    mean_probability_positive,
    mean_probability_break_even,
    mean_expected_positive_markout_p95_bps,
    maximum_expected_positive_markout_bps,
    mean_direct_expected_markout_p95_bps,
    mean_hurdle_predicted_net_positive_fraction,
    mean_direct_predicted_net_positive_fraction
)
AS
SELECT
    experiment_id,
    split,
    symbol,
    horizon_seconds,
    count(),
    avg(probability_positive_mean),
    avg(probability_break_even_mean),
    avg(expected_positive_markout_p95_bps),
    max(expected_positive_markout_max_bps),
    avg(direct_expected_markout_p95_bps),
    avg(hurdle_predicted_net_positive_fraction),
    avg(direct_predicted_net_positive_fraction)
FROM gold.fact_research_prediction_diagnostics FINAL
GROUP BY
    experiment_id,
    split,
    symbol,
    horizon_seconds;


CREATE OR REPLACE VIEW gold.v_validation_final_consistency
(
    experiment_id,
    symbol,
    horizon_seconds,
    validation_mean_daily_value,
    validation_std_daily_value,
    validation_positive_day_fraction,
    final_mean_daily_value,
    final_std_daily_value,
    final_positive_day_fraction,
    final_minus_validation_mean,
    direction_consistent,
    final_profitable_majority
)
AS
SELECT
    v.experiment_id,
    v.symbol,
    v.horizon_seconds,
    v.mean_daily_net_value_per_million_usdt,
    v.std_daily_net_value_per_million_usdt,
    v.positive_day_fraction,
    f.mean_daily_net_value_per_million_usdt,
    f.std_daily_net_value_per_million_usdt,
    f.positive_day_fraction,
    f.mean_daily_net_value_per_million_usdt
        - v.mean_daily_net_value_per_million_usdt,
    (v.mean_daily_net_value_per_million_usdt > 0)
        = (f.mean_daily_net_value_per_million_usdt > 0),
    f.positive_day_fraction >= 0.5
FROM gold.v_validation_daily_policy_stats AS v
INNER JOIN gold.v_validation_daily_policy_stats AS f
    ON v.experiment_id = f.experiment_id
   AND v.symbol = f.symbol
   AND v.horizon_seconds = f.horizon_seconds
   AND v.policy_id = f.policy_id
WHERE v.split = 'validation'
  AND f.split = 'final'
  AND v.policy_id = 'P3';


CREATE OR REPLACE VIEW gold.v_validation_oracle_horizon_best
(
    experiment_id,
    symbol,
    horizon_seconds,
    notional_budget_fraction,
    mean_daily_net_value_per_million_usdt,
    robust_score,
    bootstrap_ci_lower,
    bootstrap_ci_upper,
    positive_day_fraction,
    above_break_even_event_fraction,
    strictly_feasible,
    is_best_by_robust_score,
    is_capital_efficient
)
AS
SELECT
    experiment_id,
    symbol,
    horizon_seconds,
    notional_budget_fraction,
    mean_daily_net_value_per_million_usdt,
    robust_score,
    bootstrap_ci_lower,
    bootstrap_ci_upper,
    positive_day_fraction,
    above_break_even_event_fraction,
    strictly_feasible,
    is_best_by_robust_score,
    is_capital_efficient
FROM gold.fact_research_oracle_horizon FINAL
WHERE strictly_feasible = 1;
