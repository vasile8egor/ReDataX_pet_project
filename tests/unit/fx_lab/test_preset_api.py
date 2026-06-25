import pytest
from pydantic import ValidationError

from revolut_app.api_service.schemas.fx import PolicyComparisonRequest
from revolut_app.fx_lab.experiments.models import PhysicsMode
from revolut_app.fx_lab.shared.enums import (
    HamiltonianControllerPreset,
    HamiltonianPreset,
)


def test_none_mode_rejects_hamiltonian_preset():
    with pytest.raises(
        ValidationError,
        match='hamiltonian_preset must be null',
    ):
        PolicyComparisonRequest.model_validate(
            {
                'physics_mode': 'none',
                'hamiltonian_preset': 'coupled-v1',
            }
        )


def test_observer_requires_hamiltonian_preset():
    with pytest.raises(
        ValidationError,
        match='hamiltonian_preset is required',
    ):
        PolicyComparisonRequest.model_validate(
            {
                'physics_mode': 'observer',
            }
        )


def test_coupled_observer_request_is_valid():
    request = PolicyComparisonRequest.model_validate(
        {
            'policies': [
                'naive',
                'inventory_aware',
            ],
            'steps': 10,
            'base_intensity': 0.2,
            'physics_mode': 'observer',
            'hamiltonian_preset': 'coupled-v1',
            'persist_result': False,
        }
    )

    assert request.hamiltonian_preset.value == 'coupled-v1'


def test_controller_defaults_to_symmetric_v1():
    request = PolicyComparisonRequest(
        physics_mode=PhysicsMode.controller,
        hamiltonian_preset=HamiltonianPreset.local_v1,
    )

    assert (
        request.controller_preset
        == HamiltonianControllerPreset.symmetric_v1
    )


def test_directional_controller_preset_request_is_valid():
    request = PolicyComparisonRequest.model_validate(
        {
            'policies': [
                'naive',
                'inventory_aware',
            ],
            'physics_mode': 'controller',
            'hamiltonian_preset': 'local-v1',
            'controller_preset': 'directional-v2',
        }
    )

    assert (
        request.controller_preset
        == HamiltonianControllerPreset.directional_v2
    )


def test_directional_controller_parameter_request_is_valid():
    request = PolicyComparisonRequest(
        physics_mode=PhysicsMode.controller,
        hamiltonian_preset=HamiltonianPreset.local_v1,
        controller_preset=(
            HamiltonianControllerPreset.directional_v2
        ),
        directional_controller_parameters={
            'spread_gain_bps_per_delta_energy': 12.0,
            'max_adjustment_bps': 4.0,
            'delta_h_epsilon': 1e-6,
        },
    )

    assert (
        request.directional_controller_parameters
        .spread_gain_bps_per_delta_energy
        == pytest.approx(12.0)
    )
    assert (
        request.directional_controller_parameters
        .max_adjustment_bps
        == pytest.approx(4.0)
    )
    assert (
        request.directional_controller_parameters
        .delta_h_epsilon
        == pytest.approx(1e-6)
    )
