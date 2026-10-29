"""Alongshore-variable beach profiles, wrack obstacles and gentler eroded hills."""

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from .config import RESOLUTION
from .natural_terrain import (
    generate_natural,
    fractal_surface,
    hydraulic_erosion,
    thermal_erosion,
    rock_population,
    DROPLETS_PER_CELL,
)

BEACH_TYPES = ("beach_gentle", "beach_steep", "beach_scarp", "rolling", "hills")
HILLS_SLOPE = 9.5


def _along(n, side, rng):
    x = (np.arange(n) + 0.5) * RESOLUTION
    field = np.zeros(n)
    for k in range(1, max(1, int(side // 50)) + 1):
        field += k**-1.3 * np.sin(
            2 * np.pi * k * x / max(side, 50) + rng.uniform(0, 2 * np.pi)
        )
    return field / max(np.abs(field).max(), 1e-12)


def generate_beach(kind, side_m, seed):
    if kind not in BEACH_TYPES:
        raise ValueError(kind)
    n = int(round(side_m / RESOLUTION))
    rng = np.random.default_rng(seed)
    blank = np.zeros((n, n), dtype=bool)
    if kind == "rolling":
        t = generate_natural("rolling", side_m, seed)
        return dict(
            t,
            kind=kind,
            water=blank.copy(),
            wet=blank.copy(),
            landward=blank.copy(),
            driftwood=blank.copy(),
            scarp=blank.copy(),
        )
    if kind == "hills":
        base = gaussian_filter(fractal_surface(n, rng), 1.2)
        base *= np.tan(np.radians(HILLS_SLOPE)) / np.median(
            np.hypot(*np.gradient(base, RESOLUTION))
        )
        base -= base.min()
        pre = base.copy()
        z = hydraulic_erosion(base, rng, int(n * n * DROPLETS_PER_CELL["mountain"]))
        z *= np.tan(np.radians(HILLS_SLOPE)) / np.median(
            np.hypot(*np.gradient(z, RESOLUTION))
        )
        z = thermal_erosion(z, 38)
        return dict(
            elev=z - z.min(),
            rock=blank.copy(),
            water=blank.copy(),
            wet=blank.copy(),
            landward=blank.copy(),
            driftwood=blank.copy(),
            scarp=blank.copy(),
            pre_elev=pre,
            kind=kind,
            side_m=side_m,
            seed=seed,
        )
    # Profile draws are independent except for the physically ordered crest height.
    scarp_height = rng.uniform(0.5, 1.5) if kind == "beach_scarp" else 0.0
    beta_range = (1 / 30, 1 / 15) if kind == "beach_gentle" else (1 / 12, 1 / 6)
    beta0 = rng.uniform(*beta_range)
    ht = rng.uniform(0.3, 1)
    hb0 = rng.uniform(max(1, ht + 0.3, scarp_height + 0.3), 2.5)
    shoreline = 0.18 * side_m + min(3, 0.04 * side_m) * _along(n, side_m, rng)
    beta = np.clip(beta0 * (1 + 0.08 * _along(n, side_m, rng)), *beta_range)
    hb = np.clip(
        hb0 + 0.3 * _along(n, side_m, rng), max(1, ht + 0.3, scarp_height + 0.3), 2.5
    )
    edge = (1 - rng.uniform(0.1, 0.2)) * side_m
    y = (np.arange(n) + 0.5) * RESOLUTION
    u = y[None, :] - shoreline[:, None]
    active = np.zeros(n)
    coverage = 0.0
    if kind == "beach_scarp":
        coverage = rng.uniform(0.3, 0.7)
        field = gaussian_filter1d(rng.normal(size=n), max(1, 3 / RESOLUTION))
        active = (field >= np.quantile(field, 1 - coverage)).astype(float)
        active = gaussian_filter1d(active, 0.5)
    height = scarp_height * active
    # A berm shoulder preserves the specified foreshore slope while fitting a finite map.
    crest = np.minimum(shoreline + hb / beta, edge - 0.08 * side_m)
    tide = np.minimum(shoreline + ht / beta, crest - 0.03 * side_m)
    front_beta = ht / np.maximum(tide - shoreline, 0.5)
    upper = (hb - ht - height) / np.maximum(crest - tide, 0.5)
    z = np.where(
        y[None, :] <= tide[:, None],
        front_beta[:, None] * u,
        ht + upper[:, None] * (y[None, :] - tide[:, None]),
    )
    face = crest - 0.5
    z += height[:, None] * np.clip((y[None, :] - face[:, None]) / 0.35, 0, 1)
    back_beta = rng.uniform(1 / 100, 1 / 30) * rng.choice([-1, 1])
    back = np.maximum(
        hb[:, None] + back_beta * (y[None, :] - crest[:, None]), ht + 0.15
    )
    z = np.where(y[None, :] >= crest[:, None], back, z)
    spacing = rng.uniform(15, 35)
    phase = rng.uniform(0, 2 * np.pi)
    along = (np.arange(n) + 0.5) * RESOLUTION
    varying_phase = 2 * np.pi * along / spacing + phase + 0.15 * _along(n, side_m, rng)
    cusp = rng.uniform(0.1, 0.4) * np.cos(varying_phase)[:, None]
    # Cusps are localized at the upper foreshore, not superimposed on the sea.
    width = max(2.0, side_m * 0.04)
    z += cusp * np.exp(-(((y[None, :] - tide[:, None]) / width) ** 2))
    pre = z.copy()
    noise = gaussian_filter(rng.normal(size=(n, n)), 0.8)
    noise /= max(noise.std(), 1e-12)
    amplitude = np.where(z < ht, 0.01, rng.uniform(0.02, 0.04))
    z += noise * amplitude
    landward = np.broadcast_to(y[None, :] >= edge, (n, n)).copy()
    z += np.tan(np.radians(40)) * np.maximum(y[None, :] - (edge - RESOLUTION), 0)
    water = z < 0
    wet = (z >= 0) & (z < ht)
    rock = blank.copy()
    wood = blank.copy()
    density = rng.uniform(5, 20)
    count = int(round(density * (side_m / 100) ** 2))
    for _ in range(count):
        x = rng.uniform(0, side_m)
        i = min(n - 1, int(x / RESOLUTION))
        if rng.random() < 0.85:
            yy = rng.uniform(tide[i], max(tide[i] + 0.1, crest[i]))
        else:
            yy = rng.uniform(min(crest[i], edge - 0.1), edge)
        length, thickness, angle = (
            rng.uniform(1, 5),
            rng.uniform(0.2, 0.5),
            rng.uniform(0, 2 * np.pi),
        )
        centre = np.array([x, yy])
        d = np.array([np.cos(angle), np.sin(angle)]) * length / 2
        a, b = centre - d, centre + d
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
    rock |= wood
    k = rng.uniform(0.01, 0.03)
    diameters = rock_population(side_m, rng, k)
    for diameter in diameters:
        cx, cy = rng.uniform(0, side_m, 2) / RESOLUTION - 0.5
        rad = diameter / (2 * RESOLUTION)
        sigma = max(rad, 0.5)
        low = np.maximum(0, np.floor([cx - 3 * sigma, cy - 3 * sigma]).astype(int))
        high = np.minimum(
            n, np.ceil([cx + 3 * sigma + 1, cy + 3 * sigma + 1]).astype(int)
        )
        xx, yy = np.mgrid[low[0] : high[0], low[1] : high[1]]
        r2 = (xx - cx) ** 2 + (yy - cy) ** 2
        z[low[0] : high[0], low[1] : high[1]] += (
            diameter * 0.5 * np.exp(-2 * r2 / sigma**2)
        )
        if diameter >= 0.4:
            rock[low[0] : high[0], low[1] : high[1]] |= r2 <= rad**2
    # Classify water/wet from final elevation, after all elevation additions.
    water = z < 0
    wet = (z >= 0) & (z < ht)
    from .traversability import slope_deg

    scarp = (
        (slope_deg(z) >= 45) & ~landward & ~water
        if kind == "beach_scarp"
        else blank.copy()
    )
    return dict(
        elev=z,
        rock=rock,
        water=water,
        wet=wet,
        landward=landward,
        driftwood=wood,
        scarp=scarp,
        pre_elev=pre,
        kind=kind,
        side_m=side_m,
        seed=seed,
        parameters=dict(
            tan_beta=beta0,
            beta_range=beta_range,
            tide_height=ht,
            berm_height=hb0,
            land_edge=edge,
            scarp_height=scarp_height,
            scarp_requested_coverage=coverage,
            driftwood_count=count,
            rock_k=k,
        ),
        shoreline=shoreline,
        tide_position=tide,
        crest_position=crest,
    )
