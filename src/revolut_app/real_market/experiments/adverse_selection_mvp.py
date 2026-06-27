from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
from clickhouse_driver import Client
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


SCALES = (1, 2, 4, 8, 16, 32, 64)
HORIZONS_SECONDS = (1, 5, 30, 60)

REPLAY_MODEL_VERSION = (
    "passive-market-maker-unhedged-v1"
)

PRIMARY_HORIZON_SECONDS = 5
RANDOM_SEED = 20260627


SELECT_SYMBOL_TRADES_Q = """
SELECT
    unified.aggregate_trade_id,
    unified.timestamp_us,
    toFloat64(unified.price) AS price,

    if(
        unified.aggressor_side = 'buy_base',
        toInt8(1),
        toInt8(-1)
    ) AS aggressor_sign,

    if(
        unified.symbol = 'ETHBTC',

        toFloat64(unified.quote_quantity)
            * assumeNotNull(marks.btcusdt_mark),

        toFloat64(unified.quote_quantity)
    ) AS notional_usdt

FROM silver.fact_real_market_unified_events
    AS unified

ANY LEFT JOIN
(
    SELECT
        trade_date,
        event_index,
        btcusdt_mark

    FROM silver.fact_real_market_inventory_mtm

    WHERE replay_model_version =
        %(replay_model_version)s

      AND prices_ready = 1
) AS marks
    ON unified.trade_date = marks.trade_date
   AND unified.event_index = marks.event_index

WHERE unified.trade_date = %(trade_date)s
  AND unified.symbol = %(symbol)s

ORDER BY
    unified.timestamp_us,
    unified.aggregate_trade_id
"""


@dataclass(frozen=True)
class EvaluationMetrics:
    observations: int
    toxic_rate: float

    roc_auc: float
    average_precision: float
    brier_score: float

    top_decile_toxic_rate: float
    top_decile_lift: float


@dataclass(frozen=True)
class ModelComparison:
    symbol: str
    horizon_seconds: int

    train_observations: int
    validation_observations: int
    test_observations: int

    baseline: EvaluationMetrics
    rg: EvaluationMetrics

    delta_roc_auc: float
    delta_average_precision: float
    delta_top_decile_lift: float


@dataclass(frozen=True)
class SymbolData:
    aggregate_trade_id: np.ndarray
    timestamp_us: np.ndarray
    price: np.ndarray
    aggressor_sign: np.ndarray
    notional_usdt: np.ndarray


def load_symbol_data(
    *,
    client: Client,
    trade_date: date,
    symbol: str,
) -> SymbolData:
    columns = client.execute(
        SELECT_SYMBOL_TRADES_Q,
        {
            "trade_date": trade_date,
            "symbol": symbol,
            "replay_model_version": (
                REPLAY_MODEL_VERSION
            ),
        },
        columnar=True,
        settings={
            "use_numpy": True,
        },
    )

    if len(columns) != 5:
        raise RuntimeError(
            "Unexpected ClickHouse column count: "
            f"{len(columns)}"
        )

    (
        aggregate_trade_id,
        timestamp_us,
        price,
        aggressor_sign,
        notional_usdt,
    ) = columns

    data = SymbolData(
        aggregate_trade_id=np.asarray(
            aggregate_trade_id,
            dtype=np.uint64,
        ),
        timestamp_us=np.asarray(
            timestamp_us,
            dtype=np.int64,
        ),
        price=np.asarray(
            price,
            dtype=np.float64,
        ),
        aggressor_sign=np.asarray(
            aggressor_sign,
            dtype=np.int8,
        ),
        notional_usdt=np.asarray(
            notional_usdt,
            dtype=np.float64,
        ),
    )

    validate_symbol_data(data=data)

    return data


def validate_symbol_data(
    *,
    data: SymbolData,
) -> None:
    lengths = {
        data.aggregate_trade_id.size,
        data.timestamp_us.size,
        data.price.size,
        data.aggressor_sign.size,
        data.notional_usdt.size,
    }

    if len(lengths) != 1:
        raise ValueError(
            "Input columns have different lengths"
        )

    if data.price.size == 0:
        raise ValueError("No trades loaded")

    if np.any(np.diff(data.timestamp_us) < 0):
        raise ValueError(
            "Timestamps are not ordered"
        )

    if np.any(data.price <= 0):
        raise ValueError(
            "Prices must be positive"
        )

    if np.any(data.notional_usdt <= 0):
        raise ValueError(
            "Notional must be positive"
        )

    if not np.all(
        np.isin(
            data.aggressor_sign,
            (-1, 1),
        )
    ):
        raise ValueError(
            "Aggressor sign must be -1 or 1"
        )


