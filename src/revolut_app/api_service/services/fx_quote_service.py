from revolut_app.api_service.schemas.fx import (
    FXQuoteRequest,
    FXQuoteResponse,
    FXQuoteComponentsResponse,
    InventoryStateResponse,
    RiskSnapshotResponse,
)
from revolut_app.fx_lab.models import QuoteRequest
from revolut_app.fx_lab.quote_engine import QuoteEngine
from revolut_app.fx_lab.state_engine import InventoryLedger
from revolut_app.fx_lab.stress import StressRegimeDetect


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
                    4,
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
                    position=round(state.position, 4),
                    position_limit=state.position_limit,
                    limit_utilization=round(state.limit_utilization, 6),
                    hedge_capacity=round(state.hedge_capacity, 4),
                    max_hedge_capacity=state.max_hedge_capacity,
                    hedge_capacity_used_ratio=round(
                        state.hedge_capacity_used_ratio,
                        6,
                    ),
                    funding_cost_bps=state.funding_cost_bps,
                    market_volatility=round(state.market_volatility, 6),
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
