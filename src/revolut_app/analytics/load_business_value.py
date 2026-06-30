from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable


VALUE_COLUMNS = (
    "experiment_id",
    "metric_scope",
    "metric_date",
    "symbol",
    "horizon_seconds",
    "capacity_fraction",
    "scenario",
    "mitigation_efficiency",
    "internalization_rate",
    "action_cost_bps",
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
    "risk_concentration",
    "gross_protected_value_usdt",
    "action_cost_usdt",
    "net_protected_value_usdt",
    "gross_protected_value_per_million_total_notional",
    "net_protected_value_per_million_total_notional",
    "break_even_action_cost_bps",
    "benefit_cost_ratio",
)

BOOTSTRAP_COLUMNS = (
    "experiment_id",
    "symbol",
    "horizon_seconds",
    "capacity_fraction",
    "scenario",
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
        raise ValueError("business-value JSON root must be an object")
    return payload


def _metric_row(
    *,
    experiment_id: str,
    scope: str,
    metric_date: date | None,
    symbol: str,
    horizon_seconds: int,
    capacity_fraction: float,
    scenario_name: str,
    scenario: dict[str, Any],
    model: str,
    metrics: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        experiment_id,
        scope,
        metric_date or date(1970, 1, 1),
        symbol,
        horizon_seconds,
        capacity_fraction,
        scenario_name,
        float(scenario["mitigation_efficiency"]),
        float(scenario["internalization_rate"]),
        float(scenario["action_cost_bps"]),
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
        float(metrics["risk_concentration"]),
        float(metrics["gross_protected_value_usdt"]),
        float(metrics["action_cost_usdt"]),
        float(metrics["net_protected_value_usdt"]),
        float(
            metrics[
                "gross_protected_value_per_million_total_notional"
            ]
        ),
        float(
            metrics[
                "net_protected_value_per_million_total_notional"
            ]
        ),
        float(metrics["break_even_action_cost_bps"]),
        float(metrics["benefit_cost_ratio"]),
    )


def flatten_business_value(
    payload: dict[str, Any],
    experiment_id: str = "coupled_business_value_v1",
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    configuration = payload["configuration"]
    horizon = int(configuration["horizon_seconds"])

    value_rows: list[tuple[Any, ...]] = []
    bootstrap_rows: list[tuple[Any, ...]] = []

    for symbol, target in payload["targets"].items():
        for daily in target["daily"]:
            metric_date = date.fromisoformat(daily["date"])
            for capacity_text, capacity_payload in daily[
                "capacities"
            ].items():
                capacity = float(capacity_text)
                for scenario_name, scenario_payload in capacity_payload[
                    "scenarios"
                ].items():
                    scenario = scenario_payload["scenario"]
                    for model, metrics in scenario_payload[
                        "models"
                    ].items():
                        value_rows.append(
                            _metric_row(
                                experiment_id=experiment_id,
                                scope="daily",
                                metric_date=metric_date,
                                symbol=symbol,
                                horizon_seconds=horizon,
                                capacity_fraction=capacity,
                                scenario_name=scenario_name,
                                scenario=scenario,
                                model=model,
                                metrics=metrics,
                            )
                        )

        for capacity_text, capacity_payload in target[
            "aggregate"
        ].items():
            capacity = float(capacity_text)
            for scenario_name, scenario_payload in capacity_payload.items():
                scenario = scenario_payload["scenario"]
                for model, metrics in scenario_payload["models"].items():
                    value_rows.append(
                        _metric_row(
                            experiment_id=experiment_id,
                            scope="aggregate",
                            metric_date=None,
                            symbol=symbol,
                            horizon_seconds=horizon,
                            capacity_fraction=capacity,
                            scenario_name=scenario_name,
                            scenario=scenario,
                            model=model,
                            metrics=metrics,
                        )
                    )

        for capacity_text, capacity_payload in target[
            "bootstrap"
        ].items():
            capacity = float(capacity_text)
            for scenario_name, scenario_payload in capacity_payload.items():
                for comparison, comparison_payload in scenario_payload.items():
                    for metric, values in comparison_payload.items():
                        bootstrap_rows.append(
                            (
                                experiment_id,
                                symbol,
                                horizon,
                                capacity,
                                scenario_name,
                                comparison,
                                metric,
                                int(values["days"]),
                                float(values["mean"]),
                                float(values["ci_025"]),
                                float(values["ci_975"]),
                                float(
                                    values["positive_day_fraction"]
                                ),
                            )
                        )

    return value_rows, bootstrap_rows


def create_client() -> Any:
    try:
        from clickhouse_driver import Client
    except ImportError as exc:
        raise RuntimeError(
            "clickhouse-driver is required to load business metrics"
        ) from exc

    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default"),
        database=os.getenv("CLICKHOUSE_DATABASE", "gold"),
    )


def _insert(
    client: Any,
    table: str,
    columns: Iterable[str],
    rows: list[tuple[Any, ...]],
) -> None:
    if not rows:
        return
    client.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES",
        rows,
        types_check=True,
    )


def _delete_experiment(
    client: Any,
    table: str,
    experiment_id: str,
) -> None:
    escaped = experiment_id.replace("'", "''")
    client.execute(
        f"ALTER TABLE {table} "
        f"DELETE WHERE experiment_id = '{escaped}' "
        "SETTINGS mutations_sync = 1"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--experiment-id",
        default="coupled_business_value_v1",
    )
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()

    payload = read_json(arguments.input)
    value_rows, bootstrap_rows = flatten_business_value(
        payload,
        experiment_id=arguments.experiment_id,
    )
    client = create_client()

    if arguments.replace:
        _delete_experiment(
            client,
            "gold.fact_business_value_scenarios",
            arguments.experiment_id,
        )
        _delete_experiment(
            client,
            "gold.fact_business_value_bootstrap",
            arguments.experiment_id,
        )

    _insert(
        client,
        "gold.fact_business_value_scenarios",
        VALUE_COLUMNS,
        value_rows,
    )
    _insert(
        client,
        "gold.fact_business_value_bootstrap",
        BOOTSTRAP_COLUMNS,
        bootstrap_rows,
    )

    print(
        f"{arguments.experiment_id}: "
        f"{len(value_rows)} value rows, "
        f"{len(bootstrap_rows)} bootstrap rows"
    )


if __name__ == "__main__":
    main()
