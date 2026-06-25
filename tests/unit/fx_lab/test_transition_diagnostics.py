import pytest

from revolut_app.fx_lab.risk.rg import (
    ScaleAwareTransition,
    TransitionRiskSign,
    build_scale_aware_transition_diagnostic,
    classify_transition_sign,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.2, TransitionRiskSign.POSITIVE),
        (-0.2, TransitionRiskSign.NEGATIVE),
        (0.0, TransitionRiskSign.ZERO),
        (5e-7, TransitionRiskSign.ZERO),
        (-5e-7, TransitionRiskSign.ZERO),
    ],
)
def test_classifies_transition_sign(
    value,
    expected,
):
    assert classify_transition_sign(
        value,
        epsilon=1e-6,
    ) == expected


def test_builds_agreeing_positive_diagnostic():
    coarse = ScaleAwareTransition(
        block_size=16,
        history_ready=True,
        coarse_pressure_before={
            "EUR": 0.1,
        },
        coarse_pressure_after_if_rejected={
            "EUR": 0.1,
        },
        coarse_pressure_after_if_accepted={
            "EUR": 0.2,
        },
        coarse_h_before=0.1,
        coarse_h_after_if_rejected=0.11,
        coarse_h_after_if_accepted=0.12,
        temporal_drift_delta_h=0.01,
        request_delta_h=0.01,
        total_accepted_delta_h=0.02,
        normalized_temporal_drift_delta_h=0.16,
        normalized_request_delta_h=0.16,
        normalized_total_accepted_delta_h=0.32,
    )

    diagnostic = (
        build_scale_aware_transition_diagnostic(
            event_index=17,
            request_accepted=True,
            local_h_before=0.3,
            local_projected_h_after=0.4,
            coarse_transition=coarse,
        )
    )

    assert diagnostic.local_sign == (
        TransitionRiskSign.POSITIVE
    )

    assert diagnostic.coarse_sign == (
        TransitionRiskSign.POSITIVE
    )

    assert diagnostic.sign_agreement is True


def test_history_not_ready_has_zero_coarse_sign():
    coarse = ScaleAwareTransition(
        block_size=16,
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

    diagnostic = (
        build_scale_aware_transition_diagnostic(
            event_index=1,
            request_accepted=False,
            local_h_before=0.2,
            local_projected_h_after=0.3,
            coarse_transition=coarse,
        )
    )

    assert diagnostic.local_sign == (
        TransitionRiskSign.POSITIVE
    )

    assert diagnostic.coarse_sign == (
        TransitionRiskSign.ZERO
    )

    assert diagnostic.sign_agreement is False


def test_coarse_sign_uses_request_specific_signal():
    coarse = ScaleAwareTransition(
        block_size=16,
        history_ready=True,
        coarse_pressure_before={
            "EUR": 0.2,
        },
        coarse_pressure_after_if_rejected={
            "EUR": 0.4,
        },
        coarse_pressure_after_if_accepted={
            "EUR": 0.3,
        },
        coarse_h_before=0.1,
        coarse_h_after_if_rejected=0.5,
        coarse_h_after_if_accepted=0.3,
        temporal_drift_delta_h=0.4,
        request_delta_h=-0.2,
        total_accepted_delta_h=0.2,
        normalized_temporal_drift_delta_h=6.4,
        normalized_request_delta_h=-3.2,
        normalized_total_accepted_delta_h=3.2,
    )

    diagnostic = (
        build_scale_aware_transition_diagnostic(
            event_index=17,
            request_accepted=True,
            local_h_before=0.3,
            local_projected_h_after=0.2,
            coarse_transition=coarse,
        )
    )

    assert diagnostic.coarse_sign == (
        TransitionRiskSign.NEGATIVE
    )
    assert diagnostic.sign_agreement is True
