from revolut_app.fx_lab.shared.constants import (
    CALM_REGIME_PENALTY_BPS,
    ELEVATED_LIMIT_UTILIZATION_THRESHOLD,
    ELEVATED_PRESSURE_THRESHOLD,
    ELEVATED_REGIME_PENALTY_BPS,
    ELEVATED_VOLATILITY_THRESHOLD,
    STRESS_LIMIT_UTILIZATION_THRESHOLD,
    STRESS_PRESSURE_THRESHOLD,
    STRESS_REGIME_PENALTY_BPS,
    STRESS_VOLATILITY_THRESHOLD,
    ZERO_FLOAT,
)
from revolut_app.fx_lab.inventory.models import CurrencyState
from revolut_app.fx_lab.shared.enums import StressRegime


class StressRegimeDetect:
    def detect(
        self,
        *,
        pressures: dict[str, float],
        states: dict[str, CurrencyState],
    ) -> StressRegime:
        max_abs_pressure = max(
            (abs(value) for value in pressures.values()),
            default=ZERO_FLOAT,
        )

        max_volatility = max(
            (state.market_volatility for state in states.values()),
            default=ZERO_FLOAT,
        )

        max_limit_utilization = max(
            (state.limit_utilization for state in states.values()),
            default=ZERO_FLOAT,
        )

        if (
            max_abs_pressure >= STRESS_PRESSURE_THRESHOLD
            or max_volatility >= STRESS_VOLATILITY_THRESHOLD
            or max_limit_utilization >= STRESS_LIMIT_UTILIZATION_THRESHOLD
        ):
            return StressRegime.stress
        if (
            max_abs_pressure >= ELEVATED_PRESSURE_THRESHOLD
            or max_volatility >= ELEVATED_VOLATILITY_THRESHOLD
            or max_limit_utilization >= ELEVATED_LIMIT_UTILIZATION_THRESHOLD
        ):
            return StressRegime.elevated
        return StressRegime.calm

    @staticmethod
    def regime_penalty_bps(regime: StressRegime) -> float:
        if regime == StressRegime.calm:
            return CALM_REGIME_PENALTY_BPS
        if regime == StressRegime.elevated:
            return ELEVATED_REGIME_PENALTY_BPS
        if regime == StressRegime.stress:
            return STRESS_REGIME_PENALTY_BPS
        return CALM_REGIME_PENALTY_BPS