def calculate_causal_flow_imbalances(
    *,
    aggressor_sign: np.ndarray,
    notional_usdt: np.ndarray,
    scales: tuple[int, ...],
) -> np.ndarray:
    """
    For event i, use only events before i.

    phi_B(i) =
        sum_{k=i-B}^{i-1} signed_notional_k
        /
        sum_{k=i-B}^{i-1} abs_notional_k
    """
    count = notional_usdt.size

    signed_notional = (
        aggressor_sign.astype(np.float64)
        * notional_usdt
    )

    signed_cumulative = np.concatenate(
        (
            np.array([0.0]),
            np.cumsum(
                signed_notional,
                dtype=np.float64,
            ),
        )
    )

    absolute_cumulative = np.concatenate(
        (
            np.array([0.0]),
            np.cumsum(
                notional_usdt,
                dtype=np.float64,
            ),
        )
    )

    event_indices = np.arange(
        count,
        dtype=np.int64,
    )

    result = np.full(
        (count, len(scales)),
        np.nan,
        dtype=np.float64,
    )

    for scale_index, scale in enumerate(
        scales
    ):
        start_indices = (
            event_indices - scale
        )

        ready = start_indices >= 0

        signed_sum = np.zeros(
            count,
            dtype=np.float64,
        )

        absolute_sum = np.zeros(
            count,
            dtype=np.float64,
        )

        signed_sum[ready] = (
            signed_cumulative[
                event_indices[ready]
            ]
            - signed_cumulative[
                start_indices[ready]
            ]
        )

        absolute_sum[ready] = (
            absolute_cumulative[
                event_indices[ready]
            ]
            - absolute_cumulative[
                start_indices[ready]
            ]
        )

        valid = ready & (absolute_sum > 0)

        result[valid, scale_index] = (
            signed_sum[valid]
            / absolute_sum[valid]
        )

    return result


def calculate_adverse_selection_bps(
    *,
    timestamp_us: np.ndarray,
    price: np.ndarray,
    aggressor_sign: np.ndarray,
    horizon_seconds: int,
) -> np.ndarray:
    """
    Positive value means that price moved in the
    aggressor's direction, against the passive maker.
    """
    target_timestamp_us = (
        timestamp_us
        + horizon_seconds * 1_000_000
    )

    future_indices = (
        np.searchsorted(
            timestamp_us,
            target_timestamp_us,
            side="right",
        )
        - 1
    )

    current_indices = np.arange(
        timestamp_us.size,
        dtype=np.int64,
    )

    valid = future_indices > current_indices

    safe_indices = np.clip(
        future_indices,
        0,
        price.size - 1,
    )

    future_price = price[safe_indices]

    result = np.full(
        price.size,
        np.nan,
        dtype=np.float64,
    )

    result[valid] = (
        aggressor_sign[valid]
        * (
            future_price[valid]
            - price[valid]
        )
        / price[valid]
        * 10_000.0
    )

    return result


def build_feature_matrices(
    *,
    flow_imbalances: np.ndarray,
    aggressor_sign: np.ndarray,
    notional_usdt: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    sign = aggressor_sign.astype(
        np.float64
    )

    aligned_flow = (
        flow_imbalances
        * sign[:, np.newaxis]
    )

    absolute_flow = np.abs(
        flow_imbalances
    )

    log_notional = np.log1p(
        notional_usdt
    )[:, np.newaxis]

    scale_differences = np.diff(
        aligned_flow,
        axis=1,
    )

    scale_16_index = SCALES.index(16)

    baseline_features = np.column_stack(
        (
            log_notional[:, 0],
            aligned_flow[
                :,
                scale_16_index,
            ],
            absolute_flow[
                :,
                scale_16_index,
            ],
        )
    )

    rg_features = np.column_stack(
        (
            log_notional,
            aligned_flow,
            absolute_flow,
            scale_differences,
        )
    )

    return baseline_features, rg_features


def chronological_split(
    *,
    count: int,
) -> tuple[slice, slice, slice]:
    train_end = int(count * 0.60)
    validation_end = int(count * 0.80)

    return (
        slice(0, train_end),
        slice(
            train_end,
            validation_end,
        ),
        slice(validation_end, count),
    )


def build_classifier() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "classifier",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=1e-4,
                    max_iter=2_000,
                    tol=1e-4,
                    random_state=RANDOM_SEED,
                    average=True,
                ),
            ),
        ]
    )


def evaluate_scores(
    *,
    labels: np.ndarray,
    scores: np.ndarray,
) -> EvaluationMetrics:
    if np.unique(labels).size != 2:
        raise ValueError(
            "Both target classes are required"
        )

    toxic_rate = float(
        np.mean(labels)
    )

    top_decile_threshold = float(
        np.quantile(scores, 0.90)
    )

    top_decile_mask = (
        scores >= top_decile_threshold
    )

    top_decile_toxic_rate = float(
        np.mean(labels[top_decile_mask])
    )

    return EvaluationMetrics(
        observations=int(labels.size),
        toxic_rate=toxic_rate,
        roc_auc=float(
            roc_auc_score(
                labels,
                scores,
            )
        ),
        average_precision=float(
            average_precision_score(
                labels,
                scores,
            )
        ),
        brier_score=float(
            brier_score_loss(
                labels,
                scores,
            )
        ),
        top_decile_toxic_rate=(
            top_decile_toxic_rate
        ),
        top_decile_lift=(
            top_decile_toxic_rate
            / toxic_rate
            if toxic_rate > 0
            else float("nan")
        ),
    )


