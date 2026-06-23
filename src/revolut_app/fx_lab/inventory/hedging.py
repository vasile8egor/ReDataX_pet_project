from dataclasses import dataclass
from enum import Enum

from revolut_app.fx_lab.inventory.models import CurrencyState
from revolut_app.fx_lab.shared.enums import Currency, StressRegime
from revolut_app.fx_lab.shared.constants import (
    AMOUNT_PRECISION,
    DEFAULT_HEDGE_PRESSURE_THRESHOLD,
    DEFAULT_HEDGE_TARGET_PRESSURE,
    DEFAULT_MAX_HEDGE_FRACTION,
    DEFAULT_MIN_HEDGE_NOTIONAL,
    ELEVATED_HEDGE_PRESSURE_THRESHOLD,
    EPSILON,
    POSITION_PRECISION,
    RATIO_PRECISION,
    STRESS_HEDGE_PRESSURE_THRESHOLD,
    ZERO_FLOAT,
)


class HedgeAction(str, Enum):
    buy = 'buy'
    sell = 'sell'
    hold = 'hold'


@dataclass(frozen=True)
class HedgeRecommendation:
    currency: Currency
    action: HedgeAction
    amount: float
    desired_amount: float
    capacity_limited: bool
    unhedged_amount: float
    current_position: float
    position_limit: float
    current_pressure: float
    threshold: float
    target_pressure: float
    expected_pressure_reduction: float
    reason: str


@dataclass(frozen=True)
class HedgeAmountDecision:
    amount: float
    desired_amount: float
    capacity_limited: bool
    unhedged_amount: float


@dataclass(frozen=True)
class HedgeRecommendationResult:
    regime: StressRegime
    pressure_threshold: float
    target_pressure: float
    recommendations: list[HedgeRecommendation]


class HedgeEngine:
    def recommend(
        self, *,
        pressures: dict[str, float],
        states: dict[Currency, CurrencyState],
        regime: StressRegime,
        pressure_threshold: float = DEFAULT_HEDGE_PRESSURE_THRESHOLD,
        target_pressure: float = DEFAULT_HEDGE_TARGET_PRESSURE,
        max_hedge_fraction: float = DEFAULT_MAX_HEDGE_FRACTION,
        min_notional: float = DEFAULT_MIN_HEDGE_NOTIONAL,
    ) -> HedgeRecommendationResult:

        effective_threshold = self._effective_threshold(
            base_threshold=pressure_threshold,
            regime=regime,
        )

        recommendations: list[HedgeRecommendation] = []

        for currency, state in states.items():
            phi = pressures.get(currency.value, ZERO_FLOAT)

            if abs(phi) < effective_threshold:
                continue
            if abs(state.position) < min_notional:
                continue
            if state.hedge_capacity < min_notional:
                continue

            action = self._action_from_pressure(phi)
            decision = self._hedge_amount(
                phi=phi,
                state=state,
                target_pressure=target_pressure,
                max_hedge_fraction=max_hedge_fraction,
                min_notional=min_notional,
            )

            if decision.amount < min_notional:
                continue

            expected_reduction = max(ZERO_FLOAT, abs(phi) - target_pressure)

            recommendations.append(
                HedgeRecommendation(
                    currency=currency,
                    action=action,
                    amount=round(decision.amount, AMOUNT_PRECISION),
                    desired_amount=round(
                        decision.desired_amount,
                        AMOUNT_PRECISION
                    ),
                    capacity_limited=decision.capacity_limited,
                    unhedged_amount=round(
                        decision.unhedged_amount,
                        AMOUNT_PRECISION
                    ),
                    current_position=round(state.position, POSITION_PRECISION),
                    position_limit=round(
                        state.position_limit,
                        POSITION_PRECISION
                    ),
                    current_pressure=round(phi, RATIO_PRECISION),
                    threshold=round(effective_threshold, RATIO_PRECISION),
                    target_pressure=round(target_pressure, RATIO_PRECISION),
                    expected_pressure_reduction=round(
                        expected_reduction,
                        RATIO_PRECISION,
                    ),
                    reason=self._reason(
                        phi=phi,
                        currency=currency,
                        regime=regime,
                    ),
                )
            )
        return HedgeRecommendationResult(
            regime=regime,
            pressure_threshold=round(effective_threshold, RATIO_PRECISION),
            target_pressure=target_pressure,
            recommendations=recommendations,
        )

    @staticmethod
    def _reason(phi: float, currency: Currency, regime: StressRegime) -> str:
        if phi > 0:
            inventory_side = (
                f"positive inventory pressure: bank is long {currency.value};"
                f" recommend: play SELL {currency.value}"
            )
        elif phi < 0:
            inventory_side = (
                f"negative inventory pressure: bank is short {currency.value};"
                f" recommend: play BUY {currency.value}"
            )
        else:
            inventory_side = (
                f"neutral inventory pressure for {currency.value}; "
                "recommend: play HOLD"
            )
        return (
            f'{inventory_side}; regime={regime.value}'
        )

    @staticmethod
    def _hedge_amount(
        phi: float,
        state: CurrencyState,
        target_pressure: float,
        max_hedge_fraction: float,
        min_notional: float,
    ) -> HedgeAmountDecision:
        current_abs_phi = abs(phi)

        if current_abs_phi <= target_pressure:
            return HedgeAmountDecision(
                amount=ZERO_FLOAT,
                desired_amount=ZERO_FLOAT,
                capacity_limited=False,
                unhedged_amount=ZERO_FLOAT,
            )

        pressure_excess_ratio = (current_abs_phi - target_pressure) / max(
            current_abs_phi,
            EPSILON,
        )
        desired_amount = abs(state.position) * pressure_excess_ratio
        max_by_position = abs(state.position) * max_hedge_fraction
        max_by_capacity = abs(state.hedge_capacity)

        amount = min(
            desired_amount,
            max_by_position,
            max_by_capacity,
        )

        if amount < min_notional:
            return HedgeAmountDecision(
                amount=ZERO_FLOAT,
                desired_amount=desired_amount,
                capacity_limited=amount < desired_amount,
                unhedged_amount=desired_amount,
            )

        unhedged_amount = max(ZERO_FLOAT, desired_amount - amount)

        return HedgeAmountDecision(
            amount=amount,
            desired_amount=desired_amount,
            capacity_limited=amount < desired_amount,
            unhedged_amount=unhedged_amount,
        )

    @staticmethod
    def _effective_threshold(*, base_threshold: float, regime: StressRegime):
        if regime == StressRegime.stress:
            return min(base_threshold, STRESS_HEDGE_PRESSURE_THRESHOLD)
        if regime == StressRegime.elevated:
            return min(base_threshold, ELEVATED_HEDGE_PRESSURE_THRESHOLD)
        return base_threshold

    @staticmethod
    def _action_from_pressure(phi: float) -> HedgeAction:
        if phi > 0:
            return HedgeAction.sell
        if phi < 0:
            return HedgeAction.buy
        return HedgeAction.hold
