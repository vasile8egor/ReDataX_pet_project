from revolut_app.fx_lab.risk.rg.models import (
    ScaleAwareTransition,
    ScaleAwareTransitionDiagnostic,
    TransitionRiskSign,
)


def classify_transition_sign(
    value: float,
    *,
    epsilon: float,
) -> TransitionRiskSign:
    if epsilon < 0.0:
        raise ValueError(
            "epsilon must be non-negative"
        )

    if value > epsilon:
        return TransitionRiskSign.POSITIVE

    if value < -epsilon:
        return TransitionRiskSign.NEGATIVE

    return TransitionRiskSign.ZERO


def build_scale_aware_transition_diagnostic(
    *,
    event_index: int,
    request_accepted: bool,
    local_h_before: float,
    local_projected_h_after: float,
    coarse_transition: ScaleAwareTransition,
    epsilon: float = 1e-6,
) -> ScaleAwareTransitionDiagnostic:
    if event_index <= 0:
        raise ValueError(
            "event_index must be positive"
        )

    local_delta_h = (
        local_projected_h_after
        - local_h_before
    )

    local_sign = classify_transition_sign(
        local_delta_h,
        epsilon=epsilon,
    )

    if coarse_transition.history_ready:
        coarse_sign = classify_transition_sign(
            coarse_transition
            .normalized_request_delta_h,
            epsilon=epsilon,
        )
    else:
        coarse_sign = TransitionRiskSign.ZERO

    return ScaleAwareTransitionDiagnostic(
        event_index=event_index,
        block_size=(
            coarse_transition.block_size
        ),
        history_ready=(
            coarse_transition.history_ready
        ),
        request_accepted=request_accepted,
        local_h_before=local_h_before,
        local_projected_h_after=(
            local_projected_h_after
        ),
        local_delta_h=local_delta_h,
        coarse_h_before=(
            coarse_transition.coarse_h_before
        ),
        coarse_temporal_drift_delta_h=(
            coarse_transition
            .temporal_drift_delta_h
        ),
        normalized_coarse_temporal_drift_delta_h=(
            coarse_transition
            .normalized_temporal_drift_delta_h
        ),
        coarse_request_delta_h=(
            coarse_transition
            .request_delta_h
        ),
        normalized_coarse_request_delta_h=(
            coarse_transition
            .normalized_request_delta_h
        ),
        coarse_total_accepted_delta_h=(
            coarse_transition
            .total_accepted_delta_h
        ),
        normalized_coarse_total_accepted_delta_h=(
            coarse_transition
            .normalized_total_accepted_delta_h
        ),
        local_sign=local_sign,
        coarse_sign=coarse_sign,
        sign_agreement=(
            coarse_transition.history_ready
            and local_sign == coarse_sign
        ),
    )
