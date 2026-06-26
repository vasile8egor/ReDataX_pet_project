from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from dataclasses import replace

from revolut_app.fx_lab.shared.constants import (
    DEFAULT_CURRENCY_STATES,
    DEFAULT_STRESS_HEDGE_CAPACITY_MULTIPLIER,
    DEFAULT_STRESS_VOLATILITY_MULTIPLIER,
    EPSILON,
    LIQUIDITY_PRESSURE_WEIGHT,
    MAX_PRESSURE,
    MIN_PRESSURE,
    ORDER_FLOW_DECAY,
    ORDER_FLOW_NORMALIZER,
    ORDER_FLOW_PRESSURE_WEIGHT,
    POSITION_PRESSURE_WEIGHT,
    RATIO_PRECISION,
    ONE_FLOAT,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.shared.execution_constants import (
    EXECUTION_AMOUNT_PRECISION,
)
from revolut_app.fx_lab.inventory.models import CurrencyState
from revolut_app.fx_lab.shared.enums import Currency, FXSide
from revolut_app.fx_lab.inventory.hedging import HedgeAction

if TYPE_CHECKING:
    from revolut_app.fx_lab.pricing.models import QuoteRequest


class InventoryLedger:
    def __init__(self, states: dict[Currency, CurrencyState] | None = None):
        self.states = states or self._default_states()

    @staticmethod
    def _default_states() -> dict[Currency, CurrencyState]:
        return {
            Currency(currency): CurrencyState(
                currency=Currency(currency),
                **params,
            )
            for currency, params in DEFAULT_CURRENCY_STATES.items()
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
            POSITION_PRESSURE_WEIGHT * position_pressure
            + ORDER_FLOW_PRESSURE_WEIGHT * order_flow_imbalance
            + LIQUIDITY_PRESSURE_WEIGHT * liquidity_pressure
        )

        return round(
            max(MIN_PRESSURE, min(MAX_PRESSURE, phi)),
            RATIO_PRECISION
        )

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
                buy_amount=ZERO_FLOAT,
                sell_amount=base_amount,
            )
            self._update_order_flow(
                state=quote_state,
                buy_amount=quote_amount,
                sell_amount=ZERO_FLOAT,
            )

        elif request.side == FXSide.sell:
            base_state.position += base_amount
            quote_state.position -= quote_amount

            self._update_order_flow(
                state=base_state,
                buy_amount=base_amount,
                sell_amount=ZERO_FLOAT,
            )
            self._update_order_flow(
                state=quote_state,
                buy_amount=ZERO_FLOAT,
                sell_amount=quote_amount,
            )

        now = datetime.now(timezone.utc)
        base_state.updated_at = now
        quote_state.updated_at = now

    def apply_market_shock(
        self,
        *,
        volatility_multiplier: float = DEFAULT_STRESS_VOLATILITY_MULTIPLIER,
        hedge_capacity_multiplier: float = (
            DEFAULT_STRESS_HEDGE_CAPACITY_MULTIPLIER
        ),
    ) -> None:
        for state in self.states.values():
            state.market_volatility *= volatility_multiplier
            state.hedge_capacity *= hedge_capacity_multiplier
            state.updated_at = datetime.now(timezone.utc)

    def apply_hedge(
        self, *,
        currency: Currency,
        action: HedgeAction,
        amount: float,
    ):
        if amount <= ZERO_FLOAT:
            return {
                'requested_amount': amount,
                'executed_amount': ZERO_FLOAT,
                'position_before': self.get_state(
                    currency
                ).position,
                'position_after': self.get_state(
                    currency
                ).position,
                'hedge_capacity_before': self.get_state(
                    currency
                ).hedge_capacity,
                'hedge_capacity_after': self.get_state(
                    currency
                ).hedge_capacity,
            }

        state = self.get_state(currency)

        position_before = state.position
        hedge_capacity_before = state.hedge_capacity

        executable_amount = min(
            float(amount),
            max(ZERO_FLOAT, state.hedge_capacity),
        )

        if executable_amount <= ZERO_FLOAT:
            return {
                'requested_amount': amount,
                'executed_amount': ZERO_FLOAT,
                'position_before': position_before,
                'position_after': state.position,
                'hedge_capacity_before': hedge_capacity_before,
                'hedge_capacity_after': state.hedge_capacity,
            }

        if action == HedgeAction.buy:
            state.position += executable_amount
        elif action == HedgeAction.sell:
            state.position -= executable_amount
        else:
            executable_amount = ZERO_FLOAT

        state.hedge_capacity = max(
            ZERO_FLOAT, state.hedge_capacity - executable_amount
        )
        state.updated_at = datetime.now(timezone.utc)

        return {
            'requested_amount': float(amount),
            'executed_amount': round(
                executable_amount,
                EXECUTION_AMOUNT_PRECISION,
            ),
            'position_before': round(
                position_before,
                EXECUTION_AMOUNT_PRECISION,
            ),
            'position_after': round(
                state.position,
                EXECUTION_AMOUNT_PRECISION,
            ),
            'hedge_capacity_before': round(
                hedge_capacity_before,
                EXECUTION_AMOUNT_PRECISION,
            ),
            'hedge_capacity_after': round(
                state.hedge_capacity,
                EXECUTION_AMOUNT_PRECISION,
            ),
        }

    def copy(self):
        copied_states = {
            currency: replace(state)
            for currency, state in self.states.items()
        }

        return InventoryLedger(states=copied_states)

    def project_after_client_fx(
        self, *,
        request: QuoteRequest,
        mid_rate: float,
    ):
        projected_ledger = self.copy()
        projected_ledger.apply_client_fx(
            request=request,
            mid_rate=mid_rate,
        )
        return projected_ledger

    @staticmethod
    def _update_order_flow(
        *,
        state: CurrencyState,
        buy_amount: float,
        sell_amount: float,
        decay: float = ORDER_FLOW_DECAY,
    ) -> None:
        norm_buy = buy_amount / ORDER_FLOW_NORMALIZER
        norm_sell = sell_amount / ORDER_FLOW_NORMALIZER

        state.order_flow_buy_ewma = (
            decay * state.order_flow_buy_ewma
            + (ONE_FLOAT - decay) * norm_buy
        )

        state.order_flow_sell_ewma = (
            decay * state.order_flow_sell_ewma
            + (ONE_FLOAT - decay) * norm_sell
        )

    @staticmethod
    def _div_zero(numerator: float, denominator: float) -> float:
        if abs(denominator) < EPSILON:
            return ZERO_FLOAT
        return numerator / denominator
