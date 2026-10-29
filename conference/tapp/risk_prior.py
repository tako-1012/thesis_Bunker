"""Validation-calibrated expected terrain cost and lethal-cell probability."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .prior import PriorMap, coarse_elevation, coarse_prior
from .scenario import build
from .terrain import TERRAIN_TYPES
from .traversability import slope_deg


@dataclass
class Calibration:
    cell_m: float
    edges_deg: list
    mean_cost: list
    p_lethal: list
    counts: list


def _bins(slope, edges):
    return np.clip(np.searchsorted(edges, slope, side="right") - 1, 0, len(edges) - 2)


def calibrate(cell_m, seeds=range(100, 105), sizes=(50, 100), kinds=None) -> Calibration:
    """Pool all cells and terrain kinds; never train on a test seed."""
    seeds, sizes = tuple(seeds), tuple(sizes)
    kinds = TERRAIN_TYPES if kinds is None else tuple(kinds)
    if any(seed in range(10) for seed in seeds):
        raise ValueError("test seeds 0-9 must not be used for calibration")
    if not seeds or not sizes or not kinds:
        raise ValueError("calibration requires seeds, sizes and terrain kinds")
    edges = list(np.arange(0.0, 27.5, 2.5)) + [90.0]
    n = len(edges) - 1
    counts = np.zeros(n, dtype=np.int64)
    costs, lethal = np.zeros(n), np.zeros(n)
    for kind in kinds:
        for size in sizes:
            for seed in seeds:
                tm = build(kind, size, seed)["tmap"]
                bins = _bins(slope_deg(coarse_elevation(tm, cell_m)), edges).ravel()
                counts += np.bincount(bins, minlength=n)
                costs += np.bincount(bins, weights=tm.cost.ravel(), minlength=n)
                lethal += np.bincount(bins, weights=tm.lethal.ravel(), minlength=n)
    means, probs = costs / np.maximum(counts, 1), lethal / np.maximum(counts, 1)
    occupied = np.flatnonzero(counts)
    for b in np.flatnonzero(counts == 0):
        lower = occupied[occupied < b]
        source = lower[-1] if len(lower) else occupied[0]
        means[b], probs[b] = means[source], probs[source]
    return Calibration(cell_m=float(cell_m), edges_deg=edges, mean_cost=means.tolist(),
                       p_lethal=probs.tolist(), counts=counts.tolist())


def risk_prior(tmap, cell_m, calib, lam, z_noise_m=0.0, seed=0) -> PriorMap:
    """Expected true cost plus lambda times true-lethality probability."""
    if cell_m != calib.cell_m:
        raise ValueError("calibration cell size does not match the prior")
    if not np.isfinite(lam) or lam < 0:
        raise ValueError("lam must be finite and nonnegative")
    elev = coarse_elevation(tmap, cell_m, z_noise_m, seed)
    bins = _bins(slope_deg(elev), calib.edges_deg)
    cost = np.clip(np.asarray(calib.mean_cost)[bins] + lam * np.asarray(calib.p_lethal)[bins], 0, 1)
    lethal = coarse_prior(tmap, cell_m, z_noise_m, seed).lethal
    return PriorMap(cost=cost, lethal=lethal, cell_m=cell_m)


def save_calibration(calib, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(calib), indent=2, allow_nan=False) + "\n")


def load_calibration(path) -> Calibration:
    return Calibration(**json.loads(Path(path).read_text()))
