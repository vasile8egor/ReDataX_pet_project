from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable


MODEL_METRIC_COLUMNS = (
    "experiment_id",
    "experiment_stage",
    "metric_scope",
    "metric_date",
    "symbol",
    "horizon_seconds",
    "model",
    "observations",
    "toxic_rate",
    "roc_auc",
    "average_precision",
    "brier_score",
    "top_decile_lift",
)

BOOTSTRAP_COLUMNS = (
    "experiment_id",
    "experiment_stage",
    "symbol",
    "horizon_seconds",
    "comparison",
    "metric",
    "days",
    "mean_delta",
    "ci_lower",
    "ci_upper",
    "positive_day_fraction",
)

CAPTURE_COLUMNS = (
    "experiment_id",
    "metric_scope",
    "metric_date",
    "symbol",
    "horizon_seconds",
    "capacity_fraction",
    "model",
    "observations",
    "selected_observations",
    "selected_trade_fraction",
    "total_notional_usdt",
    "selected_notional_usdt",
    "selected_notional_fraction",
    "total_adverse_loss_usdt",
    "captured_adverse_loss_usdt",
    "capture_rate",
    "loss_lift",
    "captured_loss_per_million_total_notional",
    "selected_loss_per_million_selected_notional",
    "oracle_capture_rate",
    "oracle_efficiency",
)

CAPTURE_BOOTSTRAP_COLUMNS = (
    "experiment_id",
    "symbol",
    "horizon_seconds",
    "capacity_fraction",
    "comparison",
    "metric",
    "days",
    "mean_delta",
    "ci_lower",
    "ci_upper",
    "positive_day_fraction",
)


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: root JSON value must be an object")
    return payload


def _metric_row(
    *,
    experiment_id: str,
    stage: str,
    scope: str,
    metric_date: date | None,
    symbol: str,
    horizon_seconds: int,
    model: str,
    metrics: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        experiment_id,
        stage,
        scope,
        metric_date,
        symbol,
        int(horizon_seconds),
        model,
        int(metrics["observations"]),
        float(metrics["toxic_rate"]),
        float(metrics["roc_auc"]),
        float(metrics["average_precision"]),
        float(metrics["brier_score"]),
        float(metrics["top_decile_lift"]),
    )


