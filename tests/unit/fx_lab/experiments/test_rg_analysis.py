from uuid import uuid4

from revolut_app.fx_lab.experiments.rg_analysis import (
    RgAnalysisParameters,
    RgMultiscaleAnalysisRunner,
)
from revolut_app.fx_lab.risk.rg import (
    PressureObservation,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)
from revolut_app.loaders.rg_analysis_loader import (
    RgSourceRun,
)


class FakeRgLoader:
    def __init__(
        self,
        source_runs,
        observations_by_run,
    ):
        self.source_runs = source_runs
        self.observations_by_run = (
            observations_by_run
        )

        self.persisted = None

    def load_source_runs(
        self,
        *,
        source_model_version,
    ):
        return self.source_runs

    def load_pressure_observations(
        self,
        *,
        source_run,
    ):
        return self.observations_by_run[
            source_run.run_id
        ]

    def ensure_analysis_not_persisted(
        self,
        *,
        analysis_id,
    ):
        return None

    def persist_analysis(
        self,
        *,
        analysis,
        scales,
        currencies,
        scaling,
    ):
        self.persisted = {
            'analysis': analysis,
            'scales': scales,
            'currencies': currencies,
            'scaling': scaling,
        }


def test_rg_analysis_runner_persists_multiscale_rows():
    run_id = uuid4()
    event_dataset_id = uuid4()

    source_run = RgSourceRun(
        run_id=run_id,
        event_dataset_id=event_dataset_id,
        pricing_policy='inventory_aware',
        generated_requests=2,
    )

    observations = []
    for event_index in (1, 2):
        for currency, pressure in {
            'EUR': 0.1 * event_index,
            'GBP': -0.1 * event_index,
            'USD': 0.05 * event_index,
        }.items():
            observations.append(
                PressureObservation(
                    trajectory_id=str(run_id),
                    event_index=event_index,
                    currency=currency,
                    pressure=pressure,
                    h_total=None,
                )
            )

    loader = FakeRgLoader(
        source_runs=[source_run],
        observations_by_run={
            run_id: observations,
        },
    )

    runner = RgMultiscaleAnalysisRunner(
        loader=loader,
    )

    summary = runner.run(
        parameters=RgAnalysisParameters(
            analysis_version='test-rg-v1',
            source_model_version='source-v1',
            hamiltonian_preset=(
                HamiltonianPreset.local_v1
            ),
            block_sizes=(2,),
            stress_pressure_threshold=0.9,
            expected_source_runs=1,
        )
    )

    assert summary.source_runs == 1
    assert summary.source_frames == 2
    assert summary.scale_rows == 1
    assert summary.currency_rows == 3
    assert summary.scaling_rows == 0

    assert loader.persisted is not None
    assert (
        loader.persisted['analysis'].analysis_id
        == summary.analysis_id
    )
