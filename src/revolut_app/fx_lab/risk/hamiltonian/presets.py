from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.risk.hamiltonian.controller import (
    HamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.models import (
    HamiltonianParameters,
    HamiltonianControllerParameters,
)
from revolut_app.fx_lab.shared.enums import HamiltonianPreset
from revolut_app.fx_lab.risk.hamiltonian.directional_controller import (
    DirectionalHamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.models import (
    DirectionalHamiltonianControllerParameters,
)


def build_directional_hamiltonian_controller(preset: HamiltonianPreset):
    if preset != HamiltonianPreset.local_v1:
        raise ValueError(
            "Directional controller v2 currently "
            "supports only local-v1"
        )

    return DirectionalHamiltonianController(
        engine=build_hamiltonian_engine(preset),
        parameters=(
            DirectionalHamiltonianControllerParameters(
                spread_gain_bps_per_delta_energy=18.0,
                max_adjustment_bps=6.0,
                delta_h_epsilon=1e-6,
            )
        ),
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


def build_hamiltonian_controller(
    preset: HamiltonianPreset,
) -> HamiltonianController:
    if preset != HamiltonianPreset.local_v1:
        raise ValueError(
            'Controller v1 supports only local_v1'
        )
    return HamiltonianController(
        engine=build_hamiltonian_engine(preset),
        parameters=HamiltonianControllerParameters(
            activation_energy=0.7,
            spread_gain_bps_per_energy=2.0,
            max_adjustment_bps=8.0,
        ),
    )
