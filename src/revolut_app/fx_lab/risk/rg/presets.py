from revolut_app.fx_lab.risk.rg.models import (
    EffectiveHamiltonianCoefficients,
)


RG_EFFECTIVE_LOCAL_B16 = (
    EffectiveHamiltonianCoefficients(
        block_size=16,
        intercept=0.00833302,
        quadratic=2.04215111,
        quartic=2.05362953,
    )
)


RG_EFFECTIVE_LOCAL_B32 = (
    EffectiveHamiltonianCoefficients(
        block_size=32,
        intercept=0.01342777,
        quadratic=2.04815040,
        quartic=2.05299026,
    )
)
