from .engine import HamiltonianEngine
from .models import (
    DirectionalHamiltonianControlDecision,
    DirectionalHamiltonianControllerParameters,
    HamiltonianTransitionEvaluation,
)


class DirectionalHamiltonianController:
    def __init__(
        self, *,
        engine: HamiltonianEngine,
        parameters: DirectionalHamiltonianControllerParameters,
    ):
        self.engine = engine
        self.parameters = parameters

    def evaluate(
        self, *,
        transition: HamiltonianTransitionEvaluation,
    ):
        delta_h = transition.delta_total

        if delta_h <= self.parameters.delta_h_epsilon:
            positive_delta_h = 0.0
        else:
            positive_delta_h = delta_h

        raw_adjustment_bps = (
            positive_delta_h
            * self.parameters.spread_gain_bps_per_delta_energy
        )
        applied_adjustment_bps = min(
            raw_adjustment_bps,
            self.parameters.max_adjustment_bps,
        )

        return DirectionalHamiltonianControlDecision(
            h_before=transition.h_before,
            h_after_if_accepted=transition.h_after,
            delta_h_if_accepted=delta_h,
            positive_delta_h=positive_delta_h,
            raw_adjustment_bps=raw_adjustment_bps,
            applied_adjustment_bps=applied_adjustment_bps,
            activated=applied_adjustment_bps > 0.0,
            cap_hit=(
                raw_adjustment_bps
                > self.parameters.max_adjustment_bps
            ),
        )
