import pytest
from pydantic import ValidationError

from revolut_app.api_service.schemas.fx import PolicyComparisonRequest


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
