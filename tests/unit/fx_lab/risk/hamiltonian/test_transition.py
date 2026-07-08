import pytest

from revolut_app.fx_lab.risk.hamiltonian.presets import (
    build_hamiltonian_engine,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)


def test_equal_states_have_zero_delta_h():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    pressures = {
        'EUR': 0.40,
        'GBP': -0.20,
        'USD': 0.10,
    }

    transition = engine.evaluate_transition(
        pressures_before=pressures,
        pressures_after=pressures,
    )

    assert transition.h_before == pytest.approx(
        transition.h_after
    )
    assert transition.delta_total == pytest.approx(
        0.0
    )
    assert transition.is_risk_increasing is False
    assert transition.is_risk_reducing is False


def test_moving_away_from_zero_increases_hamiltonian():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    transition = engine.evaluate_transition(
        pressures_before={
            'EUR': 0.10,
            'GBP': 0.00,
            'USD': 0.00,
        },
        pressures_after={
            'EUR': 0.60,
            'GBP': 0.00,
            'USD': 0.00,
        },
    )

    assert transition.delta_total > 0.0
    assert transition.is_risk_increasing is True
    assert transition.is_risk_reducing is False


def test_moving_toward_zero_reduces_hamiltonian():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    transition = engine.evaluate_transition(
        pressures_before={
            'EUR': 0.70,
            'GBP': 0.00,
            'USD': 0.00,
        },
        pressures_after={
            'EUR': 0.30,
            'GBP': 0.00,
            'USD': 0.00,
        },
    )

    assert transition.delta_total < 0.0
    assert transition.is_risk_increasing is False
    assert transition.is_risk_reducing is True


def test_transition_delta_matches_independent_evaluations():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    before_pressures = {
        'EUR': 0.30,
        'GBP': -0.20,
        'USD': 0.15,
    }

    after_pressures = {
        'EUR': 0.45,
        'GBP': -0.10,
        'USD': 0.05,
    }

    before = engine.evaluate(before_pressures)
    after = engine.evaluate(after_pressures)

    transition = engine.evaluate_transition(
        pressures_before=before_pressures,
        pressures_after=after_pressures,
    )

    assert transition.before == before
    assert transition.after == after
    assert transition.delta_total == pytest.approx(
        after.total - before.total
    )


def test_transition_rejects_different_pressure_dimensions():
    engine = build_hamiltonian_engine(
        HamiltonianPreset.local_v1
    )

    with pytest.raises(
        ValueError,
        match='Pressure dimensions do not match',
    ):
        engine.evaluate_transition(
            pressures_before={
                'EUR': 0.20,
                'GBP': 0.10,
                'USD': 0.00,
            },
            pressures_after={
                'EUR': 0.30,
                'GBP': 0.10,
            },
        )
