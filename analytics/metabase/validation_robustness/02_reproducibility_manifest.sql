SELECT
    experiment_id AS "Experiment ID",
    research_version AS "Research Version",
    git_commit AS "Git Commit",
    scenario_name AS Scenario,
    round(internalization_rate * 100, 1) AS "Internalization, %",
    round(mitigation_efficiency * 100, 1) AS "Mitigation, %",
    round(action_cost_bps, 2) AS "Action Cost, bps",
    round(break_even_markout_bps, 2) AS "Break-even Markout, bps",
    decision_stride_seconds AS "Decision Stride, sec",
    hurdle_source_path AS "Hurdle Artifact",
    oracle_source_path AS "Oracle Artifact",
    created_at AS "Created At"
FROM gold.dim_research_experiment_runs FINAL
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]];
