from collections.abc import Iterable

from revolut_app.fx_lab.experiments.models import (
    PolicyInventorySnapshot,
)
from revolut_app.fx_lab.risk.rg import (
    PressureObservation,
)


def inventory_snapshots_to_rg_observations(
    snapshots: Iterable[PolicyInventorySnapshot],
    *,
    trajectory_id: str = 'policy-run',
):
    observations: list[
        PressureObservation
    ] = []

    for snapshot in snapshots:
        observations.append(
            PressureObservation(
                trajectory_id=trajectory_id,
                event_index=snapshot.event_index,
                currency=(
                    snapshot.currency.value
                    if hasattr(
                        snapshot.currency,
                        'value',
                    )
                    else str(snapshot.currency)
                ),
                pressure=snapshot.phi,
                h_total=snapshot.h_total,
            )
        )

    return observations
