from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
from clickhouse_driver import Client
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

SCALES = (1, 2, 4, 8, 16, 32, 64)
MODELS = ("m0_single_scale", "m1_multiscale", "m2_rg_flow")
EPS = 1e-8
SEED = 20260627

TRADES_SQL = """
SELECT
    toUnixTimestamp64Micro(event_timestamp) AS timestamp_us,
    toFloat64(price) AS price,
    toFloat64(base_quantity) AS base_quantity,
    toFloat64(quote_quantity) AS quote_quantity,
    if(aggressor_side = 'buy_base', toInt8(1), toInt8(-1)) AS aggressor_sign
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol = %(symbol)s
ORDER BY timestamp_us, aggregate_trade_id
"""

BTC_REF_SQL = """
SELECT
    toUnixTimestamp64Micro(event_timestamp) AS timestamp_us,
    toFloat64(price) AS price
FROM raw.fact_real_market_agg_trades FINAL
WHERE trade_date = %(trade_date)s
  AND symbol = 'BTCUSDT'
ORDER BY timestamp_us, aggregate_trade_id
"""


@dataclass(frozen=True)
class DayData:
    timestamp_us: np.ndarray
    price: np.ndarray
    base_quantity: np.ndarray
    aggressor_sign: np.ndarray
    notional_usdt: np.ndarray


@dataclass(frozen=True)
class Metrics:
    observations: int
    toxic_rate: float
    roc_auc: float
    average_precision: float
    brier_score: float
    top_decile_lift: float


@dataclass
class ModelState:
    scaler: StandardScaler
    classifier: SGDClassifier
    initialized: bool = False


def client() -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default"),
    )


def dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date is before start date")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def load_day(ch: Client, trade_date: date, symbol: str) -> DayData:
    cols = ch.execute(
        TRADES_SQL,
        {"trade_date": trade_date, "symbol": symbol},
        columnar=True,
        settings={"use_numpy": True},
    )
    if len(cols) != 5:
        raise RuntimeError(f"Unexpected column count for {symbol}: {len(cols)}")

    ts = np.asarray(cols[0], dtype=np.int64)
    price = np.asarray(cols[1], dtype=np.float64)
    qty = np.asarray(cols[2], dtype=np.float64)
    quote = np.asarray(cols[3], dtype=np.float64)
    sign = np.asarray(cols[4], dtype=np.int8)

    if ts.size == 0:
        raise ValueError(f"No rows for {symbol} on {trade_date}")
    if np.any(np.diff(ts) < 0):
        raise ValueError(f"Unordered timestamps for {symbol} on {trade_date}")

    if symbol == "ETHBTC":
        btc = ch.execute(
            BTC_REF_SQL,
            {"trade_date": trade_date},
            columnar=True,
            settings={"use_numpy": True},
        )
        btc_ts = np.asarray(btc[0], dtype=np.int64)
        btc_price = np.asarray(btc[1], dtype=np.float64)
        idx = np.searchsorted(btc_ts, ts, side="right") - 1
        notional = np.full(ts.size, np.nan, dtype=np.float64)
        ready = idx >= 0
        notional[ready] = quote[ready] * btc_price[idx[ready]]
    else:
        notional = quote

    return DayData(ts, price, qty, sign, notional)


def causal_imbalances(data: DayData) -> np.ndarray:
    signed = data.aggressor_sign.astype(np.float64) * data.notional_usdt
    finite = np.isfinite(data.notional_usdt)

    signed_cum = np.concatenate(([0.0], np.cumsum(np.nan_to_num(signed))))
    abs_cum = np.concatenate(([0.0], np.cumsum(np.nan_to_num(data.notional_usdt))))
    finite_cum = np.concatenate(([0], np.cumsum(finite.astype(np.int64))))

    n = data.timestamp_us.size
    indices = np.arange(n)
    out = np.full((n, len(SCALES)), np.nan, dtype=np.float64)

    for j, scale in enumerate(SCALES):
        starts = indices - scale
        ready = starts >= 0
        signed_sum = np.zeros(n)
        abs_sum = np.zeros(n)
        finite_count = np.zeros(n, dtype=np.int64)
        signed_sum[ready] = signed_cum[indices[ready]] - signed_cum[starts[ready]]
        abs_sum[ready] = abs_cum[indices[ready]] - abs_cum[starts[ready]]
        finite_count[ready] = finite_cum[indices[ready]] - finite_cum[starts[ready]]
        valid = ready & (finite_count == scale) & (abs_sum > 0)
        out[valid, j] = signed_sum[valid] / abs_sum[valid]

    return out


