from collections import deque
from collections.abc import Mapping
from math import isfinite

from revolut_app.fx_lab.risk.rg.models import (
    EffectiveHamiltonianCoefficients,
    ScaleAwareTransition,
)


class RollingPressureWindow:
    def __init__(
        self,
        *,
        currencies: tuple[str, ...],
        block_size: int,
    ):
        if not currencies:
            raise ValueError(
                'currencies cannot be empty'
            )

        if len(set(currencies)) != len(
            currencies
        ):
            raise ValueError(
                'currencies must be unique'
            )

        if block_size <= 0:
            raise ValueError(
                'block_size must be positive'
            )

        self.currencies = currencies
        self.block_size = block_size

        self._frames: deque[
            dict[str, float]
        ] = deque(maxlen=block_size)

        self._sums = {
            currency: 0.0
            for currency in currencies
        }

    @property
    def is_ready(self):
        return (
            len(self._frames)
            == self.block_size
        )

    @property
    def frame_count(self):
        return len(self._frames)

    def append(
        self,
        pressures: Mapping[str, float],
    ):
        resolved = self._validate_pressures(
            pressures
        )

        if self.is_ready:
            oldest = self._frames[0]

            for currency in self.currencies:
                self._sums[currency] -= (
                    oldest[currency]
                )

        self._frames.append(resolved)

        for currency in self.currencies:
            self._sums[currency] += (
                resolved[currency]
            )

    def mean_pressures(
        self,
    ):
        if not self.is_ready:
            raise ValueError(
                'Rolling pressure window '
                'is not ready'
            )

        return {
            currency: (
                self._sums[currency]
                / self.block_size
            )
            for currency in self.currencies
        }

    def projected_next_mean(
        self,
        *,
        projected_pressures: Mapping[
            str,
            float,
        ],
    ):
        if not self.is_ready:
            raise ValueError(
                'Rolling pressure window '
                'is not ready'
            )

        projected = self._validate_pressures(
            projected_pressures
        )

        oldest = self._frames[0]

        return {
            currency: (
                self._sums[currency]
                - oldest[currency]
                + projected[currency]
            )
            / self.block_size
            for currency in self.currencies
        }

    def _validate_pressures(
        self,
        pressures: Mapping[str, float],
    ):
        if set(pressures) != set(
            self.currencies
        ):
            raise ValueError(
                'Pressure dimensions do not match: '
                f'''expected={sorted(self.currencies)}, '''
                f'''actual={sorted(pressures)}'''
            )

        resolved = {
            currency: float(
                pressures[currency]
            )
            for currency in self.currencies
        }

        for currency, value in (
            resolved.items()
        ):
            if not isfinite(value):
                raise ValueError(
                    'Pressure must be finite: '
                    f'''currency={currency}, '''
                    f'''value={value}'''
                )

        return resolved


class EffectiveHamiltonianEvaluator:
    def __init__(
        self,
        *,
        coefficients:
            EffectiveHamiltonianCoefficients,
    ):
        self.coefficients = coefficients

    def evaluate(
        self,
        pressures: Mapping[str, float],
    ):
        quadratic_invariant = sum(
            value**2
            for value in pressures.values()
        )

        quartic_invariant = sum(
            value**4
            for value in pressures.values()
        )

        return (
            self.coefficients.intercept
            + self.coefficients.quadratic
            * quadratic_invariant
            + self.coefficients.quartic
            * quartic_invariant
        )


class ScaleAwareTransitionEvaluator:
    def __init__(
        self, *,
        pressure_window: RollingPressureWindow,
        hamiltonian: EffectiveHamiltonianEvaluator,
    ):
        if (
            pressure_window.block_size
            != hamiltonian
            .coefficients.block_size
        ):
            raise ValueError(
                'Pressure window and effective '
                'Hamiltonian must have the same '
                'block size'
            )

        self.pressure_window = (
            pressure_window
        )
        self.hamiltonian = hamiltonian

    def evaluate_projected_transition(
        self, *,
        current_pressures: Mapping[str, float],
        projected_pressures: Mapping[str, float],
    ):
        block_size = self.pressure_window.block_size

        if not self.pressure_window.is_ready:
            return ScaleAwareTransition(
                block_size=block_size,
                history_ready=False,
                coarse_pressure_before={},
                coarse_pressure_after_if_rejected={},
                coarse_pressure_after_if_accepted={},
                coarse_h_before=0.0,
                coarse_h_after_if_rejected=0.0,
                coarse_h_after_if_accepted=0.0,
                temporal_drift_delta_h=0.0,
                request_delta_h=0.0,
                total_accepted_delta_h=0.0,
                normalized_temporal_drift_delta_h=0.0,
                normalized_request_delta_h=0.0,
                normalized_total_accepted_delta_h=0.0,
            )

        coarse_before = self.pressure_window.mean_pressures()

        coarse_after_if_rejected = (
            self.pressure_window.projected_next_mean(
                projected_pressures=current_pressures
            )
        )
        coarse_after_if_accepted = (
            self.pressure_window.projected_next_mean(
                projected_pressures=projected_pressures
            )
        )

        h_before = self.hamiltonian.evaluate(
            coarse_before
        )

        h_after_if_rejected = self.hamiltonian.evaluate(
            coarse_after_if_rejected
        )
        h_after_if_accepted = self.hamiltonian.evaluate(
            coarse_after_if_accepted
        )
        temporal_drift_delta_h = (
            h_after_if_rejected - h_before
        )

        request_delta_h = (
            h_after_if_accepted
            - h_after_if_rejected
        )

        total_accepted_delta_h = (
            h_after_if_accepted - h_before
        )

        return ScaleAwareTransition(
            block_size=block_size,
            history_ready=True,
            coarse_pressure_before=coarse_before,
            coarse_pressure_after_if_rejected=(
                coarse_after_if_rejected
            ),
            coarse_pressure_after_if_accepted=(
                coarse_after_if_accepted
            ),
            coarse_h_before=h_before,
            coarse_h_after_if_rejected=(
                h_after_if_rejected
            ),
            coarse_h_after_if_accepted=(
                h_after_if_accepted
            ),
            temporal_drift_delta_h=(
                temporal_drift_delta_h
            ),
            request_delta_h=request_delta_h,
            total_accepted_delta_h=(
                total_accepted_delta_h
            ),
            normalized_temporal_drift_delta_h=(
                block_size
                * temporal_drift_delta_h
            ),
            normalized_request_delta_h=(
                block_size * request_delta_h
            ),
            normalized_total_accepted_delta_h=(
                block_size
                * total_accepted_delta_h
            ),
        )

    def commit(
        self, *,
        actual_pressures: Mapping[str, float],
    ):
        self.pressure_window.append(actual_pressures)
