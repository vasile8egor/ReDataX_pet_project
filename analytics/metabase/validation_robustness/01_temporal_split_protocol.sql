SELECT
    split_name AS Split,
    date_start AS "Start Date",
    date_end AS "End Date",
    days AS Days,
    purpose AS Purpose,
    allowed_decisions AS "Allowed Decisions",
    forbidden_decisions AS "Forbidden Decisions"
FROM gold.v_validation_split_protocol
WHERE 1 = 1
  [[AND experiment_id = {{experiment_id}}]]
ORDER BY split_order;
