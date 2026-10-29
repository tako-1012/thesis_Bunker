"""Read-only ALB beach patches, nearest-data fill and seeded alongshore scenarios."""

import json
import time
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from .config import RESOLUTION, Robot, CostWeights
from .natural_terrain import rock_population
from .terrain import sample_start_goal
from .traversability import TraversabilityMap
from .planners import astar

DATA = Path(__file__).resolve().parent.parent / "data" / "shizuoka_beach"


def list_patches(split=None):
    rows = json.loads((DATA / "index.json").read_text())
    return [row for row in rows if split is None or row["split"] == split]


def load_patch(name):
    if name not in {row["name"] for row in list_patches()}:
        raise ValueError(f"unknown patch: {name}")
    with np.load(DATA / (name + ".npz"), allow_pickle=False) as data:
        if data["elev"].shape != (400, 400) or float(data["res"]) != RESOLUTION:
            raise ValueError("unexpected patch grid")
        return data["elev"].copy()


def fill_nodata(raw):
    nodata = ~np.isfinite(raw)
    if nodata.all():
        raise ValueError("patch has no measured elevations")
    if nodata.any():
        indices = distance_transform_edt(
            nodata, return_distances=False, return_indices=True
        )
        return np.asarray(raw[tuple(indices)], dtype=float)
    return np.asarray(raw, dtype=float).copy()


def _debris(raw, filled, side_m, rng):
    # Same counts, lengths, thicknesses, angles and rock area law as task 007.
    # Only the centre distribution changes, using measured elevation bands.
    land = np.isfinite(raw) & (raw >= 0)
    band = np.argwhere(land & (raw >= 0.3) & (raw <= 2.5))
    inland = np.argwhere(land & (raw > 2.5))
    fallback = np.argwhere(land)

    def centre():
        candidates = band if rng.random() < 0.85 else inland
        if len(candidates) == 0:
            candidates = fallback
        cell = candidates[rng.integers(len(candidates))]
        return (cell + 0.5) * RESOLUTION + rng.uniform(
            -RESOLUTION / 2, RESOLUTION / 2, 2
        )

    n = len(raw)
    wood = np.zeros(raw.shape, bool)
    rock = wood.copy()
    z = filled.copy()
    count = int(round(rng.uniform(5, 20) * (side_m / 100) ** 2))
    for _ in range(count):
        c = centre()
        length = rng.uniform(1, 5)
        thickness = rng.uniform(0.2, 0.5)
        angle = rng.uniform(0, 2 * np.pi)
        d = np.array([np.cos(angle), np.sin(angle)]) * length / 2
        a, b = c - d, c + d
        low = np.maximum(
            0, np.floor((np.minimum(a, b) - thickness) / RESOLUTION).astype(int)
        )
        high = np.minimum(
            n, np.ceil((np.maximum(a, b) + thickness) / RESOLUTION).astype(int) + 1
        )
        xx, yy = np.mgrid[low[0] : high[0], low[1] : high[1]]
        px = (xx + 0.5) * RESOLUTION
        py = (yy + 0.5) * RESOLUTION
        t = np.clip(
            ((px - a[0]) * (b[0] - a[0]) + (py - a[1]) * (b[1] - a[1])) / length**2,
            0,
            1,
        )
        mask = (px - a[0] - t * (b[0] - a[0])) ** 2 + (
            py - a[1] - t * (b[1] - a[1])
        ) ** 2 <= (thickness / 2) ** 2
        wood[low[0] : high[0], low[1] : high[1]] |= mask
    wood &= land
    rock |= wood
    k = rng.uniform(0.01, 0.03)
    diameters = rock_population(side_m, rng, k)
    for diameter in diameters:
        cx, cy = centre() / RESOLUTION - 0.5
        rad = diameter / (2 * RESOLUTION)
        sigma = max(rad, 0.5)
        low = np.maximum(0, np.floor([cx - 3 * sigma, cy - 3 * sigma]).astype(int))
        high = np.minimum(
            n, np.ceil([cx + 3 * sigma + 1, cy + 3 * sigma + 1]).astype(int)
        )
        xx, yy = np.mgrid[low[0] : high[0], low[1] : high[1]]
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        region = np.s_[low[0] : high[0], low[1] : high[1]]
        z[region] += diameter * 0.5 * np.exp(-2 * r2 / sigma**2) * land[region]
        if diameter >= 0.4:
            rock[region] |= (r2 <= rad**2) & land[region]
    return (
        z,
        rock,
        wood,
        dict(driftwood_count=count, rock_k=k, rock_count=len(diameters)),
    )


def build_real(
    name, side_m, seed, debris=False, weights=CostWeights(), robot=Robot(), max_tries=20
):
    start = time.perf_counter()
    rows = list_patches()
    index = next((i for i, r in enumerate(rows) if r["name"] == name), None)
    if index is None:
        raise ValueError(f"unknown patch: {name}")
    if side_m not in (100, 200):
        raise ValueError("side_m must be 100 or 200")
    original = load_patch(name)
    for attempt in range(max_tries):
        trial = np.random.SeedSequence(
            [seed, 4000, side_m, index], spawn_key=(attempt,)
        )
        crop_seed, debris_seed, endpoint_seed = trial.spawn(3)
        offset = (
            int(np.random.default_rng(crop_seed).integers(0, 201))
            if side_m == 100
            else 0
        )
        origin = (offset, 60) if side_m == 100 else (0, 0)
        n = int(side_m / RESOLUTION)
        raw = original[origin[0] : origin[0] + n, origin[1] : origin[1] + n].copy()
        nodata = ~np.isfinite(raw)
        water = ~nodata & (raw < 0)
        filled = fill_nodata(raw)
        rock = np.zeros(raw.shape, bool)
        wood = rock.copy()
        parameters = {}
        if debris:
            filled, rock, wood, parameters = _debris(
                raw, filled, side_m, np.random.default_rng(debris_seed)
            )
        tm = TraversabilityMap(filled, nodata | water | rock, robot, weights)
        endpoints = sample_start_goal(
            tm.lethal, side_m, np.random.default_rng(endpoint_seed)
        )
        if endpoints is not None and astar(tm.lethal, *endpoints)["success"]:
            s, g = (tuple(map(int, p)) for p in endpoints)
            terrain = dict(
                elev=filled,
                rock=rock,
                water=water,
                nodata=nodata,
                driftwood=wood,
                parameters=parameters,
            )
            return dict(
                tmap=tm,
                start=s,
                goal=g,
                kind=name,
                side_m=side_m,
                seed=seed,
                used_seed=int(trial.generate_state(1)[0]),
                redraws=attempt,
                water=water,
                nodata=nodata,
                terrain=terrain,
                raw_elev=raw,
                debris=bool(debris),
                split=rows[index]["split"],
                patch_index=index,
                crop_origin_cells=origin,
                generation_time=time.perf_counter() - start,
            )
    raise RuntimeError(
        f"no feasible real beach scenario: {name}, {side_m}, {seed}, debris={debris}"
    )
