from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

from revolut_app.fx_lab.constants import EPSILON
from revolut_app.fx_lab.models import Currency, HamiltonianPreset


@dataclass(frozen=True)
class SignedCoupling:
    left_currency: Currency
    right_currency: Currency
    strength: float
    relation_sign: float

    def __post_init__(self):
        if self.left_currency == self.right_currency:
            raise ValueError(
                'Hamiltonian coupling requires two currencies'
            )
        if self.strength < 0.0:
            raise ValueError(
                'Hamiltonian coupling strength must be non-negative'
            )
        if self.relation_sign not in {-1, 1}:
            raise ValueError(
                'Hamiltonian relation_sign must be either -1 or 1'
            )


@dataclass(frozen=True)
class HamiltonianParameters:
    preset_name: str

    quadratic: dict[Currency, float]
    quartic: dict[Currency, float]

    couplings: tuple[SignedCoupling, ...] = ()

    external_field: dict[Currency, float] = field(default_factory=dict)
    external_strength: float = 0.0

    def __post_init__(self):
        if self.external_strength < 0.0:
            raise ValueError(
                'Hamiltonian external strength must be non-negative'
            )

    @classmethod
    def threshold_v1(
        cls, *,
        elevated_pressure: float = 0.6,
        stress_pressure: float = 0.9,
        elevated_energy: float = 1.0,
        stress_energy: float = 3.0,
    ) -> HamiltonianParameters:
        elevated_squared = elevated_pressure**2
        elevated_fourth = elevated_pressure**4

        stress_squared = stress_pressure**2
        stress_fourth = stress_pressure**4

        determinant = (
            elevated_squared * stress_fourth
            - elevated_fourth * stress_squared
        )

        if abs(determinant) < EPSILON:
            raise ValueError(
                'Hamiltonian threshold calibration is singular'
            )

        quadratic_coefficient = (
            elevated_energy * stress_fourth
            - stress_energy * elevated_fourth
        ) / determinant
        quartic_coefficient = (
            elevated_squared * stress_energy
            - stress_squared * elevated_energy
        ) / determinant

        if quadratic_coefficient < 0.0:
            raise ValueError(
                'Calibrated quadratic coefficient is negative'
            )
        if quartic_coefficient <= 0.0:
            raise ValueError(
                'Calibrated quartic coefficient is non-positive'
            )
        currencies = tuple(Currency)
        return cls(
            preset_name='threshold-local-v1',
            quadratic={
                currency: quadratic_coefficient
                for currency in currencies
            },
            quartic={
                currency: quartic_coefficient
                for currency in currencies
            },
            couplings=(),
            external_field={
                currency: 0.0
                for currency in currencies
            },
            external_strength=0.0,
        )

    @classmethod
    def threshold_coupled_v1(
        cls, *,
        elevated_pressure: float = 0.6,
        stress_pressure: float = 0.9,
        elevated_energy: float = 1.0,
        stress_energy: float = 3.0,
        coupling_strength: float = 0.2,
        relation_signs: dict[tuple[Currency, Currency], int] | None = None,
    ) -> HamiltonianParameters:
        if relation_signs is None:
            relation_signs = {
                (Currency.EUR, Currency.GBP): 1,
                (Currency.EUR, Currency.USD): -1,
                (Currency.GBP, Currency.USD): -1,
            }

        local_parameters = cls.threshold_v1(
            elevated_pressure=elevated_pressure,
            stress_pressure=stress_pressure,
            elevated_energy=elevated_energy,
            stress_energy=stress_energy,
        )

        expected_pairs = {
            (Currency.EUR, Currency.GBP),
            (Currency.EUR, Currency.USD),
            (Currency.GBP, Currency.USD),
        }

        if set(relation_signs) != expected_pairs:
            raise ValueError(
                'relation_signs must contain exactly the expected pairs'
            )

        couplings = tuple(
            SignedCoupling(
                left_currency=left,
                right_currency=right,
                strength=coupling_strength,
                relation_sign=relation_sign,
            )
            for (left, right), relation_sign in relation_signs.items()
        )

        return cls(
            preset_name='threshold-coupled-v1',
            quadratic=local_parameters.quadratic,
            quartic=local_parameters.quartic,
            couplings=couplings,
            external_field=local_parameters.external_field,
            external_strength=0.0,
        )

    def as_dict(self):
        return {
            'preset_name': self.preset_name,
            'quadratic': {
                currency.value: value
                for currency, value in self.quadratic.items()
            },
            'quartic': {
                currency.value: value
                for currency, value in self.quartic.items()
            },
            'couplings': [
                {
                    'left_currency': (
                        coupling.left_currency.value
                    ),
                    'right_currency': (
                        coupling.right_currency.value
                    ),
                    'strength': (
                        coupling.strength
                    ),
                    'relation_sign': (
                        coupling.relation_sign
                    ),
                }
                for coupling in self.couplings
            ],
            'external_field': {
                currency.value: value
                for currency, value in self.external_field.items()
            },
            'external_strength': self.external_strength,
        }


@dataclass(frozen=True)
class HamiltonianBreakdown:
    total: float

    quadratic: float
    quartic: float
    coupling: float
    external: float

    local_energy_by_currency: dict[Currency, float]
    gradient_by_currency: dict[Currency, float]

    gradient_l2_norm: float


class HamiltonianEngine:
    def __init__(self, parameters: HamiltonianParameters):
        self.parameters = parameters

        self._quadratic = dict(parameters.quadratic)
        self._quartic = dict(parameters.quartic)
        self._external_field = dict(parameters.external_field)

    def evaluate(self, pressures: dict[str, float]) -> HamiltonianBreakdown:
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


@dataclass(frozen=True)
class HamiltonianControlDecision:
    h_total: float
    activation_energy: float

    raw_adjustment_bps: float
    applied_adjustment_bps: float

    activated: bool


@dataclass(frozen=True)
class HamiltonianControllerParameters:
    activation_energy: float = 0.7
    spread_gain_bps_per_energy: float = 2.0
    max_adjustment_bps: float = 8.0

    def __post_init__(self):
        if self.activation_energy < 0.0:
            raise ValueError(
                'activation_energy must be positive'
            )
        if self.spread_gain_bps_per_energy < 0.0:
            raise ValueError(
                'spread_gain_bps_per_energy must be positive'
            )
        if self.max_adjustment_bps < 0.0:
            raise ValueError(
                'max_adjustment_bps must be positive'
            )


def build_hamiltonian_parameters(
    preset: HamiltonianPreset,
) -> HamiltonianParameters:
    if preset == HamiltonianPreset.local_v1:
        return HamiltonianParameters.threshold_v1()
    if preset == HamiltonianPreset.coupled_v1:
        return HamiltonianParameters.threshold_coupled_v1()

    raise ValueError(
        f'Unsupported Hamiltonian preset: {preset}'
    )


def build_hamiltonian_engine(
    preset: HamiltonianPreset,
) -> HamiltonianEngine:
    return HamiltonianEngine(
        parameters=build_hamiltonian_parameters(preset)
    )
