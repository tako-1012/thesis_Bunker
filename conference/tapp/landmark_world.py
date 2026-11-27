"""Deterministic known landmarks and reference samples of the Gazebo visual mesh."""

from dataclasses import dataclass
import hashlib
import math
from scipy.ndimage import distance_transform_edt, find_objects, label
import numpy as np

from .config import RESOLUTION
from .traversability import TraversabilityMap

HECTARE_M2 = 10_000
ENDPOINT_GAP_M = 2.
LANDMARK_GAP_M = 1.
TERRAIN_STEP_M = .1
SURFACE_STEP_M = .05
CELL_RADIUS_M = RESOLUTION / math.sqrt(2)


@dataclass(frozen=True)
class Landmark:
    name: str
    shape: str
    x_m: float
    y_m: float
    bottom_z_m: float
    width_m: float
    depth_m: float
    height_m: float
    yaw_rad: float

    @property
    def radius_m(self):
        if self.shape == 'cylinder':
            return self.width_m / 2
        return math.hypot(self.width_m, self.depth_m) / 2


def place_landmarks(truth, patch, density, seed, endpoints_cells):
    """Count by valid land area, then place on non-steep, debris-free terrain.

    Enclosing circles provide conservative surface-to-surface gaps. A pad
    around debris also keeps the two inflated cell masks disjoint.
    """
    terrain, tm = truth['terrain'], truth['tmap']
    land = ~(terrain['water'] | terrain['nodata'])
    area_m2 = np.count_nonzero(land) * RESOLUTION**2
    count = math.floor(density * area_m2 / HECTARE_M2 + .5)
    if not count:
        return area_m2, []

    debris = terrain['rock']
    # Match export_gazebo: each connected component is a bounding rectangle.
    box_cells = np.zeros_like(debris)
    for region in find_objects(label(debris)[0]):
        box_cells[region] = True
    allowed = land & ~tm.steep
    edge_dist = distance_transform_edt(np.pad(allowed, 1))[1:-1, 1:-1] * RESOLUTION
    debris_dist = (distance_transform_edt(~box_cells) * RESOLUTION if box_cells.any()
                   else np.full(land.shape, np.inf))
    inflation_m = math.ceil(tm.robot.footprint_radius / RESOLUTION) * RESOLUTION
    endpoints = np.asarray(endpoints_cells, dtype=float).reshape(-1, 2) * RESOLUTION
    digest = hashlib.sha256(f'{seed}:{patch}'.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:16], 'big'))
    candidates = np.argwhere(allowed)
    if count > len(candidates):
        raise ValueError(f'{patch}: requested {count} landmarks for {len(candidates)} available cells')
    rng.shuffle(candidates)
    candidates = iter(candidates)
    centres = np.empty((count, 2))
    radii = np.empty(count)
    landmarks = []
    first = rng.integers(2)
    for k in range(count):
        shape = 'box' if (k + first) % 2 == 0 else 'cylinder'
        width = rng.uniform(.4, 1.5)
        depth = rng.uniform(.4, 1.5) if shape == 'box' else width
        height = rng.uniform(.3, 1.2)
        yaw = rng.uniform(-np.pi, np.pi)
        radius = math.hypot(width, depth) / 2 if shape == 'box' else width / 2
        for i, j in candidates:
            if edge_dist[i, j] <= radius + CELL_RADIUS_M:
                continue
            if debris_dist[i, j] <= radius + CELL_RADIUS_M + 2 * inflation_m:
                continue
            centre = np.array([i, j]) * RESOLUTION
            if np.any(np.linalg.norm(endpoints - centre, axis=1) < radius + ENDPOINT_GAP_M):
                continue
            if np.any(np.linalg.norm(centres[:k] - centre, axis=1) < radius + radii[:k] + LANDMARK_GAP_M):
                continue
            centres[k], radii[k] = centre, radius
            landmarks.append(Landmark(f'landmark_{k+1}', shape, *map(float, centre),
                                      float(tm.elev[i, j]), width, depth, height, yaw))
            break
        else:
            raise ValueError(f'{patch}: placed {k} of {count} landmarks under the spacing constraints')
    return area_m2, landmarks