def future_vwap_markout(
    data: DayData,
    horizon_seconds: int,
    window_seconds: int,
) -> np.ndarray:
    start = data.timestamp_us + horizon_seconds * 1_000_000
    end = start + window_seconds * 1_000_000
    left = np.searchsorted(data.timestamp_us, start, side="left")
    right = np.searchsorted(data.timestamp_us, end, side="right")

    pv_cum = np.concatenate(([0.0], np.cumsum(data.price * data.base_quantity)))
    q_cum = np.concatenate(([0.0], np.cumsum(data.base_quantity)))
    pv = pv_cum[right] - pv_cum[left]
    q = q_cum[right] - q_cum[left]

    valid = (right > left) & (q > 0)
    target = np.full(data.price.size, np.nan, dtype=np.float64)
    target[valid] = pv[valid] / q[valid]

    markout = np.full(data.price.size, np.nan, dtype=np.float64)
    markout[valid] = (
        data.aggressor_sign[valid]
        * (target[valid] - data.price[valid])
        / data.price[valid]
        * 10_000.0
    )
    return markout


def feature_matrix(
    data: DayData,
    phi: np.ndarray,
    model_name: str,
    valid: np.ndarray,
) -> np.ndarray:
    phi_valid = phi[valid].astype(np.float32, copy=False)
    sign = data.aggressor_sign[valid].astype(np.float32, copy=False)
    log_notional = np.log1p(data.notional_usdt[valid]).astype(np.float32)[:, None]
    aligned = phi_valid * sign[:, None]
    absolute = np.abs(phi_valid)
    q2 = phi_valid**2
    q4 = q2**2

    if model_name == "m0_single_scale":
        i16 = SCALES.index(16)
        return np.column_stack((
            log_notional[:, 0],
            aligned[:, i16],
            absolute[:, i16],
            q2[:, i16],
            q4[:, i16],
        )).astype(np.float32, copy=False)

    m1 = np.column_stack((log_notional, aligned, absolute, q2, q4))

    if model_name == "m1_multiscale":
        return m1.astype(np.float32, copy=False)

    if model_name != "m2_rg_flow":
        raise ValueError(f"Unknown model: {model_name}")

    delta_aligned = np.diff(aligned, axis=1)
    beta_q2 = np.clip(
        np.log((q2[:, 1:] + EPS) / (q2[:, :-1] + EPS)) / np.log(2),
        -10,
        10,
    )
    beta_q4 = np.clip(
        np.log((q4[:, 1:] + EPS) / (q4[:, :-1] + EPS)) / np.log(2),
        -10,
        10,
    )
    return np.column_stack((m1, delta_aligned, beta_q2, beta_q4)).astype(
        np.float32,
        copy=False,
    )


def feature_matrices(data: DayData, phi: np.ndarray) -> dict[str, np.ndarray]:
    valid = (
        np.all(np.isfinite(phi), axis=1)
        & np.isfinite(data.notional_usdt)
    )
    return {
        name: feature_matrix(data, phi, name, valid)
        for name in MODELS
    }


