from dataclasses import dataclass

import numpy as np


@dataclass
class RGFlowPoint:
    window_size: int
    currency: str
    mean_phi: float
    var_phi: float
    autocorr_lag1: float
    stress_probability: float


class CoarseGrainingEngine:
    def estimate_rg_flow(
        self,
        *,
        phi_by_currency: dict[str, list[float]],
        window_sizes: list[int],
        stress_threshold: float = 0.8,
    ) -> list[RGFlowPoint]:
        result: list[RGFlowPoint] = []

        for currency, values in phi_by_currency.items():
            arr = np.asarray(values, dtype=float)

            if arr.size == 0:
                continue

            for window_size in window_sizes:
                coarse = self._coarse_grain(arr, window_size)

                if coarse.size == 0:
                    continue

                result.append(
                    RGFlowPoint(
                        window_size=window_size,
                        currency=currency,
                        mean_phi=round(float(np.mean(coarse)), 6),
                        var_phi=round(float(np.var(coarse)), 6),
                        autocorr_lag1=round(self._autocorr_lag1(coarse), 6),
                        stress_probability=round(
                            float(np.mean(np.abs(coarse) >= stress_threshold)),
                            6,
                        ),
                    )
                )
        return result

    @staticmethod
    def _coarse_grain(arr: np.ndarray, window_size: int) -> np.ndarray:
        if window_size <= 1:
            return arr

        usable_size = arr.size - (arr.size % window_size)

        if usable_size <= 0:
            return np.array([], dtype=float)

        trimmed = arr[:usable_size]
        blocks = trimmed.reshape(-1, window_size)

        return blocks.mean(axis=1)

    @staticmethod
    def _autocorr_lag1(arr: np.ndarray) -> float:
        if arr.size < 2:
            return 0.0

        x = arr[:-1]
        y = arr[1:]
        if np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])
