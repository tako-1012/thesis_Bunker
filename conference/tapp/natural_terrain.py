"""Spectral relief, Beyer-style droplet transport, talus relaxation and rock populations.

Physical constants are modelling assumptions; no test-seed fitting is performed.
"""

import numpy as np
from scipy.ndimage import gaussian_filter
from .config import RESOLUTION
from .terrain import fractal_noise
from .traversability import slope_deg

NATURAL_TYPES = ("rolling", "mountain", "badlands", "dunes", "boulders")
H = 0.8
DROPLETS_PER_CELL = {"rolling": 0.03, "mountain": 0.12, "badlands": 0.30}
MAX_STEPS = 40
ERODE_RATE = 0.3
DEPOSIT_RATE = 0.3
CAPACITY = 4.0
EVAPORATION = 0.02
INERTIA = 0.05
EROSION_RADIUS = 2
GRAVITY = 4.0
MIN_DROP = 0.01
BATCH_SIZE = 512
THERMAL_STEPS = 15
TARGET_SLOPE = {"rolling": 5.5, "mountain": 15.0, "badlands": 15.0}
ROCK_K = 0.10
MIN_DIAMETER = 0.1


def fractal_surface(n, rng):
    return fractal_noise(n, 2 * H + 2, rng)


def spectrum_slope(elev):
    n = elev.shape[0]
    k = np.hypot(np.fft.fftfreq(n)[:, None], np.fft.fftfreq(n)[None, :]) * n
    bins = np.floor(k).astype(int)
    power = np.abs(np.fft.fft2(elev - elev.mean())) ** 2
    counts = np.bincount(bins.ravel())
    radial = np.bincount(bins.ravel(), weights=power.ravel()) / np.maximum(counts, 1)
    freq = np.arange(len(radial))
    use = (freq >= 3) & (freq <= n // 4) & (radial > 0)
    return float(np.polyfit(np.log(freq[use]), np.log(radial[use]), 1)[0])


def _height_gradient(z, p):
    i = np.floor(p).astype(int)
    f = p - i
    x, y = i.T
    u, v = f.T
    a, b, c, d = z[x, y], z[x + 1, y], z[x, y + 1], z[x + 1, y + 1]
    height = a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v
    gradient = np.column_stack(
        ((b - a) * (1 - v) + (d - c) * v, (c - a) * (1 - u) + (d - b) * u)
    )
    return height, gradient


def hydraulic_erosion(elev, rng, droplets):
    """Batched droplets conserve transported soil, including sediment on exit.

    Directions use bilinear gradients and inertia; capacity depends on descent,
    speed and water. Soil removal uses a normalized radial brush. Simultaneous
    requests are capped at the soil available in each cell.
    """
    z = elev.copy()
    n = len(z)
    brush = [
        (x, y, max(0, EROSION_RADIUS - np.hypot(x, y)))
        for x in range(-EROSION_RADIUS, EROSION_RADIUS + 1)
        for y in range(-EROSION_RADIUS, EROSION_RADIUS + 1)
        if np.hypot(x, y) < EROSION_RADIUS
    ]
    norm = sum(w for _, _, w in brush)
    for begin in range(0, droplets, BATCH_SIZE):
        m = min(BATCH_SIZE, droplets - begin)
        p = rng.uniform(EROSION_RADIUS, n - EROSION_RADIUS - 1, (m, 2))
        direction = np.zeros_like(p)
        speed, water, sediment = np.ones(m), np.ones(m), np.zeros(m)
        for _ in range(MAX_STEPS):
            old, grad = _height_gradient(z, p)
            direction = INERTIA * direction - (1 - INERTIA) * grad
            length = np.linalg.norm(direction, axis=1)
            flat = length < 1e-12
            angles = rng.uniform(0, 2 * np.pi, int(flat.sum()))
            direction[flat] = np.column_stack((np.cos(angles), np.sin(angles)))
            direction /= np.maximum(np.linalg.norm(direction, axis=1)[:, None], 1e-12)
            nxt = p + direction
            inside = ((nxt >= EROSION_RADIUS) & (nxt < n - EROSION_RADIUS - 1)).all(
                axis=1
            )
            nxt = np.clip(nxt, EROSION_RADIUS, n - EROSION_RADIUS - 1 - 1e-8)
            new, _ = _height_gradient(z, nxt)
            change = new - old
            capacity = np.maximum(-change, MIN_DROP) * speed * water * CAPACITY
            deposit = np.where(
                change > 0,
                np.minimum(change, sediment),
                np.maximum(sediment - capacity, 0) * DEPOSIT_RATE,
            )
            deposit = np.where(inside, deposit, sediment)
            ix = np.floor(p).astype(int)
            f = p - ix
            for dx, dy, w in (
                (0, 0, (1 - f[:, 0]) * (1 - f[:, 1])),
                (1, 0, f[:, 0] * (1 - f[:, 1])),
                (0, 1, (1 - f[:, 0]) * f[:, 1]),
                (1, 1, f[:, 0] * f[:, 1]),
            ):
                np.add.at(z, (ix[:, 0] + dx, ix[:, 1] + dy), deposit * w)
            sediment -= deposit
            request = np.where(
                inside,
                np.minimum(
                    np.maximum(capacity - sediment, 0) * ERODE_RATE,
                    np.maximum(-change, 0),
                ),
                0,
            )
            demand = np.zeros_like(z)
            for dx, dy, w in brush:
                np.add.at(demand, (ix[:, 0] + dx, ix[:, 1] + dy), request * w / norm)
            ratio = np.minimum(1, np.maximum(z, 0) / np.maximum(demand, 1e-30))
            removed = demand * ratio
            z -= removed
            for dx, dy, w in brush:
                sediment += request * w / norm * ratio[ix[:, 0] + dx, ix[:, 1] + dy]
            speed = np.sqrt(np.maximum(speed**2 - change * GRAVITY, 0))
            water *= 1 - EVAPORATION
            p = nxt
            if not inside.all():
                p, direction, speed, water, sediment = (
                    a[inside] for a in (p, direction, speed, water, sediment)
                )
            if not len(p):
                break
        if len(p):
            ix = np.floor(p).astype(int)
            np.add.at(z, (ix[:, 0], ix[:, 1]), sediment)
    return z


def thermal_erosion(elev, angle):
    z = elev.copy()
    # Four undirected axes cover all eight neighbours, with synchronous transfer.
    for _ in range(THERMAL_STEPS):
        delta = np.zeros_like(z)
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            a = (
                (slice(0, -1), slice(None))
                if dy == 0
                else (
                    (slice(None), slice(0, -1))
                    if dx == 0
                    else (slice(0, -1), slice(0, -1) if dy == 1 else slice(1, None))
                )
            )
            b = (
                (slice(1, None), slice(None))
                if dy == 0
                else (
                    (slice(None), slice(1, None))
                    if dx == 0
                    else (slice(1, None), slice(1, None) if dy == 1 else slice(0, -1))
                )
            )
            d = z[a] - z[b]
            excess = np.maximum(
                np.abs(d) - np.tan(np.radians(angle)) * RESOLUTION * np.hypot(dx, dy), 0
            )
            transfer = np.sign(d) * excess / 16
            delta[a] -= transfer
            delta[b] += transfer
        z += delta
    return z


def rock_population(side_m, rng, k=ROCK_K):
    """Area-law derivative divided by disk area gives the number density."""
    q = 1.79 + 0.152 / k
    ds = np.linspace(MIN_DIAMETER, max(10.0, 20 / q), 20000)
    density = k * q * np.exp(-q * ds) / (np.pi * ds**2 / 4)
    cumulative = np.concatenate(
        ([0.0], np.cumsum((density[1:] + density[:-1]) * np.diff(ds) / 2))
    )
    count = rng.poisson(cumulative[-1] * side_m**2)
    return np.interp(rng.uniform(0, cumulative[-1], count), cumulative, ds)


def generate_natural(kind, side_m, seed):
    if kind not in NATURAL_TYPES:
        raise ValueError(kind)
    n = int(round(side_m / RESOLUTION))
    if n < 16:
        raise ValueError("terrain requires at least 16 cells per side")
    rng = np.random.default_rng(seed)
    base = fractal_surface(n, rng)
    pre = base.copy()
    rock = np.zeros((n, n), dtype=bool)
    diameters = np.empty(0)
    mode = "rolling" if kind == "boulders" else kind
    if mode == "dunes":
        x, y = np.meshgrid(
            (np.arange(n) + 0.5) * RESOLUTION,
            (np.arange(n) + 0.5) * RESOLUTION,
            indexing="ij",
        )
        wavelength = max(8.0, side_m / 5)
        bend = gaussian_filter(base, max(1, n * 0.03)) * wavelength * 0.15
        phase = np.mod((x + bend) / wavelength, 1)
        fraction = np.tan(np.radians(32)) / (
            np.tan(np.radians(8)) + np.tan(np.radians(32))
        )
        height = wavelength * fraction * np.tan(np.radians(8))
        z = height * np.where(
            phase < fraction, phase / fraction, (1 - phase) / (1 - fraction)
        )
        # Finite-height crest modulation avoids continuous wall-like slip faces.
        envelope = 0.65 + 0.35 * (
            0.5
            + 0.5 * np.cos(2 * np.pi * y / (side_m * 0.7) + rng.uniform(0, 2 * np.pi))
        )
        z *= envelope
        z += base * 0.02
        pre = z.copy()
        z = thermal_erosion(z, 32)
    else:
        z = gaussian_filter(base, 0.6 if mode == "badlands" else 1.2)
        z *= np.tan(np.radians(TARGET_SLOPE[mode])) / np.median(
            np.hypot(*np.gradient(z, RESOLUTION))
        )
        z -= z.min()
        pre = z.copy()
        z = hydraulic_erosion(z, rng, int(n * n * DROPLETS_PER_CELL[mode]))
        # Size normalization is based on median slope, not test outcomes.
        z *= np.tan(np.radians(TARGET_SLOPE[mode])) / np.median(
            np.hypot(*np.gradient(z, RESOLUTION))
        )
        if mode != "rolling":
            z = thermal_erosion(z, 38)
    if kind == "boulders":
        diameters = rock_population(side_m, rng)
        for diameter in diameters:
            centre = rng.uniform(0, side_m, 2) / RESOLUTION - 0.5
            radius = diameter / (2 * RESOLUTION)
            spread = max(radius, 0.5)
            low = np.maximum(0, np.floor(centre - 3 * spread).astype(int))
            high = np.minimum(n, np.ceil(centre + 3 * spread + 1).astype(int))
            xx, yy = np.mgrid[low[0] : high[0], low[1] : high[1]]
            r2 = (xx - centre[0]) ** 2 + (yy - centre[1]) ** 2
            z[low[0] : high[0], low[1] : high[1]] += (
                diameter * 0.5 * np.exp(-2 * r2 / spread**2)
            )
            if diameter >= 0.4:
                rock[low[0] : high[0], low[1] : high[1]] |= r2 <= radius**2
    return dict(
        elev=z - z.min(),
        rock=rock,
        kind=kind,
        side_m=side_m,
        seed=seed,
        pre_elev=pre,
        rock_diameters=diameters,
    )
