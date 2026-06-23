from dataclasses import dataclass


@dataclass
class RGFlowPoint:
    window_size: int
    currency: str
    mean_phi: float
    var_phi: float
    autocorr_lag1: float
    stress_probability: float