def day_dataset(
    data: DayData,
    horizon_seconds: int,
    window_seconds: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    phi = causal_imbalances(data)
    markout = future_vwap_markout(data, horizon_seconds, window_seconds)
    valid = (
        np.all(np.isfinite(phi), axis=1)
        & np.isfinite(data.notional_usdt)
        & np.isfinite(markout)
    )
    labels = (markout[valid] > 0).astype(np.uint8)
    return phi, valid, labels


def state() -> ModelState:
    return ModelState(
        scaler=StandardScaler(),
        classifier=SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-4,
            learning_rate="optimal",
            average=True,
            random_state=SEED,
        ),
    )


def fit(
    ch: Client,
    symbol: str,
    train_dates: list[date],
    horizons: tuple[int, ...],
    window_seconds: int,
) -> dict[int, dict[str, ModelState]]:
    states = {h: {name: state() for name in MODELS} for h in horizons}

    for pass_name in ("scaler", "classifier"):
        print(f"{symbol}: {pass_name} pass", flush=True)
        for d in train_dates:
            data = load_day(ch, d, symbol)
            print(f"{symbol} {d}: rows={data.price.size}", flush=True)
            for h in horizons:
                phi, valid, labels = day_dataset(data, h, window_seconds)
                for name in MODELS:
                    model = states[h][name]
                    features = feature_matrix(data, phi, name, valid)
                    if pass_name == "scaler":
                        model.scaler.partial_fit(features)
                    else:
                        x = model.scaler.transform(features)
                        model.classifier.partial_fit(x, labels, classes=np.array([0, 1], dtype=np.uint8))
                        model.initialized = True
    return states


def metrics(labels: np.ndarray, scores: np.ndarray) -> Metrics:
    if np.unique(labels).size != 2:
        raise ValueError("Both target classes are required")
    rate = float(np.mean(labels))
    threshold = float(np.quantile(scores, 0.90))
    top_rate = float(np.mean(labels[scores >= threshold]))
    return Metrics(
        observations=int(labels.size),
        toxic_rate=rate,
        roc_auc=float(roc_auc_score(labels, scores)),
        average_precision=float(average_precision_score(labels, scores)),
        brier_score=float(brier_score_loss(labels, scores)),
        top_decile_lift=float(top_rate / rate),
    )


def bootstrap(values: list[float], samples: int, seed: int) -> dict[str, float | int]:
    x = np.asarray([v for v in values if np.isfinite(v)], dtype=np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(samples, x.size))
    means = np.mean(x[idx], axis=1)
    return {
        "days": int(x.size),
        "mean": float(np.mean(x)),
        "ci_025": float(np.quantile(means, 0.025)),
        "ci_975": float(np.quantile(means, 0.975)),
        "positive_day_fraction": float(np.mean(x > 0)),
    }