def landmark_mask(shape, landmarks):
    """Rasterize XY overlaps with closed grid squares, before robot inflation."""
    mask = np.zeros(shape, bool)
    half = RESOLUTION / 2
    for item in landmarks:
        centre = np.array([item.x_m, item.y_m]) / RESOLUTION
        radius = (item.radius_m + half) / RESOLUTION
        lo = np.maximum(0, np.ceil(centre - radius).astype(int))
        hi = np.minimum(shape, np.floor(centre + radius).astype(int) + 1)
        slices = tuple(slice(a, b) for a, b in zip(lo, hi))
        x, y = (np.indices(tuple(hi - lo)) + (lo - centre)[:, None, None]) * RESOLUTION
        if item.shape == 'cylinder':
            hit = np.hypot(np.maximum(np.abs(x) - half, 0),
                           np.maximum(np.abs(y) - half, 0)) <= item.radius_m
        else:
            a, b = item.width_m / 2, item.depth_m / 2
            c, s = math.cos(item.yaw_rad), math.sin(item.yaw_rad)
            projection = half * (abs(c) + abs(s))
            hit = ((np.abs(x) <= a*abs(c) + b*abs(s) + half)
                   & (np.abs(y) <= a*abs(s) + b*abs(c) + half)
                   & (np.abs(c*x + s*y) <= a + projection)
                   & (np.abs(-s*x + c*y) <= b + projection))
        mask[slices] |= hit
    return mask


def with_landmarks(scenario, mask):
    """Mark fixed objects in the map via the existing obstacle inflation."""
    tm, terrain = scenario['tmap'], scenario['terrain']
    rock = terrain['rock'] | mask
    updated = dict(scenario, terrain=dict(terrain, rock=rock),
                   tmap=TraversabilityMap(tm.elev, rock | terrain['water'] | terrain['nodata'],
                                         tm.robot, tm.weights))
    if 'obstacle' in updated:
        updated['obstacle'] = rock
    return updated


def terrain_points(elev):
    """Sample the two triangles used by terrain_mesh.write_terrain_obj."""
    z = np.round(np.asarray(elev, dtype=float), 4)
    axes = [np.arange(round((n-1)*RESOLUTION/TERRAIN_STEP_M)+1)*TERRAIN_STEP_M for n in z.shape]
    x, y = np.meshgrid(*axes, indexing='ij', sparse=True)
    # The last sample is on the far edge of the last quad.
    i = np.minimum(np.floor(x/RESOLUTION).astype(int), z.shape[0]-2)
    j = np.minimum(np.floor(y/RESOLUTION).astype(int), z.shape[1]-2)
    u, v = x/RESOLUTION-i, y/RESOLUTION-j
    a, b, c, d = z[i, j], z[i+1, j], z[i+1, j+1], z[i, j+1]
    points = np.empty((len(axes[0]), len(axes[1]), 3), dtype=np.float32)
    points[..., 0], points[..., 1] = x, y
    points[..., 2] = (1-np.maximum(u, v))*a + np.maximum(u-v, 0)*b + np.minimum(u, v)*c + np.maximum(v-u, 0)*d
    return points.reshape(-1, 3)


def _sample_axis(lo, hi):
    return np.linspace(lo, hi, math.ceil((hi-lo)/SURFACE_STEP_M)+1)


def landmark_points(item):
    """Return points on all six box faces or on a cylinder's wall and caps."""
    zs = _sample_axis(0, item.height_m)
    if item.shape == 'box':
        axes = [_sample_axis(-item.width_m/2, item.width_m/2),
                _sample_axis(-item.depth_m/2, item.depth_m/2), zs]
        faces = []
        for axis, samples in enumerate(axes):
            coords = axes.copy()
            coords[axis] = samples[[0, -1]]
            faces.append(np.stack(np.meshgrid(*coords, indexing='ij'), axis=-1).reshape(-1, 3))
        local = np.unique(np.concatenate(faces), axis=0)
    else:
        rim = item.radius_m
        circles = []
        for r in _sample_axis(0, rim):
            theta = np.linspace(0., 2*np.pi, max(1, math.ceil(2*np.pi*r/SURFACE_STEP_M)), endpoint=False)
            circles.append(np.column_stack((r*np.cos(theta), r*np.sin(theta))))
        wall = np.column_stack((np.repeat(circles[-1], len(zs), axis=0), np.tile(zs, len(circles[-1]))))
        caps = np.concatenate(circles[:-1])
        local = np.concatenate([wall, np.c_[caps, np.zeros(len(caps))],
                                np.c_[caps, np.full(len(caps), item.height_m)]])
    c, s = math.cos(item.yaw_rad), math.sin(item.yaw_rad)
    local[:, :2] = local[:, :2] @ np.array([[c, s], [-s, c]])
    return local + [item.x_m, item.y_m, item.bottom_z_m]


def save_reference_cloud(path, elev, landmarks):
    ground = terrain_points(elev)
    points = np.concatenate([ground, *(landmark_points(item).astype(np.float32) for item in landmarks)])
    kind = np.zeros(len(points), dtype=np.uint8)
    kind[len(ground):] = 1
    np.savez_compressed(path, xyz=points, kind=kind, format_version=1,
                        terrain_step_m=TERRAIN_STEP_M, landmark_step_m=SURFACE_STEP_M)
    return len(ground), len(points)-len(ground)
