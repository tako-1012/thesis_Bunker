"""Robot and experiment parameters.

Every value here is a modelling assumption and is reported in the paper.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Robot:
    # Conservative traversable slope limit for the tracked UGV [deg].
    max_slope_deg: float = 25.0
    # Roughness at which the roughness term saturates [m] (local height std).
    rough_sat: float = 0.10
    # Footprint radius used to inflate geometric obstacles (rocks) [m].
    footprint_radius: float = 0.5
    # Mass and rolling-resistance coefficient for the energy estimate.
    mass_kg: float = 150.0
    rolling_coeff: float = 0.15


@dataclass(frozen=True)
class CostWeights:
    # c = alpha * slope_term + beta * roughness_term, alpha + beta = 1
    alpha: float = 0.7
    beta: float = 0.3


RESOLUTION = 0.5          # grid resolution [m/cell]
DEFAULT_W = 4.0           # terrain weight of TA* (fixed a priori, see sweep)
G = 9.81
