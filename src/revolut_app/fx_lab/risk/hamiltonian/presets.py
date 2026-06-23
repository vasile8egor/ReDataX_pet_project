from revolut_app.fx_lab.risk.hamiltonian.engine import HamiltonianEngine
from revolut_app.fx_lab.risk.hamiltonian.models import HamiltonianParameters
from revolut_app.fx_lab.shared.enums import HamiltonianPreset


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
