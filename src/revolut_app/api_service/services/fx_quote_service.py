import json
from datetime import timedelta
from uuid import UUID
from fastapi import HTTPException, status
from revolut_app.api_service.schemas.fx import (
    DaySimulationRequest,
    DaySimulationResponse,
    ExperimentPersistenceResponse,
    FXQuoteRequest,
    FXQuoteResponse,
    FXQuoteComponentsResponse,
    HedgeExecutionItemResponse,
    HedgeExecutionRequest,
    HedgeExecutionResponse,
    HedgeRecommendationRequest,
    HedgeRecommendationItemResponse,
    HedgeRecommendationResponse,
    InventorySnapshotPointResponse,
    InventoryStateResponse,
    PnLSnapshotResponse,
    PnLEventResponse,
    PolicyComparisonRequest,
    PolicyComparisonResponse,
    PolicyRunResponse,
    RGFlowPointResponse,
    RGFlowRequest,
    RGFlowResponse,
    RiskSnapshotResponse,
)
from revolut_app.fx_lab.shared.constants import (
    BPS_DENOMINATOR,
    COMPONENT_BPS_PRECISION,
    PNL_PRECISION,
    RATIO_PRECISION,
    STATE_VALUE_PRECISION,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.execution_constants import (
    EXECUTION_AMOUNT_PRECISION,
    EXECUTION_COST_PRECISION,
)
from revolut_app.fx_lab.market.event_generation import HawkesLikeFXEventGenerator
from revolut_app.fx_lab.experiments.models import (
    FXEvent,
    FXEventDataset,
)
from revolut_app.fx_lab.pricing.models import QuoteRequest
from revolut_app.fx_lab.shared.enums import (
    Currency,
    CustomerSegment,
    FXSide,
)
from revolut_app.fx_lab.market.mid_rate import StaticMidRateProvider
from revolut_app.fx_lab.pricing.quote_engine import QuoteEngine
from revolut_app.fx_lab.inventory.ledger import InventoryLedger
from revolut_app.fx_lab.inventory.stress import StressRegimeDetect
from revolut_app.fx_lab.simulation import (
    DaySimulationEngine,
    DaySimulationResult,
    InventorySnapshotPoint,
)
from revolut_app.fx_lab.risk.rg import CoarseGrainingEngine
from revolut_app.fx_lab.inventory.hedging import HedgeEngine, HedgeAction
from revolut_app.fx_lab.inventory.pnl import PnLLedger
from revolut_app.fx_lab.experiments import (
    PolicyComparisonEngine,
)
from revolut_app.loaders.fx_experiment_loader import (
    EventDatasetRecord,
    FXEventRecord,
    FXExperimentClickHouseLoader,
    InventorySnapshotRecord,
    SimulationRunRecord,
)
from revolut_app.fx_lab.experiments.models import PhysicsMode
from revolut_app.fx_lab.risk.hamiltonian import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.shared.enums import HamiltonianPreset
from revolut_app.core.version import resolve_git_sha


class FXQuoteService:
    def __init__(
        self, *,
        ledger: InventoryLedger | None = None,
        quote_engine: QuoteEngine | None = None,
        stress_detect: StressRegimeDetect | None = None,
    ):
        self.ledger = ledger or InventoryLedger()
        self.stress_detect = stress_detect or StressRegimeDetect()
        self.quote_engine = quote_engine or QuoteEngine(
            ledger=self.ledger,
            stress_detect=self.stress_detect,
        )
        self.last_simulation_result: DaySimulationResult | None = None
        self.hedge_engine = HedgeEngine()
        self.pnl_ledger = PnLLedger()
        self.policy_comparison_engine = PolicyComparisonEngine()
        self.experiment_loader = FXExperimentClickHouseLoader()

    def quote(self, request: FXQuoteRequest) -> FXQuoteResponse:
        domain_request = QuoteRequest(
            customer_id=request.customer_id,
            base_currency=request.base_currency,
            quote_currency=request.quote_currency,
            side=request.side,
            amount=request.amount,
            segment=request.segment,
            channel=request.channel,
        )

        quote = self.quote_engine.quote(domain_request)

        if request.execute:
            self.ledger.apply_client_fx(
                request=domain_request,
                mid_rate=quote.mid_rate,
            )

            quote.executed = True
            quote.inventory_pressure = self.ledger.pressures()
            quote.regime = self._current_regime()

        return FXQuoteResponse(
            quote_id=quote.quote_id,
            timestamp=quote.timestamp,
            customer_id=quote.request.customer_id,
            base_currency=quote.request.base_currency,
            quote_currency=quote.request.quote_currency,
            side=quote.request.side,
            amount=quote.request.amount,
            mid_rate=quote.mid_rate,
            client_rate=quote.client_rate,
            components=FXQuoteComponentsResponse(
                base_spread_bps=quote.components.base_spread_bps,
                inventory_penalty_bps=quote.components.inventory_penalty_bps,
                liquidity_penalty_bps=quote.components.liquidity_penalty_bps,
                regime_penalty_bps=quote.components.regime_penalty_bps,
                total_spread_bps=round(
                    quote.components.total_spread_bps,
                    COMPONENT_BPS_PRECISION,
                ),
            ),
            inventory_pressure=quote.inventory_pressure,
            regime=quote.regime,
            executed=quote.executed,
        )

    def risk_snapshot(self) -> RiskSnapshotResponse:
        pressures = self.ledger.pressures()
        states_by_currency = self.ledger.get_all_states()

        states_payload = []

        for currency, state in states_by_currency.items():
            states_payload.append(
                InventoryStateResponse(
                    currency=currency,
                    position=round(state.position, STATE_VALUE_PRECISION),
                    position_limit=state.position_limit,
                    limit_utilization=round(
                        state.limit_utilization,
                        RATIO_PRECISION,
                    ),
                    hedge_capacity=round(
                        state.hedge_capacity,
                        STATE_VALUE_PRECISION,
                    ),
                    max_hedge_capacity=state.max_hedge_capacity,
                    hedge_capacity_used_ratio=round(
                        state.hedge_capacity_used_ratio,
                        RATIO_PRECISION,
                    ),
                    funding_cost_bps=state.funding_cost_bps,
                    market_volatility=round(
                        state.market_volatility,
                        RATIO_PRECISION,
                    ),
                    phi=pressures[currency.value],
                )
            )
        regime = self.stress_detect.detect(
            pressures=pressures,
            states={
                currency.value: state
                for currency, state in states_by_currency.items()
            },
        )

        return RiskSnapshotResponse(
            regime=regime,
            inventory_pressure=pressures,
            states=states_payload,
        )

    def apply_stress_shock(
        self,
        *,
        volatility_multiplier: float,
        hedge_capacity_multiplier: float,
    ) -> RiskSnapshotResponse:
        self.ledger.apply_market_shock(
            volatility_multiplier=volatility_multiplier,
            hedge_capacity_multiplier=hedge_capacity_multiplier,
        )
        return self.risk_snapshot()

    def reset_state(self) -> None:
        self.ledger = InventoryLedger()
        self.stress_detect = StressRegimeDetect()
        self.quote_engine = QuoteEngine(
            ledger=self.ledger,
            stress_detect=self.stress_detect,
        )
        self.hedge_engine = HedgeEngine()
        self.pnl_ledger = PnLLedger()
        self.last_simulation_result = None

    def simulate_day(
        self,
        request: DaySimulationRequest,
    ) -> DaySimulationResponse:
        if request.reset_state:
            self.reset_state()

        engine = DaySimulationEngine(
            ledger=self.ledger,
            quote_engine=self.quote_engine,
            stress_detect=self.stress_detect,
            pnl_ledger=self.pnl_ledger,
        )
        result = engine.simulate_day(
            steps=request.steps,
            dt_seconds=request.dt_seconds,
            base_intensity=request.base_intensity,
            alpha=request.alpha,
            beta=request.beta,
            seed=request.seed,
            amount_multiplier=request.amount_multiplier,
            max_snapshots=request.max_snapshots,
        )
        self.last_simulation_result = result

        return DaySimulationResponse(
            run_id=result.run_id,
            started_at=result.started_at,
            finished_at=result.finished_at,
            generated_requests=result.generated_requests,
            executed_events=result.executed_events,
            final_regime=result.final_regime,
            accepted_events=result.accepted_events,
            rejected_events=result.rejected_events,
            acceptance_rate=result.acceptance_rate,
            max_abs_pressure=result.max_abs_pressure,
            stress_time_fraction=result.stress_time_fraction,
            elevated_or_stress_time_fraction=(
                result.elevated_or_stress_time_fraction
            ),
            synthetic_spread_revenue_usd=result.synthetic_spread_revenue_usd,
            final_inventory_pressure=result.final_inventory_pressure,
            regime_counts=result.regime_counts,
            snapshots=[
                InventorySnapshotPointResponse(
                    event_index=snapshot.event_index,
                    timestamp=snapshot.timestamp,
                    regime=snapshot.regime,
                    accepted=snapshot.accepted,
                    acceptance_probability=snapshot.acceptance_probability,
                    rejected_events=snapshot.rejected_events,
                    inventory_pressure=snapshot.inventory_pressure,
                    max_abs_pressure=snapshot.max_abs_pressure,
                    synthetic_spread_revenue_usd=(
                        snapshot.synthetic_spread_revenue_usd
                    ),
                )
                for snapshot in result.snapshots
            ],
        )

    def rg_flow(self, request: RGFlowRequest) -> RGFlowResponse:
        if self.last_simulation_result is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Run /fx/simulate-day before requesting RG flow.',
            )

        snapshots = self.last_simulation_result.snapshots
        phi_by_currency = self._extract_phi_series_from_snapshots(snapshots)
        engine = CoarseGrainingEngine()
        points = engine.estimate_rg_flow(
            phi_by_currency=phi_by_currency,
            window_sizes=request.window_sizes,
            stress_threshold=request.stress_threshold,
        )

        return RGFlowResponse(
            source_run_id=self.last_simulation_result.run_id,
            source_snapshots=len(snapshots),
            window_sizes=request.window_sizes,
            stress_threshold=request.stress_threshold,
            points=[
                RGFlowPointResponse(
                    window_size=point.window_size,
                    currency=point.currency,
                    mean_phi=point.mean_phi,
                    var_phi=point.var_phi,
                    autocorr_lag1=point.autocorr_lag1,
                    stress_probability=point.stress_probability,
                )
                for point in points
            ]
        )

    def hedge_recommendation(
        self,
        request: HedgeRecommendationRequest,
    ) -> HedgeRecommendationResponse:
        pressures = self.ledger.pressures()
        states = self.ledger.get_all_states()

        regime = self.stress_detect.detect(
            pressures=pressures,
            states={
                currency.value: state
                for currency, state in states.items()
            },
        )
        result = self.hedge_engine.recommend(
            pressures=pressures,
            states=states,
            regime=regime,
            pressure_threshold=request.pressure_threshold,
            target_pressure=request.target_pressure,
            max_hedge_fraction=request.max_hedge_fraction,
            min_notional=request.min_notional,
        )

        return HedgeRecommendationResponse(
            regime=result.regime,
            pressure_threshold=result.pressure_threshold,
            target_pressure=result.target_pressure,
            recommendations=[
                HedgeRecommendationItemResponse(
                    currency=recommendation.currency,
                    action=recommendation.action,
                    amount=recommendation.amount,
                    desired_amount=recommendation.desired_amount,
                    capacity_limited=recommendation.capacity_limited,
                    unhedged_amount=recommendation.unhedged_amount,
                    current_position=recommendation.current_position,
                    position_limit=recommendation.position_limit,
                    current_pressure=recommendation.current_pressure,
                    threshold=recommendation.threshold,
                    target_pressure=recommendation.target_pressure,
                    expected_pressure_reduction=(
                        recommendation.expected_pressure_reduction
                    ),
                    reason=recommendation.reason,
                )
                for recommendation in result.recommendations
            ],
        )

    def execute_hedge(
        self,
        request: HedgeExecutionRequest,
    ) -> HedgeExecutionResponse:
        before = self.risk_snapshot()
        pressures_before = self.ledger.pressures()
        states = self.ledger.get_all_states()
        regime = self.stress_detect.detect(
            pressures=pressures_before,
            states={
                currency.value: state
                for currency, state in states.items()
            },
        )

        recommendation_result = self.hedge_engine.recommend(
            pressures=pressures_before,
            states=states,
            regime=regime,
            pressure_threshold=request.pressure_threshold,
            target_pressure=request.target_pressure,
            max_hedge_fraction=request.max_hedge_fraction,
            min_notional=request.min_notional,
        )

        executed_hedges: list[HedgeExecutionItemResponse] = []
        total_hedge_cost_usd = ZERO_FLOAT
        skipped_count = 0

        recommendations = recommendation_result.recommendations[
            :request.max_actions
        ]

        for recommendation in recommendations:
            if recommendation.action == HedgeAction.hold:
                skipped_count += 1
                continue

            pressure_before = self.ledger.pressure(
                recommendation.currency,
            )

            execution = self.ledger.apply_hedge(
                currency=recommendation.currency,
                action=recommendation.action,
                amount=recommendation.amount,
            )

            executed_amount = execution['executed_amount']

            if executed_amount <= ZERO_FLOAT:
                skipped_count += 1
                continue

            pressure_after = self.ledger.pressure(
                recommendation.currency,
            )

            hedge_cost_usd = self._hedge_cost_usd(
                currency=recommendation.currency,
                amount=executed_amount,
                hedge_cost_bps=request.hedge_cost_bps,
            )

            total_hedge_cost_usd += hedge_cost_usd

            notional_usd = self._notional_usd(
                currency=recommendation.currency,
                amount=executed_amount,
            )

            self.pnl_ledger.record_hedge_cost(
                currency=recommendation.currency.value,
                hedge_action=recommendation.action.value,
                executed_amount=executed_amount,
                notional_usd=notional_usd,
                hedge_cost_bps=request.hedge_cost_bps,
                hedge_cost_usd=hedge_cost_usd,
            )

            executed_hedges.append(
                HedgeExecutionItemResponse(
                    currency=recommendation.currency,
                    action=recommendation.action,
                    request_amount=round(
                        execution['requested_amount'],
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    executed_amount=round(
                        executed_amount,
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    hedge_cost_usd=round(
                        hedge_cost_usd,
                        EXECUTION_COST_PRECISION,
                    ),
                    position_before=round(
                        execution['position_before'],
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    position_after=round(
                        execution['position_after'],
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    pressure_before=round(
                        pressure_before,
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    pressure_after=round(
                        pressure_after,
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    hedge_capacity_before=round(
                        execution['hedge_capacity_before'],
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                    hedge_capacity_after=round(
                        execution['hedge_capacity_after'],
                        EXECUTION_AMOUNT_PRECISION,
                    ),
                )
            )

        after = self.risk_snapshot()

        if executed_hedges:
            message = (
                'Hedge execution completed. '
                'Inventory state and hedge capacity were updated.'
            )
        else:
            message = (
                'No hedge actions were executed. '
                'No recommendations passed execution filters.'
            )

        return HedgeExecutionResponse(
            before=before,
            after=after,
            executed_hedges=executed_hedges,
            total_hedge_cost_usd=round(
                total_hedge_cost_usd,
                EXECUTION_COST_PRECISION,
            ),
            executed_count=len(executed_hedges),
            skipped_count=skipped_count,
            message=message,
        )

    def pnl_snapshot(self) -> PnLSnapshotResponse:
        snapshot = self.pnl_ledger.snapshot(
            funding_cost_usd=self._estimated_funding_cost_usd(),
        )

        return PnLSnapshotResponse(
            spread_revenue_usd=snapshot.spread_revenue_usd,
            hedge_cost_usd=snapshot.hedge_cost_usd,
            funding_cost_usd=snapshot.funding_cost_usd,
            gross_pnl_usd=snapshot.gross_pnl_usd,
            net_pnl_usd=snapshot.net_pnl_usd,
            events_count=snapshot.events_count,
            last_events=[
                PnLEventResponse(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    timestamp=event.timestamp,
                    amount_usd=event.amount_usd,
                    description=event.description,
                    metadata=event.metadata,
                )
                for event in snapshot.last_events
            ],
        )

    def policy_comparison(
        self,
        request: PolicyComparisonRequest,
    ) -> PolicyComparisonResponse:
        if request.event_dataset_id is None:
            generator = HawkesLikeFXEventGenerator(seed=request.seed)
            event_dataset = generator.simulate_event_dataset(
                steps=request.steps,
                dt_seconds=request.dt_seconds,
                base_intensity=request.base_intensity,
                alpha=request.alpha,
                beta=request.beta,
                start_at=request.simulation_start_at,
                seed=request.seed,
            )
            dataset_was_reused = False
        else:
            try:
                event_records = self.experiment_loader.load_event_dataset(
                    event_dataset_id=request.event_dataset_id,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f'Failed to load FX event dataset: {exc}',
                ) from exc

            if not event_records:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        'FX event dataset was not found: '
                        f'{request.event_dataset_id}'
                    ),
                )

            event_dataset = self._event_dataset_from_records(
                records=event_records,
            )
            dataset_was_reused = True

        hamiltonian_engine = self._build_hamiltonian_engine(
            physics_mode=request.physics_mode,
            preset=request.hamiltonian_preset,
        )
        if request.physics_mode == PhysicsMode.controller:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    'Hamiltonian controller is not implemented yet'
                ),
            )

        result = self.policy_comparison_engine.compare(
            policy_names=request.policies,
            event_dataset=event_dataset,
            amount_multiplier=request.amount_multiplier,
            snapshot_every_n_events=(
                request.snapshot_every_n_events
            ),
            hamiltonian_engine=hamiltonian_engine,
        )

        dataset_rows = 0
        run_rows = 0
        snapshot_rows = 0
        event_rows = 0
        if request.persist_result:
            parameters = {
                'policies': [
                    policy.value
                    for policy in request.policies
                ],
                'steps': request.steps,
                'dt_seconds': request.dt_seconds,
                'base_intensity': request.base_intensity,
                'alpha': request.alpha,
                'beta': request.beta,
                'seed': request.seed,
                'amount_multiplier': request.amount_multiplier,
                'model_version': request.model_version,
                'physics_mode': request.physics_mode.value,
                'hedging_policy': request.hedging_policy,
                'snapshot_every_n_events': request.snapshot_every_n_events,
                'event_dataset_id': str(event_dataset.event_dataset_id),
                'event_dataset_reused': dataset_was_reused,
                'git_sha': resolve_git_sha(),
                'hamiltonian': (
                    hamiltonian_engine.parameters.as_dict()
                    if hamiltonian_engine is not None
                    else None
                ),
                'hamiltonian_preset': (
                    request.hamiltonian_preset.value
                    if request.hamiltonian_preset is not None
                    else None
                ),
            }

            event_dataset_record = EventDatasetRecord(
                event_dataset_id=UUID(result.event_dataset_id),
                comparison_id=UUID(result.comparison_id),
                generator=event_dataset.generator,
                seed=event_dataset.seed,
                steps=event_dataset.source_steps,
                dt_seconds=event_dataset.dt_seconds,
                base_intensity=event_dataset.base_intensity,
                alpha=event_dataset.alpha,
                beta=event_dataset.beta,
                amount_multiplier=request.amount_multiplier,
                generated_requests=result.generated_requests,
                created_at=event_dataset.started_at,
            )

            runs = [
                SimulationRunRecord(
                    run_id=UUID(item.run_id),
                    comparison_id=UUID(result.comparison_id),
                    event_dataset_id=UUID(result.event_dataset_id),
                    model_version=request.model_version,
                    physics_mode=request.physics_mode.value,
                    pricing_policy=item.policy.value,
                    hedging_policy=request.hedging_policy,
                    seed=event_dataset.seed,
                    steps=event_dataset.source_steps,
                    dt_seconds=event_dataset.dt_seconds,
                    base_intensity=event_dataset.base_intensity,
                    alpha=event_dataset.alpha,
                    beta=event_dataset.beta,
                    amount_multiplier=request.amount_multiplier,
                    generated_requests=item.generated_requests,
                    accepted_events=item.accepted_events,
                    rejected_events=item.rejected_events,
                    acceptance_rate=item.acceptance_rate,
                    average_quoted_spread_bps=(
                        item.average_quoted_spread_bps
                    ),
                    average_accepted_spread_bps=(
                        item.average_accepted_spread_bps
                    ),
                    customer_spread_cost_usd=(
                        item.customer_spread_cost_usd
                    ),
                    spread_revenue_usd=item.spread_revenue_usd,
                    allocated_product_revenue_usd=(
                        item.allocated_product_revenue_usd
                    ),
                    hedge_cost_usd=0.0,
                    funding_cost_usd=item.funding_cost_usd,
                    net_pnl_usd=item.net_pnl_usd,
                    final_regime=item.final_regime.value,
                    max_abs_pressure=item.max_abs_pressure,
                    stress_time_fraction=item.stress_time_fraction,
                    final_inventory_pressure_json=json.dumps(
                        item.final_inventory_pressure,
                        sort_keys=True,
                    ),
                    parameters_json=json.dumps(
                        parameters,
                        sort_keys=True,
                    ),
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                )
                for item in result.results
            ]

            snapshot_records = [
                InventorySnapshotRecord(
                    run_id=UUID(policy_result.run_id),
                    comparison_id=UUID(result.comparison_id),
                    event_dataset_id=UUID(result.event_dataset_id),

                    model_version=request.model_version,
                    physics_mode=request.physics_mode.value,
                    pricing_policy=policy_result.policy.value,

                    event_index=snapshot.event_index,
                    source_event_id=snapshot.source_event_id,
                    source_step_index=snapshot.source_step_index,
                    snapshot_ts=snapshot.snapshot_ts,

                    currency=snapshot.currency.value,

                    position=snapshot.position,
                    position_limit=snapshot.position_limit,
                    limit_utilization=snapshot.limit_utilization,
                    position_pressure=snapshot.position_pressure,

                    order_flow_buy_ewma=(
                        snapshot.order_flow_buy_ewma
                    ),
                    order_flow_sell_ewma=(
                        snapshot.order_flow_sell_ewma
                    ),
                    order_flow_imbalance=(
                        snapshot.order_flow_imbalance
                    ),

                    phi=snapshot.phi,

                    hedge_capacity=snapshot.hedge_capacity,
                    max_hedge_capacity=(
                        snapshot.max_hedge_capacity
                    ),
                    hedge_capacity_used_ratio=(
                        snapshot.hedge_capacity_used_ratio
                    ),

                    funding_cost_bps=snapshot.funding_cost_bps,
                    market_volatility=snapshot.market_volatility,

                    regime=snapshot.regime.value,

                    event_accepted=snapshot.event_accepted,
                    acceptance_probability=(
                        snapshot.acceptance_probability
                    ),

                    cumulative_accepted_events=(
                        snapshot.cumulative_accepted_events
                    ),
                    cumulative_rejected_events=(
                        snapshot.cumulative_rejected_events
                    ),
                    cumulative_spread_revenue_usd=(
                        snapshot.cumulative_spread_revenue_usd
                    ),

                    h_total=snapshot.h_total,
                    h_quadratic=snapshot.h_quadratic,
                    h_quartic=snapshot.h_quartic,
                    h_coupling=snapshot.h_coupling,
                    h_external=snapshot.h_external,
                )
                for policy_result in result.results
                for snapshot in policy_result.snapshots
            ]

            event_records_to_persist = (
                self._event_records_from_dataset(event_dataset)
                if not dataset_was_reused
                else []
            )

            try:
                dataset_rows, run_rows, snapshot_rows, event_rows = (
                    self.experiment_loader.load_comparison(
                        event_dataset=event_dataset_record,
                        runs=runs,
                        snapshots=snapshot_records,
                        events=event_records_to_persist,
                        persist_event_dataset=not dataset_was_reused,
                    )
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Policy comparison completed, but ClickHouse "
                        f"persistence failed: {exc}"
                    ),
                ) from exc

        return PolicyComparisonResponse(
            event_dataset_id=event_dataset.event_dataset_id,
            event_dataset_reused=dataset_was_reused,
            comparison_id=result.comparison_id,
            started_at=result.started_at,
            finished_at=result.finished_at,
            generated_requests=result.generated_requests,
            seed=result.seed,
            results=[
                PolicyRunResponse(
                    run_id=item.run_id,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                    policy=item.policy,
                    generated_requests=item.generated_requests,
                    accepted_events=item.accepted_events,
                    rejected_events=item.rejected_events,
                    acceptance_rate=item.acceptance_rate,
                    average_quoted_spread_bps=(
                        item.average_quoted_spread_bps
                    ),
                    average_accepted_spread_bps=(
                        item.average_accepted_spread_bps
                    ),
                    customer_spread_cost_usd=(
                        item.customer_spread_cost_usd
                    ),
                    spread_revenue_usd=item.spread_revenue_usd,
                    allocated_product_revenue_usd=(
                        item.allocated_product_revenue_usd
                    ),
                    funding_cost_usd=item.funding_cost_usd,
                    net_pnl_usd=item.net_pnl_usd,
                    final_regime=item.final_regime,
                    max_abs_pressure=item.max_abs_pressure,
                    stress_time_fraction=item.stress_time_fraction,
                    final_inventory_pressure=(
                        item.final_inventory_pressure
                    ),
                )
                for item in result.results
            ],
            best_policy_by_net_pnl=result.best_policy_by_net_pnl,
            lowest_risk_policy=result.lowest_risk_policy,
            lowest_customer_spread_policy=(
                result.lowest_customer_spread_policy
            ),
            persistence=ExperimentPersistenceResponse(
                persistence=request.persist_result,
                event_dataset_rows=dataset_rows,
                simulation_run_rows=run_rows,
                inventory_snapshot_rows=snapshot_rows,
                event_rows=event_rows,
            ),
            model_version=request.model_version,
            physics_mode=request.physics_mode,
            hamiltonian_preset=request.hamiltonian_preset,
        )

    @staticmethod
    def _event_records_from_dataset(
        event_dataset: FXEventDataset,
    ) -> list[FXEventRecord]:
        return [
            FXEventRecord(
                event_dataset_id=event_dataset.event_dataset_id,
                event_id=event.event_id,
                event_sequence=event.event_sequence,
                source_step_index=event.source_step_index,
                event_ts=event.event_ts,
                customer_id=event.request.customer_id,
                base_currency=event.request.base_currency.value,
                quote_currency=event.request.quote_currency.value,
                side=event.request.side.value,
                amount=event.request.amount,
                customer_segment=event.request.segment.value,
                channel=event.request.channel,
                generator=event_dataset.generator,
                seed=event_dataset.seed,
                source_steps=event_dataset.source_steps,
                dt_seconds=event_dataset.dt_seconds,
                base_intensity=event_dataset.base_intensity,
                alpha=event_dataset.alpha,
                beta=event_dataset.beta,
            )
            for event in event_dataset.events
        ]

    @staticmethod
    def _event_dataset_from_records(
        records: list[FXEventRecord],
    ) -> FXEventDataset:
        first = records[0]
        started_at = first.event_ts - timedelta(
            seconds=first.source_step_index * first.dt_seconds,
        )

        events = tuple(
            FXEvent(
                event_id=record.event_id,
                event_sequence=record.event_sequence,
                source_step_index=record.source_step_index,
                event_ts=record.event_ts,
                request=QuoteRequest(
                    customer_id=record.customer_id,
                    base_currency=Currency(record.base_currency),
                    quote_currency=Currency(record.quote_currency),
                    side=FXSide(record.side),
                    amount=record.amount,
                    segment=CustomerSegment(record.customer_segment),
                    channel=record.channel,
                ),
            )
            for record in records
        )

        return FXEventDataset(
            event_dataset_id=first.event_dataset_id,
            generator=first.generator,
            seed=first.seed,
            started_at=started_at,
            finished_at=started_at + timedelta(
                seconds=first.source_steps * first.dt_seconds,
            ),
            source_steps=first.source_steps,
            dt_seconds=first.dt_seconds,
            base_intensity=first.base_intensity,
            alpha=first.alpha,
            beta=first.beta,
            events=events,
        )

    def _estimated_funding_cost_usd(self) -> float:
        total_cost = ZERO_FLOAT

        for currency, state in self.ledger.get_all_states().items():
            usd_mark = StaticMidRateProvider.USD_MARKS[currency.value]

            notional_usd = abs(state.position) * usd_mark

            funding_cost = (
                notional_usd * state.funding_cost_bps / BPS_DENOMINATOR
            )

            total_cost += funding_cost
        return round(total_cost, PNL_PRECISION)

    @staticmethod
    def _notional_usd(currency: Currency, amount: float) -> float:
        usd_mark = StaticMidRateProvider.USD_MARKS[currency.value]
        return amount * usd_mark

    @staticmethod
    def _hedge_cost_usd(
        currency: Currency,
        amount: float,
        hedge_cost_bps: float,
    ) -> float:
        usd_mark = StaticMidRateProvider.USD_MARKS[currency.value]
        notional_usd = amount * usd_mark
        return notional_usd * hedge_cost_bps / BPS_DENOMINATOR

    @staticmethod
    def _extract_phi_series_from_snapshots(
        snapshots: list[InventorySnapshotPoint],
    ) -> dict[str, list[float]]:
        phi_by_currency: dict[str, list[float]] = {}

        for snapshot in snapshots:
            for currency, phi in snapshot.inventory_pressure.items():
                if currency not in phi_by_currency:
                    phi_by_currency[currency] = []

                phi_by_currency[currency].append(phi)

        return phi_by_currency

    def _current_regime(self):
        pressures = self.ledger.pressures()
        states = {
            currency.value: state
            for currency, state in self.ledger.get_all_states().items()
        }

        return self.stress_detect.detect(
            pressures=pressures,
            states=states,
        )

    def _build_hamiltonian_engine(
        self, *,
        physics_mode: PhysicsMode,
        preset: HamiltonianPreset | None,
    ):
        if physics_mode == PhysicsMode.none:
            return None
        if physics_mode == PhysicsMode.controller:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    'Hamiltonian controller doesnt exist now'
                ),
            )
        return build_hamiltonian_engine(preset)
