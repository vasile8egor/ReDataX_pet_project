from fastapi import HTTPException, status
from revolut_app.api_service.schemas.fx import (
    DaySimulationRequest,
    DaySimulationResponse,
    FXQuoteRequest,
    FXQuoteResponse,
    FXQuoteComponentsResponse,
    HedgeRecommendationRequest,
    HedgeRecommendationItemResponse,
    HedgeRecommendationResponse,
    InventorySnapshotPointResponse,
    InventoryStateResponse,
    RGFlowPointResponse,
    RGFlowRequest,
    RGFlowResponse,
    RiskSnapshotResponse,
)
from revolut_app.fx_lab.constants import (
    COMPONENT_BPS_PRECISION,
    RATIO_PRECISION,
    STATE_VALUE_PRECISION,
)
from revolut_app.fx_lab.models import QuoteRequest
from revolut_app.fx_lab.quote_engine import QuoteEngine
from revolut_app.fx_lab.state_engine import InventoryLedger
from revolut_app.fx_lab.stress import StressRegimeDetect
from revolut_app.fx_lab.simulation import (
    DaySimulationEngine,
    DaySimulationResult,
    InventorySnapshotPoint,
)
from revolut_app.fx_lab.rg import CoarseGrainingEngine
from revolut_app.fx_lab.hedging import HedgeEngine


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
