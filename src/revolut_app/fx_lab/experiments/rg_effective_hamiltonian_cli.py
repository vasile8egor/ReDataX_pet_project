from revolut_app.fx_lab.experiments.rg_effective_hamiltonian import (
    RgEffectiveHamiltonianParameters,
    RgEffectiveHamiltonianRunner,
)
from revolut_app.fx_lab.shared.enums import (
    HamiltonianPreset,
)
from revolut_app.loaders.rg_analysis_loader import (
    RgAnalysisClickHouseLoader,
)


def main() -> None:
    loader = RgAnalysisClickHouseLoader()

    runner = RgEffectiveHamiltonianRunner(
        loader=loader
    )

    summary = runner.run(
        parameters=(
            RgEffectiveHamiltonianParameters(
                fit_version=(
                    "rg-effective-hamiltonian-v1"
                ),
                source_analysis_version=(
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
                expected_trajectories_per_policy=10,
                operator_basis=(
                    "isotropic-local-q2-q4-v1"
                ),
            )
        )
    )

    print()
    print(
        "Effective Hamiltonian fitting completed"
    )
    print(
        f"fit_analysis_id="
        f"{summary.fit_analysis_id}"
    )
    print(f"policies={summary.policies}")
    print(
        f"block_sizes="
        f"{summary.block_sizes}"
    )
    print(f"fit_rows={summary.fit_rows}")
    print(
        f"total_observations="
        f"{summary.total_observations}"
    )


if __name__ == "__main__":
    main()