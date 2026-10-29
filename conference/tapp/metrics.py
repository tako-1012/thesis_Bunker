"""Planner-independent path evaluation on the ground-truth terrain.

Every path (grid or any-angle) is resampled at a fixed arc-length step and
evaluated with the same code, so metrics are comparable across planners.
"""
import numpy as np
from scipy.ndimage import map_coordinates

from .config import RESOLUTION, G

STEP_M = 0.1


def resample(path_cells):
    p = np.asarray(path_cells, dtype=float)
    d = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(d)])
    total = s[-1]
    k = max(int(np.ceil(total * RESOLUTION / STEP_M)), 1)
    q = np.linspace(0.0, total, k + 1)
    x = np.interp(q, s, p[:, 0])
    y = np.interp(q, s, p[:, 1])
    return x, y


def evaluate(path_cells, tmap, roll_limit=None):
    x, y = resample(path_cells)
    z = map_coordinates(tmap.elev, [x, y], order=1, mode="nearest")
    xi = np.clip(np.rint(x).astype(int), 0, tmap.shape[0] - 1)
    yi = np.clip(np.rint(y).astype(int), 0, tmap.shape[1] - 1)
    dxy = np.hypot(np.diff(x), np.diff(y)) * RESOLUTION
    dz = np.diff(z)
    seg3d = np.hypot(dxy, dz)
    length_xy = dxy.sum()
    length_3d = seg3d.sum()
    climb = np.clip(dz, 0, None).sum()
    slope = tmap.slope[xi, yi]
    cost = tmap.cost[xi, yi]
    # samples are uniform in arc length, so plain means are length-weighted
    mean_cost = float(cost.mean())
    rough = tmap.rough[xi, yi]
    steep_frac = float(tmap.steep[xi, yi].mean())
    steep_len = steep_frac * float(length_xy)
    rock_hit = bool(tmap.rock[xi, yi].any())
    # directional pitch over 1 m windows
    win = max(int(round(1.0 / STEP_M)), 1)
    if len(z) > win:
        pitch = np.degrees(np.arctan(np.abs(z[win:] - z[:-win]) /
                                     np.maximum(np.hypot(x[win:] - x[:-win], y[win:] - y[:-win]) * RESOLUTION, 1e-6)))
        max_pitch = float(pitch.max())
    else:
        max_pitch = 0.0
    # heading-dependent attitude: pitch along, roll across the direction of travel
    hx, hy = np.diff(x), np.diff(y)
    hn = np.maximum(np.hypot(hx, hy), 1e-12)
    ux, uy = hx / hn, hy / hn
    gxs, gys = tmap.gx[xi[:-1], yi[:-1]], tmap.gy[xi[:-1], yi[:-1]]
    pitch_dir = np.degrees(np.arctan(np.abs(gxs * ux + gys * uy)))
    roll = np.degrees(np.arctan(np.abs(gxs * uy - gys * ux)))
    m, mu = tmap.robot.mass_kg, tmap.robot.rolling_coeff
    energy_kj = m * G * (mu * length_xy + climb) / 1000.0
    return {
        "length_xy": float(length_xy),
        "length_3d": float(length_3d),
        "climb": float(climb),
        "max_slope": float(slope.max()),
        "p95_slope": float(np.percentile(slope, 95)),
        "max_pitch": max_pitch,
        "max_roll": float(roll.max()),
        "p95_roll": float(np.percentile(roll, 95)),
        "roll_frac": float((roll > (tmap.robot.max_roll_deg if roll_limit is None else roll_limit)).mean()),
        "max_pitch_dir": float(pitch_dir.max()),
        "pitch_frac": float((pitch_dir > tmap.robot.max_slope_deg).mean()),
        "mean_cost": mean_cost,
        "mean_rough": float(rough.mean()),
        "p95_rough": float(np.percentile(rough, 95)),
        "steep_len": steep_len,
        "steep_frac": steep_frac,
        "rock_hit": rock_hit,
        "energy_kj": float(energy_kj),
    }
