from revolut_app.fx_lab.models import CurrencyState, StressRegime


class StressRegimeDetect:
    def detect(
        self,
        *,
        pressures: dict[str, float],
        states: dict[str, CurrencyState],
    ) -> StressRegime:
        max_abs_pressure = max(
            (abs(value) for value in pressures.values()),
            default=0.0,
        )

        max_volatility = max(
            (state.market_volatility for state in states.values()),
            default=0.0,
        )

        max_limit_utilization = max(
            (state.limit_utilization for state in states.values()),
            default=0.0,
        )

        if (
            max_abs_pressure >= 0.9
            or max_volatility >= 0.045
            or max_limit_utilization >= 0.9
        ):
            return StressRegime.stress
        if (
            max_abs_pressure >= 0.6
            or max_volatility >= 0.025
            or max_limit_utilization >= 0.7
        ):
            return StressRegime.elevated
        return StressRegime.calm

    @staticmethod
    def regime_penalty_bps(regime: StressRegime) -> float:
        if regime == StressRegime.calm:
            return 0.0
        if regime == StressRegime.elevated:
            return 4.0
        if regime == StressRegime.stress:
            return 12.0
