from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.risk.hamiltonian.controller import (
    HamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.models import (
    HamiltonianParameters,
    HamiltonianControllerParameters,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
    HamiltonianControllerPreset,
)
from revolut_app.fx_lab.risk.hamiltonian.directional_controller import (
    DirectionalHamiltonianController,
)
from revolut_app.fx_lab.risk.hamiltonian.models import (
    DirectionalHamiltonianControllerParameters,
)


def build_directional_hamiltonian_controller(
    preset: HamiltonianPreset,
    parameters: (
        DirectionalHamiltonianControllerParameters | None
    ) = None,
):
    if preset != HamiltonianPreset.local_v1:
        raise ValueError(
            'Directional controller v2 supports only local-v1'
        )
    resolved_parameters = (
        parameters if parameters is not None
        else DirectionalHamiltonianControllerParameters(
            spread_gain_bps_per_delta_energy=18.0,
            max_adjustment_bps=6.0,
            delta_h_epsilon=1e-6,
        )
    )
    return DirectionalHamiltonianController(
        engine=build_hamiltonian_engine(preset),
        parameters=resolved_parameters,
    )


def build_selected_hamiltonian_controller(
    hamiltonian_preset: HamiltonianPreset,
    controller_preset: HamiltonianControllerPreset,
    directional_parameters: (
        DirectionalHamiltonianControllerParameters | None
    ) = None,
):
    if (
        controller_preset == HamiltonianControllerPreset.symmetric_v1
    ):
        if directional_parameters is not None:
            raise ValueError(
                'Directional parameters cant be used with symmetric-v1'
            )
        return build_hamiltonian_controller(hamiltonian_preset)

    if (
        controller_preset == HamiltonianControllerPreset.directional_v2
    ):
        return build_directional_hamiltonian_controller(
            hamiltonian_preset,
            parameters=directional_parameters
        )

    raise ValueError(
        'Unsupported Hamiltonian controller preset: '
        f'''{controller_preset}'''
    )


def build_hamiltonian_parameters(
    preset: HamiltonianPreset,
):
    if preset == HamiltonianPreset.local_v1:
        return HamiltonianParameters.threshold_v1()
    if preset == HamiltonianPreset.coupled_v1:
        return HamiltonianParameters.threshold_coupled_v1()

    raise ValueError(
        f'Unsupported Hamiltonian preset: {preset}'
    )


def build_hamiltonian_engine(
    preset: HamiltonianPreset,
):
    return HamiltonianEngine(
        parameters=build_hamiltonian_parameters(preset)
    )


def build_hamiltonian_controller(
    preset: HamiltonianPreset,
):
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