def evaluate_symbol(
    *,
    symbol: str,
    data: SymbolData,
    horizon_seconds: int,
) -> ModelComparison:
    flow_imbalances = (
        calculate_causal_flow_imbalances(
            aggressor_sign=(
                data.aggressor_sign
            ),
            notional_usdt=(
                data.notional_usdt
            ),
            scales=SCALES,
        )
    )

    adverse_selection_bps = (
        calculate_adverse_selection_bps(
            timestamp_us=data.timestamp_us,
            price=data.price,
            aggressor_sign=(
                data.aggressor_sign
            ),
            horizon_seconds=horizon_seconds,
        )
    )

    baseline_x, rg_x = (
        build_feature_matrices(
            flow_imbalances=(
                flow_imbalances
            ),
            aggressor_sign=(
                data.aggressor_sign
            ),
            notional_usdt=(
                data.notional_usdt
            ),
        )
    )

    valid = (
        np.all(
            np.isfinite(rg_x),
            axis=1,
        )
        & np.isfinite(
            adverse_selection_bps
        )
    )

    baseline_x = baseline_x[valid]
    rg_x = rg_x[valid]

    adverse_selection_bps = (
        adverse_selection_bps[valid]
    )

    labels = (
        adverse_selection_bps > 0.0
    ).astype(np.uint8)

    train_slice, validation_slice, test_slice = (
        chronological_split(
            count=labels.size
        )
    )

    baseline_model = build_classifier()
    rg_model = build_classifier()

    baseline_model.fit(
        baseline_x[train_slice],
        labels[train_slice],
    )

    rg_model.fit(
        rg_x[train_slice],
        labels[train_slice],
    )

    baseline_test_scores = (
        baseline_model.predict_proba(
            baseline_x[test_slice]
        )[:, 1]
    )

    rg_test_scores = (
        rg_model.predict_proba(
            rg_x[test_slice]
        )[:, 1]
    )

    test_labels = labels[test_slice]

    baseline_metrics = evaluate_scores(
        labels=test_labels,
        scores=baseline_test_scores,
    )

    rg_metrics = evaluate_scores(
        labels=test_labels,
        scores=rg_test_scores,
    )

    return ModelComparison(
        symbol=symbol,
        horizon_seconds=horizon_seconds,
        train_observations=(
            labels[train_slice].size
        ),
        validation_observations=(
            labels[validation_slice].size
        ),
        test_observations=(
            test_labels.size
        ),
        baseline=baseline_metrics,
        rg=rg_metrics,
        delta_roc_auc=(
            rg_metrics.roc_auc
            - baseline_metrics.roc_auc
        ),
        delta_average_precision=(
            rg_metrics.average_precision
            - baseline_metrics.average_precision
        ),
        delta_top_decile_lift=(
            rg_metrics.top_decile_lift
            - baseline_metrics.top_decile_lift
        ),
    )


def create_client() -> Client:
    return Client(
        host=os.getenv(
            "CLICKHOUSE_HOST",
            "clickhouse",
        ),
        port=int(
            os.getenv(
                "CLICKHOUSE_PORT",
                "9000",
            )
        ),
        user=os.getenv(
            "CLICKHOUSE_USER",
            "default",
        ),
        password=os.getenv(
            "CLICKHOUSE_PASSWORD",
            "default",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        type=date.fromisoformat,
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[
            "BTCUSDT",
            "ETHUSDT",
            "ETHBTC",
        ],
    )

    parser.add_argument(
        "--horizon-seconds",
        type=int,
        default=PRIMARY_HORIZON_SECONDS,
    )

    arguments = parser.parse_args()

    client = create_client()

    results: list[ModelComparison] = []

    for symbol in arguments.symbols:
        print(
            f"Loading symbol={symbol}",
            flush=True,
        )

        data = load_symbol_data(
            client=client,
            trade_date=arguments.date,
            symbol=symbol,
        )

        print(
            f"Loaded symbol={symbol} "
            f"trades={data.price.size}",
            flush=True,
        )

        result = evaluate_symbol(
            symbol=symbol,
            data=data,
            horizon_seconds=(
                arguments.horizon_seconds
            ),
        )

        results.append(result)

        print(
            json.dumps(
                asdict(result),
                indent=2,
                ensure_ascii=False,
            ),
            flush=True,
        )

    print()
    print("SUMMARY")

    for result in results:
        print(
            f"{result.symbol}: "
            f"delta_roc_auc="
            f"{result.delta_roc_auc:+.6f} "
            f"delta_ap="
            f"{result.delta_average_precision:+.6f} "
            f"delta_top_decile_lift="
            f"{result.delta_top_decile_lift:+.6f}"
        )


if __name__ == "__main__":
    main()
