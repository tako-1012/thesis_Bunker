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
    alpha: float = 0.5
    beta: float = 0.5


RESOLUTION = 0.5          # grid resolution [m/cell]
# Terrain weight and slope share of the "balanced" profile, selected on the
# validation split by experiments/analyze_weights.py (results/selected_weights.json).
# check_selected_weights() guards against the two drifting apart.
DEFAULT_W = 8.0
G = 9.81


def check_selected_weights(path):
    """Fail loudly if the defaults differ from the weights selected on validation."""
    import json
    sel = json.load(open(path))["main"]
    if (sel["w"], sel["alpha"]) != (DEFAULT_W, CostWeights().alpha):
        raise SystemExit(f"config defaults (w={DEFAULT_W}, alpha={CostWeights().alpha}) differ from "
                         f"selected weights {sel}; update tapp/config.py")
    return sel
