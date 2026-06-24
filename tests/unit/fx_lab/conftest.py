from datetime import datetime, timezone
from uuid import UUID

import pytest

from revolut_app.fx_lab.market.event_generation import (
    HawkesLikeFXEventGenerator
)


@pytest.fixture
def fixed_dataset_id():
    return UUID('11111111-1111-1111-1111-111111111111')


@pytest.fixture
def fixed_start_at():
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fx_event_dataset(
    fixed_dataset_id: UUID,
    fixed_start_at: datetime,
):
    generator = HawkesLikeFXEventGenerator(seed=42)
    return generator.simulate_event_dataset(
        steps=2000,
        dt_seconds=10,
        base_intensity=0.03,
        alpha=0.08,
        beta=0.12,
        start_at=fixed_start_at,
        event_dataset_id=fixed_dataset_id,
        seed=42,
    )