def evaluate(
    ch: Client,
    symbol: str,
    split_dates: list[date],
    horizons: tuple[int, ...],
    window_seconds: int,
    states: dict[int, dict[str, ModelState]],
    bootstrap_samples: int,
) -> dict[str, object]:
    result: dict[str, object] = {}

    for h in horizons:
        daily: list[dict[str, object]] = []
        pooled_labels: list[np.ndarray] = []
        pooled_scores = {name: [] for name in MODELS}

        for d in split_dates:
            print(f"{symbol} eval H={h}s {d}", flush=True)
            data = load_day(ch, d, symbol)
            phi, valid, labels = day_dataset(data, h, window_seconds)
            model_metrics: dict[str, dict[str, object]] = {}

            for name in MODELS:
                model = states[h][name]
                features = feature_matrix(data, phi, name, valid)
                scores = model.classifier.predict_proba(model.scaler.transform(features))[:, 1]
                pooled_scores[name].append(scores.astype(np.float32, copy=False))
                model_metrics[name] = asdict(metrics(labels, scores))

            pooled_labels.append(labels)
            m0, m1, m2 = (model_metrics[name] for name in MODELS)
            daily.append({
                "date": d.isoformat(),
                "models": model_metrics,
                "m1_minus_m0": {
                    "roc_auc": m1["roc_auc"] - m0["roc_auc"],
                    "average_precision": m1["average_precision"] - m0["average_precision"],
                    "brier_improvement": m0["brier_score"] - m1["brier_score"],
                    "top_decile_lift": m1["top_decile_lift"] - m0["top_decile_lift"],
                },
                "m2_minus_m1": {
                    "roc_auc": m2["roc_auc"] - m1["roc_auc"],
                    "average_precision": m2["average_precision"] - m1["average_precision"],
                    "brier_improvement": m1["brier_score"] - m2["brier_score"],
                    "top_decile_lift": m2["top_decile_lift"] - m1["top_decile_lift"],
                },
            })

        all_labels = np.concatenate(pooled_labels)
        pooled = {
            name: asdict(metrics(all_labels, np.concatenate(pooled_scores[name])))
            for name in MODELS
        }
        boot: dict[str, object] = {}
        for comparison in ("m1_minus_m0", "m2_minus_m1"):
            boot[comparison] = {}
            for metric_name in ("roc_auc", "average_precision", "brier_improvement", "top_decile_lift"):
                values = [day[comparison][metric_name] for day in daily]
                boot[comparison][metric_name] = bootstrap(
                    values,
                    bootstrap_samples,
                    SEED + h + len(metric_name) + len(comparison),
                )

        result[str(h)] = {"daily": daily, "pooled": pooled, "bootstrap": boot}

    return result


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def write_output(path: str, output: dict[str, object]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary_path = f"{path}.part"
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporary_path, path)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    p.add_argument("--horizons-seconds", nargs="+", type=int, default=[1, 5])
    p.add_argument("--target-window-seconds", type=int, default=1)
    p.add_argument("--train-start", type=parse_date, required=True)
    p.add_argument("--train-end", type=parse_date, required=True)
    p.add_argument("--validation-start", type=parse_date, required=True)
    p.add_argument("--validation-end", type=parse_date, required=True)
    p.add_argument("--test-start", type=parse_date, required=True)
    p.add_argument("--test-end", type=parse_date, required=True)
    p.add_argument("--bootstrap-samples", type=int, default=5000)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    train_dates = dates(args.train_start, args.train_end)
    validation_dates = dates(args.validation_start, args.validation_end)
    test_dates = dates(args.test_start, args.test_end)
    all_dates = train_dates + validation_dates + test_dates
    if len(set(all_dates)) != len(all_dates):
        raise ValueError("Date ranges overlap")

    horizons = tuple(sorted(set(args.horizons_seconds)))
    ch = client()
    output: dict[str, object] = {
        "configuration": {
            "symbols": args.symbols,
            "horizons_seconds": horizons,
            "target_window_seconds": args.target_window_seconds,
            "train_dates": [d.isoformat() for d in train_dates],
            "validation_dates": [d.isoformat() for d in validation_dates],
            "test_dates": [d.isoformat() for d in test_dates],
        },
        "symbols": {},
    }

    for symbol in args.symbols:
        states = fit(ch, symbol, train_dates, horizons, args.target_window_seconds)
        validation = evaluate(
            ch, symbol, validation_dates, horizons,
            args.target_window_seconds, states, args.bootstrap_samples,
        )
        test = evaluate(
            ch, symbol, test_dates, horizons,
            args.target_window_seconds, states, args.bootstrap_samples,
        )
        output["symbols"][symbol] = {"validation": validation, "test": test}
        write_output(args.output, output)

        for h in horizons:
            m10 = test[str(h)]["bootstrap"]["m1_minus_m0"]["average_precision"]
            m21 = test[str(h)]["bootstrap"]["m2_minus_m1"]["average_precision"]
            print(
                f"{symbol} H={h}s "
                f"M1-M0 AP={m10['mean']:+.6f} CI=[{m10['ci_025']:+.6f},{m10['ci_975']:+.6f}] "
                f"M2-M1 AP={m21['mean']:+.6f} CI=[{m21['ci_025']:+.6f},{m21['ci_975']:+.6f}]",
                flush=True,
            )

    write_output(args.output, output)


if __name__ == "__main__":
    main()
