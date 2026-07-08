from math import sqrt

from revolut_app.fx_lab.risk.hamiltonian.models import (
    HamiltonianBreakdown,
    HamiltonianParameters,
    HamiltonianTransitionEvaluation,
)
from revolut_app.fx_lab.shared.enums import Currency


class HamiltonianEngine:
    def __init__(self, parameters: HamiltonianParameters):
        self.parameters = parameters

        self._quadratic = dict(parameters.quadratic)
        self._quartic = dict(parameters.quartic)
        self._external_field = dict(parameters.external_field)

    def evaluate(self, pressures: dict[str, float]):
        phi = {
            currency: (float(pressures.get(currency.value, 0.0)))
            for currency in Currency
        }

        quadratic_energy = 0.0
        quartic_energy = 0.0

        local_energy_by_currency: dict[Currency, float] = {}
        gradient_by_currency = {
            currency: 0.0
            for currency in Currency
        }

        for currency in Currency:
            value = phi[currency]

            quadratic_coefficient = self._quadratic.get(currency, 0.0)
            quartic_coefficient = self._quartic.get(currency, 0.0)

            quadratic_component = quadratic_coefficient * value**2
            quartic_component = quartic_coefficient * value**4

            quadratic_energy += quadratic_component
            quartic_energy += quartic_component

            local_energy_by_currency[currency] = (
                quadratic_component + quartic_component
            )
            gradient_by_currency[currency] += (
                2.0 * quadratic_coefficient * value
                + 4.0 * quartic_coefficient * value**3
            )

        coupling_energy = 0.0

        for coupling in self.parameters.couplings:
            left = coupling.left_currency
            right = coupling.right_currency

            difference = (phi[left] - coupling.relation_sign * phi[right])
            pair_energy = coupling.strength * difference**2
            coupling_energy += pair_energy

            gradient_by_currency[left] += 2.0 * coupling.strength * difference
            gradient_by_currency[right] += (
                -2.0 * coupling.strength
                * coupling.relation_sign
                * difference
            )

        external_energy = 0.0

        for currency in Currency:
            field_value = self._external_field.get(currency, 0.0)
            component = (
                - self.parameters.external_strength
                * field_value
                * phi[currency]
            )

            external_energy += component
            gradient_by_currency[currency] += (
                - self.parameters.external_strength
                * field_value
            )

        total = (
            quadratic_energy
            + quartic_energy
            + coupling_energy
            + external_energy
        )

        gradient_l2_norm = sqrt(
            sum(value**2 for value in gradient_by_currency.values())
        )

        return HamiltonianBreakdown(
            total=total,
            quadratic=quadratic_energy,
            quartic=quartic_energy,
            coupling=coupling_energy,
            external=external_energy,
            local_energy_by_currency=local_energy_by_currency,
            gradient_by_currency=gradient_by_currency,
            gradient_l2_norm=gradient_l2_norm,
        )

    def evaluate_transition(
        self,
        *,
        pressures_before: dict[str, float],
        pressures_after: dict[str, float],
    ):
        before_keys = set(pressures_before)
        after_keys = set(pressures_after)

        if before_keys != after_keys:
            missing_after = sorted(before_keys - after_keys)
            unexpected_after = sorted(after_keys - before_keys)

            raise ValueError(
                'Pressure dimensions do not match: '
                f'missing_after/unexpected_after='
                f'{missing_after}/{unexpected_after}'
            )

        before = self.evaluate(pressures_before)
        after = self.evaluate(pressures_after)

        return HamiltonianTransitionEvaluation(
            before=before,
            after=after,
            delta_total=after.total - before.total,
        )
