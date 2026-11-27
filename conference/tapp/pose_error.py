"""Task072 shoreline-frame pose bias and distance-indexed random walk."""

from dataclasses import dataclass
import hashlib
import json
import math

import numpy as np

POSE_ERRORS = ('none', 'bias', 'drift')
ESTIMATED_POSE_TOPIC = '/localization/pose'


def parse_bias(value):
    try:
        bias = tuple(float(part) for part in value.split(','))
    except ValueError:
        raise ValueError('pose-error bias requires along_m,seaward_m,yaw_deg') from None
    if len(bias) != 3 or not all(map(math.isfinite, bias)):
        raise ValueError('pose-error bias requires three finite values: along_m,seaward_m,yaw_deg')
    return bias


@dataclass(frozen=True)
class PoseErrorSettings:
    mode: str = 'none'
    seed: int = 0
    rep: int = 1
    bias: tuple[float, float, float] | None = None
    drift_pct: float | None = None

    def __post_init__(self):
        if self.mode not in POSE_ERRORS:
            raise ValueError('unknown pose-error mode')
        if not isinstance(self.seed, int) or not isinstance(self.rep, int) or self.rep < 1:
            raise ValueError('pose-error seed must be an integer and repetition must be a positive integer')
        if (self.mode == 'bias') != (self.bias is not None):
            raise ValueError('--pose-error-bias must be supplied with --pose-error bias only')
        if (self.mode == 'drift') != (self.drift_pct is not None):
            raise ValueError('--pose-error-drift-pct must be supplied with --pose-error drift only')
        if self.bias is not None and (len(self.bias) != 3 or not all(map(math.isfinite, self.bias))):
            raise ValueError('pose-error bias requires three finite values')
        if self.drift_pct is not None and (not math.isfinite(self.drift_pct) or self.drift_pct < 0):
            raise ValueError('pose-error drift percent must be finite and nonnegative')

    def run_seed(self, patch):
        key = json.dumps([self.seed, patch, self.rep], separators=(',', ':')).encode('ascii')
        return int.from_bytes(hashlib.sha256(key).digest()[:8], 'big')


class PoseError:
    """One instance per run, consuming each accepted ground pose in stamp order."""

    def __init__(self, settings, tangent, normal, run_seed):
        self.axes = np.asarray([tangent, normal], dtype=float)
        if (self.axes.shape != (2, 2) or not np.isfinite(self.axes).all()
                or not np.allclose(self.axes @ self.axes.T, np.eye(2), atol=1e-10, rtol=0)):
            raise ValueError('pose-error coastal axes must be orthonormal')
        # LAS metadata uses the patch's tangent and LANDWARD normal.
        # Gazebo's x/y are that same patch basis, with no global plane rotation.
        self.coastal_axes = self.axes.copy()
        self.coastal_axes[1] *= -1.
        along, sea, yaw = settings.bias if settings.bias is not None else (0., 0., 0.)
        self.error = np.array([along, sea])
        self.yaw_rad = math.radians(yaw)
        self.sigma = settings.drift_pct/100 if settings.drift_pct is not None else 0.
        self.rng = np.random.Generator(np.random.PCG64(run_seed)) if settings.mode == 'drift' else None
        self.previous_xy = None
        self.travel_m = 0.
        self.steps = 0

    def offset(self, x, y):
        if self.previous_xy is not None:
            self.travel_m += math.hypot(x-self.previous_xy[0], y-self.previous_xy[1])
        self.previous_xy = x, y
        if self.rng is not None:
            steps = math.floor(self.travel_m)
            for _ in range(self.steps, steps):
                self.error += self.rng.normal(0., self.sigma, size=2)
            self.steps = steps
        return self.axes @ (self.error @ self.coastal_axes)
