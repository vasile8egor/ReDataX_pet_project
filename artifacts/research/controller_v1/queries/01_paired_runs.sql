WITH latest_runs AS
(
    SELECT
        event_dataset_id,
        pricing_policy,
        model_version,

        argMax(
            run_id,
            tuple(loaded_at, run_id)
        ) AS latest_run_id,

        argMax(
            generated_requests,
            tuple(loaded_at, run_id)
        ) AS generated_requests_value,

        argMax(
            accepted_events,
            tuple(loaded_at, run_id)
        ) AS accepted_events_value,

        argMax(
            rejected_events,
            tuple(loaded_at, run_id)
        ) AS rejected_events_value,

        argMax(
            acceptance_rate,
            tuple(loaded_at, run_id)
        ) AS acceptance_rate_value,

        argMax(
            average_quoted_spread_bps,
            tuple(loaded_at, run_id)
        ) AS quoted_spread_value,

        argMax(
            average_accepted_spread_bps,
            tuple(loaded_at, run_id)
        ) AS accepted_spread_value,

        argMax(
            customer_spread_cost_usd,
            tuple(loaded_at, run_id)
        ) AS customer_spread_cost_value,

        argMax(
            spread_revenue_usd,
            tuple(loaded_at, run_id)
        ) AS spread_revenue_value,

        argMax(
            allocated_product_revenue_usd,
            tuple(loaded_at, run_id)
        ) AS product_revenue_value,

        argMax(
            funding_cost_usd,
            tuple(loaded_at, run_id)
        ) AS funding_cost_value,

        argMax(
            net_pnl_usd,
            tuple(loaded_at, run_id)
        ) AS net_pnl_value,

        argMax(
            stress_time_fraction,
            tuple(loaded_at, run_id)
        ) AS stress_fraction_value,

        argMax(
            max_abs_pressure,
            tuple(loaded_at, run_id)
        ) AS max_pressure_value,

        argMax(
            final_regime,
            tuple(loaded_at, run_id)
        ) AS final_regime_value

    FROM gold.fact_simulation_runs

    WHERE model_version IN
    (
        'hamiltonian-observer-v1-normal',
        'hamiltonian-controller-v1-normal'
    )

    GROUP BY
        event_dataset_id,
        pricing_policy,
        model_version
),

paired AS
(
    SELECT
        toString(observer.event_dataset_id)
            AS event_dataset_id,

        observer.pricing_policy
            AS pricing_policy,

        toString(observer.latest_run_id)
            AS observer_run_id,

        toString(controller.latest_run_id)
            AS controller_run_id,

        observer.generated_requests_value
            AS generated_requests,

        observer.accepted_events_value
            AS observer_accepted_events,

        controller.accepted_events_value
            AS controller_accepted_events,

        controller.accepted_events_value
            - observer.accepted_events_value
            AS delta_accepted_events,

        observer.rejected_events_value
            AS observer_rejected_events,

        controller.rejected_events_value
            AS controller_rejected_events,

        observer.acceptance_rate_value
            AS observer_acceptance_rate,

        controller.acceptance_rate_value
            AS controller_acceptance_rate,

        controller.acceptance_rate_value
            - observer.acceptance_rate_value
            AS delta_acceptance_rate,

        observer.quoted_spread_value
            AS observer_quoted_spread_bps,

        controller.quoted_spread_value
            AS controller_quoted_spread_bps,

        controller.quoted_spread_value
            - observer.quoted_spread_value
            AS delta_quoted_spread_bps,

        observer.accepted_spread_value
            AS observer_accepted_spread_bps,

        controller.accepted_spread_value
            AS controller_accepted_spread_bps,

        controller.accepted_spread_value
            - observer.accepted_spread_value
            AS delta_accepted_spread_bps,

        observer.customer_spread_cost_value
            AS observer_customer_spread_cost_usd,

        controller.customer_spread_cost_value
            AS controller_customer_spread_cost_usd,

        controller.customer_spread_cost_value
            - observer.customer_spread_cost_value
            AS delta_customer_spread_cost_usd,

        observer.spread_revenue_value
            AS observer_spread_revenue_usd,

        controller.spread_revenue_value
            AS controller_spread_revenue_usd,

        controller.spread_revenue_value
            - observer.spread_revenue_value
            AS delta_spread_revenue_usd,

        observer.product_revenue_value
            AS observer_product_revenue_usd,

        controller.product_revenue_value
            AS controller_product_revenue_usd,

        controller.product_revenue_value
            - observer.product_revenue_value
            AS delta_product_revenue_usd,

        observer.funding_cost_value
            AS observer_funding_cost_usd,

        controller.funding_cost_value
            AS controller_funding_cost_usd,

        controller.funding_cost_value
            - observer.funding_cost_value
            AS delta_funding_cost_usd,

        observer.net_pnl_value
            AS observer_net_pnl_usd,

        controller.net_pnl_value
            AS controller_net_pnl_usd,

        controller.net_pnl_value
            - observer.net_pnl_value
            AS delta_net_pnl_usd,

        observer.stress_fraction_value
            AS observer_stress_fraction,

        controller.stress_fraction_value
            AS controller_stress_fraction,

        controller.stress_fraction_value
            - observer.stress_fraction_value
            AS delta_stress_fraction,

        observer.max_pressure_value
            AS observer_max_abs_pressure,

        controller.max_pressure_value
            AS controller_max_abs_pressure,

        controller.max_pressure_value
            - observer.max_pressure_value
            AS delta_max_abs_pressure,

        observer.final_regime_value
            AS observer_final_regime,

        controller.final_regime_value
            AS controller_final_regime

    FROM latest_runs AS observer

    INNER JOIN latest_runs AS controller
        ON observer.event_dataset_id
            = controller.event_dataset_id

       AND observer.pricing_policy
            = controller.pricing_policy

    WHERE observer.model_version =
        'hamiltonian-observer-v1-normal'

      AND controller.model_version =
        'hamiltonian-controller-v1-normal'
)

SELECT *
FROM paired
ORDER BY
    pricing_policy,
    event_dataset_id

FORMAT CSVWithNames;

