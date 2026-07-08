-- Views must be removed first.

DROP VIEW IF EXISTS gold.v_research_final_summary;
DROP VIEW IF EXISTS gold.v_research_policy_comparison;
DROP VIEW IF EXISTS gold.v_research_daily_value;
DROP VIEW IF EXISTS gold.v_research_model_selection_path;
DROP VIEW IF EXISTS gold.v_research_intervention_frontier;
DROP VIEW IF EXISTS gold.v_research_oracle_gap;
DROP VIEW IF EXISTS gold.v_research_bootstrap_summary;

-- Reporting facts and dimensions.

DROP TABLE IF EXISTS gold.fact_research_prediction_diagnostics;
DROP TABLE IF EXISTS gold.fact_research_bootstrap;
DROP TABLE IF EXISTS gold.fact_research_policy_metrics;
DROP TABLE IF EXISTS gold.fact_research_model_selection;
DROP TABLE IF EXISTS gold.fact_research_oracle_horizon;

DROP TABLE IF EXISTS gold.dim_research_experiment_runs;
DROP TABLE IF EXISTS gold.dim_research_model_registry;
DROP TABLE IF EXISTS gold.dim_research_policy_registry;
