import pytest

from revolut_app.fx_lab.risk.hamiltonian import (
    DirectionalHamiltonianController,
    DirectionalHamiltonianControllerParameters,
    HamiltonianBreakdown,
    HamiltonianTransitionEvaluation,
    build_directional_hamiltonian_controller,
    build_selected_hamiltonian_controller,
)
from revolut_app.fx_lab.shared.enums import (
    Currency,
    HamiltonianControllerPreset,
    HamiltonianPreset,
)


def build_breakdown(total: float):
    return HamiltonianBreakdown(
        total=total,
        quadratic=total,
        quartic=0.0,
        coupling=0.0,
        external=0.0,
        local_energy_by_currency={
            currency: 0.0
            for currency in Currency
        },
        gradient_by_currency={
            currency: 0.0
            for currency in Currency
        },
        gradient_l2_norm=0.0,
    )


def test_directional_controller_penalizes_positive_delta_h():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    transition = controller.engine.evaluate_transition(
        pressures_before={
            'EUR': 0.20,
            'GBP': 0.00,
            'USD': 0.00,
        },
        pressures_after={
            'EUR': 0.50,
            'GBP': 0.00,
            'USD': 0.00,
        },
    )

    decision = controller.evaluate(
        transition=transition
    )

    assert decision.delta_h_if_accepted > 0.0
    assert decision.activated is True
    assert decision.applied_adjustment_bps > 0.0


def test_directional_controller_does_not_penalize_reducing_trade():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    transition = controller.engine.evaluate_transition(
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

    decision = controller.evaluate(
        transition=transition
    )

    assert decision.delta_h_if_accepted < 0.0
    assert decision.positive_delta_h == 0.0
    assert decision.raw_adjustment_bps == 0.0
    assert decision.applied_adjustment_bps == 0.0
    assert decision.activated is False


def test_directional_controller_uses_calibrated_gain():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    transition = HamiltonianTransitionEvaluation(
        before=build_breakdown(total=1.0),
        after=build_breakdown(total=1.1),
        delta_total=0.1,
    )

    decision = controller.evaluate(
        transition=transition
    )

    assert decision.raw_adjustment_bps == pytest.approx(
        1.8
    )

    assert decision.applied_adjustment_bps == pytest.approx(
        1.8
    )


def test_directional_controller_caps_adjustment():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    transition = HamiltonianTransitionEvaluation(
        before=build_breakdown(total=1.0),
        after=build_breakdown(total=2.0),
        delta_total=1.0,
    )

    decision = controller.evaluate(
        transition=transition
    )

    assert decision.raw_adjustment_bps == pytest.approx(
        18.0
    )

    assert decision.applied_adjustment_bps == pytest.approx(
        6.0
    )

    assert decision.cap_hit is True


def test_directional_controller_ignores_numerical_delta():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    transition = HamiltonianTransitionEvaluation(
        before=build_breakdown(total=1.0),
        after=build_breakdown(
            total=1.0 + 5e-7
        ),
        delta_total=5e-7,
    )

    decision = controller.evaluate(
        transition=transition
    )

    assert decision.activated is False
    assert decision.applied_adjustment_bps == 0.0


def test_directional_controller_factory():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    assert isinstance(
        controller,
        DirectionalHamiltonianController,
    )

    assert (
        controller.parameters
        .spread_gain_bps_per_delta_energy
        == pytest.approx(18.0)
    )

    assert (
        controller.parameters.max_adjustment_bps
        == pytest.approx(6.0)
    )


def test_directional_controller_default_parameters():
    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1
    )

    assert (
        controller.parameters
        .spread_gain_bps_per_delta_energy
        == pytest.approx(18.0)
    )

    assert (
        controller.parameters.max_adjustment_bps
        == pytest.approx(6.0)
    )


def test_directional_controller_parameter_override():
    parameters = DirectionalHamiltonianControllerParameters(
        spread_gain_bps_per_delta_energy=12.0,
        max_adjustment_bps=4.0,
        delta_h_epsilon=1e-6,
    )

    controller = build_directional_hamiltonian_controller(
        HamiltonianPreset.local_v1,
        parameters=parameters,
    )

    assert controller.parameters == parameters


def test_directional_parameters_rejected_for_symmetric_controller():
    parameters = DirectionalHamiltonianControllerParameters(
        spread_gain_bps_per_delta_energy=12.0,
        max_adjustment_bps=4.0,
        delta_h_epsilon=1e-6,
    )

    with pytest.raises(
        ValueError,
        match='Directional parameters',
    ):
        build_selected_hamiltonian_controller(
            hamiltonian_preset=HamiltonianPreset.local_v1,
            controller_preset=(
                HamiltonianControllerPreset.symmetric_v1
            ),
            directional_parameters=parameters,
        )
