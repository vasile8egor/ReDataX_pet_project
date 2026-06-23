WITH snapshot_state AS (
    SELECT
        run_id,
        event_index,
        pricing_policy,

        maxIf(
            phi,
            currency = 'EUR'
        ) AS phi_eur,

        maxIf(
            phi,
            currency = 'GBP'
        ) AS phi_gbp,

        maxIf(
            phi,
            currency = 'USD'
        ) AS phi_usd

    FROM gold.fact_inventory_snapshots

    WHERE model_version =
        'hamiltonian-observer-v1-normal'

    GROUP BY
        run_id,
        event_index,
        pricing_policy
)

SELECT
    pricing_policy,

    round(
        corr(phi_eur, phi_gbp),
        4
    ) AS corr_eur_gbp,

    round(
        corr(phi_eur, phi_usd),
        4
    ) AS corr_eur_usd,

    round(
        corr(phi_gbp, phi_usd),
        4
    ) AS corr_gbp_usd

FROM snapshot_state

GROUP BY pricing_policy

ORDER BY pricing_policy;