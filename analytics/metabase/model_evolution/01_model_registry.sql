SELECT
    model_id AS Model,
    model_name AS Name,
    model_family AS Family,
    target_type AS Target,
    status AS Status,
    predecessor_id AS Predecessor,
    description AS Description
FROM gold.dim_research_model_registry FINAL
WHERE model_id IN ('M0', 'M1', 'M2', 'M3', 'M4', 'M5')
ORDER BY multiIf(
    model_id = 'M0', 0,
    model_id = 'M1', 1,
    model_id = 'M2', 2,
    model_id = 'M3', 3,
    model_id = 'M4', 4,
    model_id = 'M5', 5,
    99
);
