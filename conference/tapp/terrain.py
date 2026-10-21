"""Procedural 2.5D terrain generation (deterministic given a seed).

Four terrain families are generated, all scaled with the map side length so
that slope statistics are comparable across map sizes:

* hills   - fractal rolling hills
* ridge   - a steep ridge across the start-goal line with a few passes
* craters - mild fractal relief with crater-like depressions
* rocky   - mild relief, rough patches and scattered rocks (lethal obstacles)
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from .config import RESOLUTION

TERRAIN_TYPES = ("hills", "ridge", "craters", "rocky")


def fractal_noise(n, beta, rng):
    """Spectral synthesis of 1/f^beta noise, normalised to zero mean, unit std."""
    kx = np.fft.fftfreq(n)[:, None]
    ky = np.fft.fftfreq(n)[None, :]
    k = np.sqrt(kx ** 2 + ky ** 2)
    k[0, 0] = 1.0
    amp = k ** (-beta / 2.0)
    amp[0, 0] = 0.0
    phase = rng.uniform(0, 2 * np.pi, (n, n))
    field = np.real(np.fft.ifft2(amp * np.exp(1j * phase)))
    field -= field.mean()
    return field / field.std()


def _grid(n):
    c = (np.arange(n) + 0.5) * RESOLUTION
    return np.meshgrid(c, c, indexing="ij")  # x along axis 0, y along axis 1


def _tan_slope(elev):
    gx, gy = np.gradient(elev, RESOLUTION)
    return np.hypot(gx, gy)


def relief(n, target_median_slope_deg, rng, beta=3.0, smooth_m=1.5):
    """Smooth fractal relief scaled so that its median slope equals the target."""
    f = gaussian_filter(fractal_noise(n, beta, rng), smooth_m / RESOLUTION)
    return f * np.tan(np.radians(target_median_slope_deg)) / np.median(_tan_slope(f))


def generate(kind, side_m, seed):
    """Return dict(elev [m], rock mask) for one map."""
    rng = np.random.default_rng(seed)
    n = int(round(side_m / RESOLUTION))
    X, Y = _grid(n)
    L = side_m
    rock = np.zeros((n, n), dtype=bool)
    # micro relief (sensor-scale roughness), 1 cm std everywhere
    micro = 0.01 * gaussian_filter(rng.normal(size=(n, n)), 0.7) / 0.2

    if kind == "hills":
        elev = relief(n, 11.0, rng, beta=3.2)
    elif kind == "ridge":
        elev = relief(n, 4.0, rng)
        # steep ridge perpendicular to the x axis (start left, goal right)
        x0 = rng.uniform(0.4, 0.6) * L
        width = rng.uniform(0.04, 0.06) * L
        height = rng.uniform(0.7, 1.0) * width  # flank slope ~ 30-40 deg
        ridge = height * np.exp(-((X - x0) / width) ** 2)
        notch = np.ones_like(ridge)  # one or two passes
        for _ in range(rng.integers(1, 3)):
            yc = rng.uniform(0.15, 0.85) * L
            notch *= 1.0 - 0.85 * np.exp(-((Y - yc) / (0.06 * L)) ** 2)
        elev = elev + ridge * notch
    elif kind == "craters":
        elev = relief(n, 4.0, rng)
        for _ in range(rng.integers(6, 12)):
            cx, cy = rng.uniform(0.15, 0.85, 2) * L
            r = rng.uniform(0.05, 0.12) * L
            d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / r
            depth = rng.uniform(0.3, 0.6) * r
            elev += depth * (0.25 * np.exp(-((d - 1.0) / 0.25) ** 2) - np.exp(-(d / 0.75) ** 2))
    elif kind == "rocky":
        elev = relief(n, 4.0, rng)
        mask = gaussian_filter(rng.normal(size=(n, n)), sigma=0.04 * L / RESOLUTION)
        mask = (mask - mask.mean()) / mask.std()
        patches = 1.0 / (1.0 + np.exp(-4.0 * (mask - 0.5)))
        micro = micro + 0.08 * patches * gaussian_filter(rng.normal(size=(n, n)), 0.7) / 0.2
        n_rocks = int(0.004 * n * n / 4)
        for _ in range(n_rocks):
            cx, cy = rng.uniform(0, L, 2)
            r = rng.uniform(0.2, 0.8)
            rock |= (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
    else:
        raise ValueError(kind)

    elev = elev - elev.min() + micro
    return {"elev": elev.astype(np.float64), "rock": rock, "kind": kind,
            "side_m": side_m, "seed": seed}


def sample_start_goal(lethal, side_m, rng, margin=0.08):
    """Start in the left band, goal in the right band, both on free cells."""
    n = lethal.shape[0]
    lo, hi = int(margin * n), int((margin + 0.10) * n)
    for _ in range(1000):
        s = (rng.integers(lo, hi), rng.integers(lo, n - lo))
        g = (rng.integers(n - hi, n - lo), rng.integers(lo, n - lo))
        if not lethal[s] and not lethal[g]:
            return s, g
    return None