def flatten_oos_metrics(
    payload: dict[str, Any],
    experiment_id: str = "real_oos_multiscale_v1",
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    metric_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []

    for symbol, symbol_payload in payload["symbols"].items():
        for stage, stage_payload in symbol_payload.items():
            for horizon_text, result in stage_payload.items():
                horizon = int(horizon_text)

                for daily_result in result["daily"]:
                    metric_date = date.fromisoformat(daily_result["date"])
                    for model, metrics in daily_result["models"].items():
                        metric_rows.append(
                            _metric_row(
                                experiment_id=experiment_id,
                                stage=stage,
                                scope="daily",
                                metric_date=metric_date,
                                symbol=symbol,
                                horizon_seconds=horizon,
                                model=model,
                                metrics=metrics,
                            )
                        )

                for model, metrics in result["pooled"].items():
                    metric_rows.append(
                        _metric_row(
                            experiment_id=experiment_id,
                            stage=stage,
                            scope="pooled",
                            metric_date=None,
                            symbol=symbol,
                            horizon_seconds=horizon,
                            model=model,
                            metrics=metrics,
                        )
                    )

                for comparison, comparison_payload in result["bootstrap"].items():
                    for metric, values in comparison_payload.items():
                        bootstrap_rows.append(
                            (
                                experiment_id,
                                stage,
                                symbol,
                                horizon,
                                comparison,
                                metric,
                                int(values["days"]),
                                float(values["mean"]),
                                float(values["ci_025"]),
                                float(values["ci_975"]),
                                float(values["positive_day_fraction"]),
                            )
                        )

    return metric_rows, bootstrap_rows


def flatten_coupled_metrics(
    payload: dict[str, Any],
    experiment_id: str = "coupled_rg_final_v1",
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    metric_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []
    horizon = int(payload["configuration"]["horizon_seconds"])

    for symbol, target_payload in payload["targets"].items():
        result = target_payload["final_test"]

        for daily_result in result["daily"]:
            metric_date = date.fromisoformat(daily_result["date"])
            for model, metrics in daily_result["models"].items():
                metric_rows.append(
                    _metric_row(
                        experiment_id=experiment_id,
                        stage="final_test",
                        scope="daily",
                        metric_date=metric_date,
                        symbol=symbol,
                        horizon_seconds=horizon,
                        model=model,
                        metrics=metrics,
                    )
                )

        for model, metrics in result["pooled"].items():
            metric_rows.append(
                _metric_row(
                    experiment_id=experiment_id,
                    stage="final_test",
                    scope="pooled",
                    metric_date=None,
                    symbol=symbol,
                    horizon_seconds=horizon,
                    model=model,
                    metrics=metrics,
                )
            )

        for comparison, comparison_payload in result["bootstrap"].items():
            for metric, values in comparison_payload.items():
                bootstrap_rows.append(
                    (
                        experiment_id,
                        "final_test",
                        symbol,
                        horizon,
                        comparison,
                        metric,
                        int(values["days"]),
                        float(values["mean"]),
                        float(values["ci_025"]),
                        float(values["ci_975"]),
                        float(values["positive_day_fraction"]),
                    )
                )

    return metric_rows, bootstrap_rows


def _capture_row(
    *,
    experiment_id: str,
    scope: str,
    metric_date: date | None,
    symbol: str,
    horizon_seconds: int,
    capacity_fraction: float,
    model: str,
    metrics: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        experiment_id,
        scope,
        metric_date,
        symbol,
        int(horizon_seconds),
        float(capacity_fraction),
        model,
        int(metrics["observations"]),
        int(metrics["selected_observations"]),
        float(metrics["selected_trade_fraction"]),
        float(metrics["total_notional_usdt"]),
        float(metrics["selected_notional_usdt"]),
        float(metrics["selected_notional_fraction"]),
        float(metrics["total_adverse_loss_usdt"]),
        float(metrics["captured_adverse_loss_usdt"]),
        float(metrics["capture_rate"]),
        float(metrics["loss_lift"]),
        float(metrics["captured_loss_per_million_total_notional"]),
        float(metrics["selected_loss_per_million_selected_notional"]),
        float(metrics["oracle_capture_rate"]),
        float(metrics["oracle_efficiency"]),
    )


def flatten_capture_metrics(
    payload: dict[str, Any],
    experiment_id: str = "adverse_selection_capture_v1",
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    metric_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []

    for symbol, symbol_payload in payload["symbols"].items():
        for horizon_text, result in symbol_payload.items():
            horizon = int(horizon_text)

            for daily_result in result["daily"]:
                metric_date = date.fromisoformat(daily_result["date"])
                for capacity_text, capacity_payload in daily_result["capacities"].items():
                    capacity = float(capacity_text)
                    for model, metrics in capacity_payload["models"].items():
                        metric_rows.append(
                            _capture_row(
                                experiment_id=experiment_id,
                                scope="daily",
                                metric_date=metric_date,
                                symbol=symbol,
                                horizon_seconds=horizon,
                                capacity_fraction=capacity,
                                model=model,
                                metrics=metrics,
                            )
                        )

            for capacity_text, models in result["aggregate"].items():
                capacity = float(capacity_text)
                for model, metrics in models.items():
                    metric_rows.append(
                        _capture_row(
                            experiment_id=experiment_id,
                            scope="aggregate",
                            metric_date=None,
                            symbol=symbol,
                            horizon_seconds=horizon,
                            capacity_fraction=capacity,
                            model=model,
                            metrics=metrics,
                        )
                    )

            for capacity_text, metrics_payload in result["bootstrap"].items():
                capacity = float(capacity_text)
                for metric, values in metrics_payload.items():
                    bootstrap_rows.append(
                        (
                            experiment_id,
                            symbol,
                            horizon,
                            capacity,
                            "m1_minus_m0",
                            metric,
                            int(values["days"]),
                            float(values["mean"]),
                            float(values["ci_025"]),
                            float(values["ci_975"]),
                            float(values["positive_day_fraction"]),
                        )
                    )

    return metric_rows, bootstrap_rows


def _insert(
    client: Any,
    table: str,
    columns: Iterable[str],
    rows: list[tuple[Any, ...]],
) -> None:
    if not rows:
        return
    column_sql = ", ".join(columns)
    client.execute(
        f"INSERT INTO {table} ({column_sql}) VALUES",
        rows,
        types_check=True,
    )


def _delete_experiment(client: Any, table: str, experiment_id: str) -> None:
    escaped = experiment_id.replace("'", "''")
    client.execute(
        f"ALTER TABLE {table} DELETE WHERE experiment_id = '{escaped}' "
        "SETTINGS mutations_sync = 1"
    )


def create_client() -> Any:
    try:
        from clickhouse_driver import Client
    except ImportError as exc:
        raise RuntimeError(
            "clickhouse-driver is required to load analytics artifacts"
        ) from exc

    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default"),
        database=os.getenv("CLICKHOUSE_DATABASE", "gold"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load ReDataX experiment JSON artifacts into ClickHouse."
    )
    parser.add_argument("--oos", help="Path to oos_rg_proof.json")
    parser.add_argument("--capture", help="Path to adverse_selection_capture.json")
    parser.add_argument("--coupled", help="Path to coupled_rg_final.json")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing rows for each experiment_id before insert.",
    )
    arguments = parser.parse_args()

    if not any((arguments.oos, arguments.capture, arguments.coupled)):
        parser.error("at least one artifact path must be supplied")

    client = create_client()

    if arguments.oos:
        experiment_id = "real_oos_multiscale_v1"
        metrics, bootstrap = flatten_oos_metrics(read_json(arguments.oos))
        if arguments.replace:
            _delete_experiment(client, "gold.fact_model_validation_metrics", experiment_id)
            _delete_experiment(client, "gold.fact_model_comparison_bootstrap", experiment_id)
        _insert(client, "gold.fact_model_validation_metrics", MODEL_METRIC_COLUMNS, metrics)
        _insert(client, "gold.fact_model_comparison_bootstrap", BOOTSTRAP_COLUMNS, bootstrap)
        print(f"{experiment_id}: {len(metrics)} metrics, {len(bootstrap)} bootstrap rows")

    if arguments.coupled:
        experiment_id = "coupled_rg_final_v1"
        metrics, bootstrap = flatten_coupled_metrics(read_json(arguments.coupled))
        if arguments.replace:
            _delete_experiment(client, "gold.fact_model_validation_metrics", experiment_id)
            _delete_experiment(client, "gold.fact_model_comparison_bootstrap", experiment_id)
        _insert(client, "gold.fact_model_validation_metrics", MODEL_METRIC_COLUMNS, metrics)
        _insert(client, "gold.fact_model_comparison_bootstrap", BOOTSTRAP_COLUMNS, bootstrap)
        print(f"{experiment_id}: {len(metrics)} metrics, {len(bootstrap)} bootstrap rows")

    if arguments.capture:
        experiment_id = "adverse_selection_capture_v1"
        metrics, bootstrap = flatten_capture_metrics(read_json(arguments.capture))
        if arguments.replace:
            _delete_experiment(client, "gold.fact_adverse_selection_capture", experiment_id)
            _delete_experiment(
                client,
                "gold.fact_adverse_selection_capture_bootstrap",
                experiment_id,
            )
        _insert(client, "gold.fact_adverse_selection_capture", CAPTURE_COLUMNS, metrics)
        _insert(
            client,
            "gold.fact_adverse_selection_capture_bootstrap",
            CAPTURE_BOOTSTRAP_COLUMNS,
            bootstrap,
        )
        print(f"{experiment_id}: {len(metrics)} metrics, {len(bootstrap)} bootstrap rows")


if __name__ == "__main__":
    main()
