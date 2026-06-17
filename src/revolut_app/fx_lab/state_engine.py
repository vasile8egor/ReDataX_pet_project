from datetime import datetime, timezone

from revolut_app.fx_lab.models import (
    Currency,
    CurrencyState,
    FXSide,
    QuoteRequest,
)


class InventoryLedger:
    def __init__(self, states: dict[Currency, CurrencyState] | None = None):
        self.states = states or self._default_states()

    @staticmethod
    def _default_states() -> dict[Currency, CurrencyState]:
        return {
            Currency.EUR: CurrencyState(
                currency=Currency.EUR,
                position=10_000.0,
                position_limit=100_000.0,
                hedge_capacity=50_000.0,
                max_hedge_capacity=50_000.0,
                funding_cost_bps=1.2,
                market_volatility=0.012,
            ),
            Currency.GBP: CurrencyState(
                currency=Currency.GBP,
                position=8_000.0,
                position_limit=90_000.0,
                hedge_capacity=40_000.0,
                max_hedge_capacity=40_000.0,
                funding_cost_bps=1.4,
                market_volatility=0.014,
            ),
            Currency.USD: CurrencyState(
                currency=Currency.USD,
                position=15_000.0,
                position_limit=120_000.0,
                hedge_capacity=60_000.0,
                max_hedge_capacity=60_000.0,
                funding_cost_bps=1.0,
                market_volatility=0.01,
            ),
        }

    def get_state(self, currency: Currency) -> CurrencyState:
        if currency not in self.states:
            self.states[currency] = CurrencyState(currency=currency)
        return self.states[currency]

    def get_all_states(self) -> dict[Currency, CurrencyState]:
        return self.states

    def pressure(self, currency: Currency) -> float:
        state = self.get_state(currency)

        position_pressure = self._div_zero(
            state.position,
            state.position_limit,
        )
        order_flow_total = (
            state.order_flow_buy_ewma
            + state.order_flow_sell_ewma
        )
        order_flow_imbalance = self._div_zero(
            state.order_flow_buy_ewma - state.order_flow_sell_ewma,
            order_flow_total,
        )

        liquidity_pressure = state.hedge_capacity_used_ratio

        phi = (
            0.65 * position_pressure
            + 0.25 * order_flow_imbalance
            + 0.10 * liquidity_pressure
        )

        return round(max(-2.0, min(2.0, phi)), 6)

    def pressures(self) -> dict[str, float]:
        return {
            currency.value: self.pressure(currency)
            for currency in self.states
        }

    def apply_client_fx(self, request: QuoteRequest, mid_rate: float) -> None:
        base_state = self.get_state(request.base_currency)
        quote_state = self.get_state(request.quote_currency)

        base_amount = request.amount
        quote_amount = base_amount * mid_rate

        if request.side == FXSide.buy:
            base_state.position -= base_amount
            quote_state.position += quote_amount

            self._update_order_flow(
                state=base_state,
                buy_amount=base_amount,
                sell_amount=0.0,
            )

        elif request.side == FXSide.sell:
            base_state.position += base_amount
            quote_state.position -= quote_amount

            self._update_order_flow(
                state=base_state,
                buy_amount=0.0,
                sell_amount=base_amount,
            )

        now = datetime.now(timezone.utc)
        base_state.updated_at = now
        quote_state.updated_at = now

    def apply_market_shock(
        self,
        *,
        volatility_multiplier: float = 2.0,
        hedge_capacity_multiplier: float = 0.7,
    ) -> None:
        for state in self.states.values():
            state.market_volatility *= volatility_multiplier
            state.hedge_capacity *= hedge_capacity_multiplier
            state.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _update_order_flow(
        *,
        state: CurrencyState,
        buy_amount: float,
        sell_amount: float,
        decay: float = 0.92,
    ) -> None:
        norm_buy = buy_amount / 10_000.0
        norm_sell = sell_amount / 10_000.0

        state.order_flow_buy_ewma = (
            decay * state.order_flow_buy_ewma
            + (1.0 - decay) * norm_buy
        )

        state.order_flow_sell_ewma = (
            decay * state.order_flow_sell_ewma
            + (1.0 - decay) * norm_sell
        )

    @staticmethod
    def _div_zero(numerator: float, denominator: float) -> float:
        if abs(denominator) < 1e-12:
            return 0.0
        return numerator / denominator
