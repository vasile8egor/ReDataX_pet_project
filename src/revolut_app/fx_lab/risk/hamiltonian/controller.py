from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.risk.hamiltonian.models import (
    HamiltonianControlDecision,
    HamiltonianControllerParameters,
)


class HamiltonianController:
    def __init__(
        self, *,
        engine: HamiltonianEngine,
        parameters: HamiltonianControllerParameters
    ):
        self.engine = engine
        self.parameters = parameters

    def evalute(self, *, pressures: dict[str, float],):
        breakdown = self.engine.evaluate(pressures)
        excess_energy = max(
            0.0, (
                breakdown.total - self.parameters.activation_energy
            ),
        )

        raw_adjustment_bps = (
            self.parameters.spread_gain_bps_per_energy
            * excess_energy
        )
        applied_adjustment_bps = min(
            raw_adjustment_bps, self.parameters.max_adjustment_bps
        )

        return (
            breakdown,
            HamiltonianControlDecision(
                h_total=breakdown.total,
                activation_energy=self.parameters.activation_energy,
                raw_adjustment_bps=raw_adjustment_bps,
                applied_adjustment_bps=applied_adjustment_bps,
                activated=(
                    True if applied_adjustment_bps > 0.0
                    else False
                ),
            ),
        )
