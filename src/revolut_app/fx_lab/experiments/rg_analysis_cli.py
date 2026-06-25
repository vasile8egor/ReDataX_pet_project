from __future__ import annotations

from revolut_app.fx_lab.experiments.rg_analysis import (
    RgAnalysisParameters,
    RgMultiscaleAnalysisRunner,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)
from revolut_app.loaders.rg_analysis_loader import (
    RgAnalysisClickHouseLoader,
)


def main() -> None:
    loader = RgAnalysisClickHouseLoader()

    runner = RgMultiscaleAnalysisRunner(
        loader=loader
    )

    summary = runner.run(
        parameters=RgAnalysisParameters(
            analysis_version=(
                "rg-multiscale-observables-v1"
            ),
            source_model_version=(
                "hamiltonian-observer-v1-"
                "rg-event-level"
            ),
            hamiltonian_preset=(
                HamiltonianPreset.local_v1
            ),
            block_sizes=(1, 2, 4, 8, 16, 32, 64),
            stress_pressure_threshold=0.9,
            expected_source_runs=30,
        )
    )

    print()
    print("RG multiscale analysis completed")
    print(f"analysis_id={summary.analysis_id}")
    print(f"source_runs={summary.source_runs}")
    print(
        f"source_frames="
        f"{summary.source_frames}"
    )
    print(f"scale_rows={summary.scale_rows}")
    print(
        f"currency_rows="
        f"{summary.currency_rows}"
    )
    print(
        f"scaling_rows="
        f"{summary.scaling_rows}"
    )


if __name__ == "__main__":
    main()
