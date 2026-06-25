from revolut_app.fx_lab.risk.rg import (
    EffectiveHamiltonianEvaluator,
    RG_EFFECTIVE_LOCAL_B16,
    RollingPressureWindow,
    ScaleAwareTransitionEvaluator,
)
from revolut_app.fx_lab.shared.enums import (
    ScaleAwareDiagnosticPreset,
)


def build_scale_aware_transition_evaluator(
    preset: ScaleAwareDiagnosticPreset,
) -> ScaleAwareTransitionEvaluator:
    if preset == (
        ScaleAwareDiagnosticPreset
        .RG_LOCAL_B16_V1
    ):
        coefficients = (
            RG_EFFECTIVE_LOCAL_B16
        )
    else:
        raise ValueError(
            "Unsupported scale-aware "
            f"diagnostic preset: {preset}"
        )

    window = RollingPressureWindow(
        currencies=(
            "EUR",
            "GBP",
            "USD",
        ),
        block_size=(
            coefficients.block_size
        ),
    )

    return ScaleAwareTransitionEvaluator(
        pressure_window=window,
        hamiltonian=(
            EffectiveHamiltonianEvaluator(
                coefficients=coefficients
            )
        ),
    )
